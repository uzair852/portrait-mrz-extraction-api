from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
import cv2
import numpy as np
import base64
from passporteye import read_mrz
import tempfile
import os
import re
from datetime import datetime

app = FastAPI(title="Portrait & MRZ Extraction API")

detector = cv2.FaceDetectorYN.create(
    "face_detection_yunet.onnx",
    "",
    (320, 320),
    score_threshold=0.7
)

def expand_box(x, y, w_box, h_box, img_w, img_h, margin_percent=0.25):
    margin_x = int(w_box * margin_percent)
    margin_y = int(h_box * margin_percent)
    new_x = max(0, x - margin_x)
    new_y = max(0, y - int(margin_y * 1.5))
    new_w = min(img_w - new_x, w_box + 2 * margin_x)
    new_h = min(img_h - new_y, h_box + int(margin_y * 2.5))
    return new_x, new_y, new_w, new_h


def format_mrz_date(date_str, is_expiry=False):
    if not date_str or len(date_str) != 6:
        return None
    yy = int(date_str[0:2])
    mm = date_str[2:4]
    dd = date_str[4:6]

    if is_expiry:
        year = 2000 + yy
    else:
        year = 2000 + yy if yy <= 30 else 1900 + yy

    return f"{year}-{mm}-{dd}"


def clean_mrz_name(name):
    """Removes OCR artifacts left over from misread MRZ padding characters."""
    if not name:
        return name

    # Remove runs of 3+ repeated identical characters (common OCR misread of padding)
    name = re.sub(r'(.)\1{2,}', '', name)

    # Stop at the first single-letter "word" - real names don't contain these,
    # they're leftover fragments from misread padding
    tokens = name.split()
    cleaned = []
    for t in tokens:
        if len(t) == 1:
            break
        cleaned.append(t)

    return ' '.join(cleaned).strip()


def check_expiry(expiry_date_str):
    if not expiry_date_str:
        return {"is_expired": None, "message": "Expiry date could not be determined."}

    try:
        expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d")
    except ValueError:
        return {"is_expired": None, "message": "Expiry date could not be determined."}

    today = datetime.today()
    days_remaining = (expiry_date - today).days

    if days_remaining < 0:
        return {"is_expired": True, "message": f"This document expired on {expiry_date_str}."}
    elif days_remaining <= 90:
        return {"is_expired": False, "message": f"This document is valid but expires soon, in {days_remaining} day(s)."}
    else:
        return {"is_expired": False, "message": f"This document is valid until {expiry_date_str}."}


@app.get("/", response_class=HTMLResponse)
def root():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    contents = await file.read()
    np_array = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(np_array, cv2.IMREAD_COLOR)

    if image is None:
        raise HTTPException(status_code=400, detail="Could not read the uploaded file as a valid image.")

    (h, w) = image.shape[:2]

    detector.setInputSize((w, h))
    faces = detector.detect(image)

    portrait_base64 = None
    confidence = None

    if faces[1] is not None and len(faces[1]) > 0:
        best_face = max(faces[1], key=lambda f: f[-1])
        x, y, w_box, h_box = best_face[:4].astype(int)
        new_x, new_y, new_w, new_h = expand_box(x, y, w_box, h_box, w, h)
        portrait = image[new_y:new_y + new_h, new_x:new_x + new_w]
        success, buffer = cv2.imencode(".jpg", portrait)
        if success:
            portrait_base64 = base64.b64encode(buffer).decode("utf-8")
            confidence = float(best_face[-1])

    mrz_fields = None
    expiry_status = None
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        mrz = read_mrz(tmp_path)
        if mrz is not None:
            data = mrz.to_dict()
            expiration_date = format_mrz_date(data.get("expiration_date"), is_expiry=True)
            mrz_fields = {
                "surname": clean_mrz_name(data.get("surname")),
                "given_names": clean_mrz_name(data.get("names")),
                "nationality": data.get("nationality"),
                "sex": data.get("sex"),
                "date_of_birth": format_mrz_date(data.get("date_of_birth")),
                "expiration_date": expiration_date,
                "document_number": data.get("number"),
                "document_type": data.get("type"),
                "valid_score": data.get("valid_score"),
            }
            expiry_status = check_expiry(expiration_date)
    finally:
        os.remove(tmp_path)

    if portrait_base64 is None and mrz_fields is None:
        raise HTTPException(status_code=422, detail="No face or MRZ data could be detected in the uploaded image.")

    return JSONResponse(content={
        "success": True,
        "portrait_base64": portrait_base64,
        "portrait_confidence": confidence,
        "mrz_fields": mrz_fields,
        "expiry_status": expiry_status
    })
