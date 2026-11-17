\# Portrait \& MRZ Extraction API



A FastAPI service that takes a photo or scan of a passport or ID card and returns:



\- the \*\*portrait photo\*\*, cropped from the document

\- the \*\*MRZ data\*\* (the machine-readable lines at the bottom of a passport), parsed into clean fields

\- a \*\*validity check\*\*: whether the document is expired, expiring within 90 days, or valid



It includes a simple web interface for uploading documents and viewing the results.



Built during my AI Engineering internship at e\& (Etisalat), June–August 2026.



!\[Demo](screenshots/demo.png)



\*The sample is the official ICAO specimen passport (nationality "UTO" = Utopia). It contains no real personal data.\*



\## How It Works



```

Uploaded image

&#x20;    │

&#x20;    ├──► Face detection (OpenCV YuNet)

&#x20;    │         │

&#x20;    │         ▼

&#x20;    │    Pick highest-confidence face → expand box with margin → crop portrait

&#x20;    │

&#x20;    └──► MRZ detection and OCR (PassportEye + Tesseract with an OCR-B model)

&#x20;              │

&#x20;              ▼

&#x20;         Parse fields → clean names → format dates → check expiry

&#x20;    │

&#x20;    ▼

JSON response (portrait as base64, MRZ fields, expiry status)

```



\### Improving MRZ accuracy



With Tesseract's default English model, the MRZ's `<` filler characters were often misread as letters, so a name like `ANNA<MARIA<<<<` came out as `ANNASMARIACSK`. Upscaling and binarising the image only helped partly. Switching to a Tesseract model trained specifically on the \*\*OCR-B\*\* font used in MRZs fixed it completely, so the specimen now reads exactly as printed.



\## API



\### `POST /extract`



Upload an image as `multipart/form-data` with the field name `file`.



```

curl -X POST -F "file=@sample.png" http://localhost:8000/extract

```



Example response (portrait shortened):



```json

{

&#x20; "success": true,

&#x20; "portrait\_base64": "/9j/4AAQSkZJRg...",

&#x20; "portrait\_confidence": 0.935,

&#x20; "mrz\_fields": {

&#x20;   "surname": "ERIKSSON",

&#x20;   "given\_names": "ANNA MARIA",

&#x20;   "nationality": "UTO",

&#x20;   "sex": "F",

&#x20;   "date\_of\_birth": "1974-08-12",

&#x20;   "expiration\_date": "2012-04-15",

&#x20;   "document\_number": "L898902C3",

&#x20;   "document\_type": "P",

&#x20;   "valid\_score": 100

&#x20; },

&#x20; "expiry\_status": {

&#x20;   "is\_expired": true,

&#x20;   "message": "This document expired on 2012-04-15."

&#x20; }

}

```



| Status | Meaning |

|---|---|

| 200 | Portrait and/or MRZ extracted |

| 400 | The file is not a valid image |

| 422 | No face and no MRZ could be detected |



\### `GET /`



The web interface for uploading a document and viewing the results.



Interactive API docs are available at `/docs` (generated automatically by FastAPI).



\## Tech Stack



| Component | Technology |

|---|---|

| API | FastAPI, Uvicorn |

| Face detection | OpenCV YuNet (`face\_detection\_yunet.onnx`) |

| MRZ detection and parsing | PassportEye |

| OCR | Tesseract with an OCR-B trained model |

| Deployment | Docker, Railway |



\## Project Structure



```

├── app.py                                  # FastAPI app: face detection, MRZ reading, expiry check

├── index.html                              # Web interface

├── face\_detection\_yunet.onnx               # Face detection model

├── tessdata/ocrb.traineddata               # Tesseract model for the MRZ font

├── sample.png                              # ICAO specimen passport for testing

├── screenshots/                            # Demo images

├── Dockerfile

├── requirements.txt

├── API\_Documentation.pdf

└── Portrait\_MRZ\_API\_Solution\_Document.pdf  # Full solution write-up

```



\## Running Locally



\*\*Prerequisite:\*\* \[Tesseract OCR](https://github.com/tesseract-ocr/tesseract) (version 4 or newer) must be installed and on your PATH.



1\. Clone the repo:

&#x20;  ```

&#x20;  git clone https://github.com/uzair852/portrait-mrz-extraction-api.git

&#x20;  cd portrait-mrz-extraction-api

&#x20;  ```

2\. Install dependencies:

&#x20;  ```

&#x20;  pip install -r requirements.txt

&#x20;  ```

3\. Start the server:

&#x20;  ```

&#x20;  uvicorn app:app --reload

&#x20;  ```

4\. Open http://localhost:8000 and upload `sample.png`.



\### With Docker



```

docker build -t mrz-api .

docker run -p 8000:8000 mrz-api

```



The Docker image installs Tesseract automatically.



\## Credits



\- OCR-B Tesseract model: \[Shreeshrii/tessdata\_ocrb](https://github.com/Shreeshrii/tessdata\_ocrb)

\- YuNet face detector: \[OpenCV Zoo](https://github.com/opencv/opencv\_zoo)

