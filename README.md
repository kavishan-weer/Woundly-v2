# Woundly

Woundly is a browser-based wound progress tracking prototype. It lets a patient create photo check-ins, sends each image to a local Python server for wound analysis, saves the results in SQLite, and visualizes changes across check-ins. It also includes a clinician portal for reviewing entries.


## What happens in the project

1. A user registers or signs in through the web interface.
2. The patient uploads a wound photo and confirms the prototype consent notice.
3. The frontend sends the image as a Base64 data URL to `POST /api/analyze`.
4. A TensorFlow/Keras U-Net predicts a wound segmentation mask.
5. OpenCV cleans the mask, removes small noise regions, and keeps the meaningful contours.
6. The server calculates frame coverage, perimeter, shape features, mean wound color, and photo brightness/sharpness.
7. Pixels inside the predicted wound mask are grouped into visual HSV color categories.
8. The browser saves the photo and analysis as a check-in associated with the signed-in user.
9. Later entries can be compared in the dashboard and timeline to show relative changes over time.
10. Clinicians can open the separate portal, review patient entries, and add a status or note.

## Features

- Patient registration and login
- Browser photo upload and preview
- U-Net wound-boundary segmentation
- Wound mask visualization
- Pixel-area and contour-perimeter estimates
- Frame coverage and shape measurements
- Brightness and sharpness/photo-quality checks
- Segmented HSV visual color-group percentages
- SQLite-backed photo check-in history
- Patient dashboard, timeline, and progress views
- Clinician queue and entry review workflow
- Role-based API access and bearer-token authentication

## Analysis pipeline

```text
Photo upload
  -> browser preview and Base64 encoding
  -> /api/analyze
  -> resize image to 128 x 128 RGB
  -> Gaussian-blur preprocessing
  -> TensorFlow/Keras U-Net prediction
  -> threshold and morphological cleanup
  -> contour extraction and OpenCV measurements
  -> HSV color grouping inside the mask
  -> brightness/sharpness quality checks
  -> JSON response stored in SQLite
```

### Segmentation

The runtime prefers `my model/unet_wound_segmentation.h5`. If that supplied artifact is unavailable, it falls back to `models/wound_segmentation_unet.keras`. The selected model returns a pixel probability map, which is converted to a binary mask at a configured threshold. Opening and closing operations remove noise, and the largest meaningful regions are retained.

The active segmentation model and threshold metadata are recorded in `models/segmentation_meta.json`. Training and evaluation utilities are also included in `train_models.py`, `evaluate_models.py`, `calibrate_segmentation.py`, and `diagnose_segmentation.py`.

### Measurements

The server currently calculates:

- Segmented pixel area
- Contour perimeter
- Percentage of the 128 × 128 analysis frame covered by the mask
- Mean model probability
- Circularity
- Bounding-box aspect ratio
- Mean RGB value inside the mask
- HSV visual color groups
- Image brightness and Laplacian variance as a blur indicator

These are image-based measurements. Because no calibrated reference marker is present in the photo, Woundly cannot report a physically accurate area in square centimetres or a real-world wound diameter.

### Tissue color display

The tissue view uses fixed HSV rules on pixels inside the predicted mask. It reports mutually exclusive percentages for visual groups such as red/pink-like, yellow/tan-like, dark-like, and pale-like pixels.

These names describe image colors only. They are not medically validated tissue classifications, and lighting or camera settings can change the result.

## Web interfaces

- `index.html` — patient dashboard, photo check-in workflow, timeline, and guidance
- `clinician.html` — clinician login and review queue
- `app.js` — patient application entry point
- `js/clinician_app.js` — clinician portal logic
- `server.py` — static file server and JSON API
- `model_lib.py` — preprocessing, segmentation, measurements, and photo quality logic
- `tissue_analysis.py` — HSV color-group analysis

## Storage and accounts

Woundly uses a local SQLite database, `woundly.db`, for:

- Users and password hashes
- Bearer authentication tokens
- Roles (`patient` or `clinician`)
- Photos and analysis results
- Clinician review statuses and notes

The application is intended for local demonstration. It is not a production security or clinical-record system. Passwords are currently hashed with SHA-256, bearer tokens are stored in the database, and the HTTP server is bound to `127.0.0.1`.

## API

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/health` | Check whether the server is running |
| `POST` | `/api/register` | Register a patient or clinician |
| `POST` | `/api/login` | Log in and receive a bearer token |
| `GET` | `/api/me` | Get the current authenticated user |
| `POST` | `/api/analyze` | Analyze an uploaded image |
| `GET` | `/api/entries` | Get the patient's check-ins |
| `POST` | `/api/entries` | Save a photo and analysis entry |
| `DELETE` | `/api/entries/{id}` | Delete a patient's entry |
| `GET` | `/api/clinician/queue` | Get entries for clinician review |
| `POST` | `/api/clinician/review` | Update an entry's clinician review |

Most account, entry, and clinician routes require:

```http
Authorization: Bearer <token>
```

The analysis route accepts:

```json
{
  "image": "data:image/jpeg;base64,<Base64 image>"
}
```

## Run locally

### Requirements

- Python 3.9 or newer
- TensorFlow
- OpenCV
- NumPy
- Pillow
- A modern browser

### Setup

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
python server.py
```

Open <http://localhost:4173>.

The server creates or updates `woundly.db` automatically.

### Clinician account

The registration API supports a clinician role with registration code `CLINIC2026`. Open `http://localhost:4173/clinician.html` for the clinician interface.

> [!CAUTION]
> The clinician registration code is demo-only configuration. .

## Model training and evaluation

Rebuild or replace the segmentation model locally with:

```bash
python train_models.py
python evaluate_models.py
```

Additional commands inspect and calibrate the segmentation pipeline:

```bash
python calibrate_segmentation.py
python diagnose_segmentation.py
```

Evaluation artifacts are stored under `models/`. Notebook experiments are in `notebooks/`, and additional reports and diagnostics are in `segmentation_diagnostics/` and `my model/`.

## Technology stack

- **Frontend:** HTML, CSS, JavaScript ES modules
- **Server:** Python standard-library HTTP server
- **Database:** SQLite
- **Segmentation:** TensorFlow/Keras U-Net
- **Image analysis:** OpenCV and NumPy
- **Image handling:** Pillow

## Project structure

```text
.
├── index.html                 # Patient web interface
├── clinician.html             # Clinician review interface
├── app.js                     # Patient application entry point
├── server.py                  # HTTP server, API, authentication, SQLite
├── model_lib.py               # Segmentation and image measurements
├── tissue_analysis.py         # HSV color-group analysis
├── train_models.py            # Segmentation model training
├── evaluate_models.py         # Model evaluation utilities
├── calibrate_segmentation.py  # Threshold calibration
├── diagnose_segmentation.py   # Segmentation diagnostics
├── js/                        # Frontend modules
├── css/                       # Frontend styles
├── models/                    # Segmentation/classification artifacts and metadata
├── my model/                  # Supplied model artifacts
├── notebooks/                 # Experiments and analysis notebooks
├── segmentation_diagnostics/  # Generated diagnostic outputs
├── ARCHITECTURE.md            # Architecture detail
└── requirements.txt           # Python dependencies
```


## Safety notice

Do not use Woundly to diagnose a wound, decide on treatment, rule out infection or other complications, or delay professional care. Consult a qualified healthcare professional about concerning or worsening wounds.

## Documentation

- [Architecture](ARCHITECTURE.md)
- [Project report](woundly_project_report.md)
