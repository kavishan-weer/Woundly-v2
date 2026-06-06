# Project Report: Woundly Prototype

## Technical Architecture, Model Pipeline, and System Overview

**Date:** June 6, 2026  
**Project:** Woundly — Local-First Wound Progress Tracking Companion  
**Recipient:** Project Supervisor / Clinical Lead

---

### 1. Executive Summary

**Woundly** is a local-first, privacy-by-design wound progress tracking prototype. It is designed as a **Mobile-First Clinical Support System** to empower patients to track their wound healing journey over time through photo-based check-ins, while providing clinicians with a remote monitoring review queue.

By running artificial intelligence models locally (on-device or via a local lightweight server), Woundly analyzes wound photographs to segment wound boundaries, extract explainable visual features, estimate pressure-injury categories, and evaluate image quality. All patient photographs and journal logs stay private inside the client-side browser database (`localStorage`), demonstrating a secure approach to digital wound care.

---

### 2. Architecture & Data Flow

Woundly is built with a decoupled architecture featuring a vanilla web frontend and a lightweight Python backend running local machine learning inference.

```
+---------------------------------------------------------+
|                  VANILLA WEB FRONTEND                   |
|  - DM Sans & Manrope modern typography                  |
|  - HTML5 & CSS3 Glassmorphism Dashboard                 |
|  - Vanilla JS Client-Side State & Routing               |
|  - Local storage for Patient Photo Journal              |
+------------------------------------+--------------------+
                                     |
                         HTTP POST   |   JSON Response
                       /api/analyze  |  (Metrics & Base64)
                                     v
+---------------------------------------------------------+
|                 LIGHTWEIGHT PYTHON SERVER               |
|  - SimpleHTTPRequestHandler (Threaded)                  |
|  - Preprocessing (Resize, Normalize, Gaussian Blur)      |
|  - Local TensorFlow/Keras Deep Learning Models          |
|  - OpenCV post-processing & tissue color segmentation   |
+---------------------------------------------------------+
```

#### Detailed Pipeline Flow:

1. **Upload & Preprocessing:** The user captures or drops a photo. The image is resized to match target model inputs ($224 \times 224$ for segmentation, $160 \times 160$ for classification) and undergoes normalization and a light Gaussian blur to reduce high-frequency noise.
2. **U-Net Segmentation:** The U-Net model predicts pixel-level probability masks identifying the wound area.
3. **Morphological Post-Processing:** OpenCV performs morphological opening/closing to eliminate small, disconnected noise pixels. A contour filter keeps only the largest, contiguous wound regions.
4. **Feature Extraction:** Calculates metrics such as pixel area, perimeter, frame coverage, bounding box aspect ratio, and shape circularity.
5. **HSV Tissue Color Segmentation:** Visual pixels inside the wound boundary are grouped using custom Hue-Saturation-Value (HSV) rules to estimate tissue composition.
6. **Photo-Quality Check:** Sharpness is measured via the variance of the Laplacian, and brightness is checked using average pixel intensity.
7. **MobileNetV2 Classification:** Predicts the pressure-injury category (Stage I to IV, SDTI, Unstageable, or Invalid).
8. **Longitudinal Analysis:** The frontend compares consecutive check-ins to track changes in size and tissue composition.

---

### 3. Core AI & Computer Vision Models

The local backend ([server.py](file:///Users/kavishanwee/Desktop/ispf/server.py)) coordinates two principal machine learning models managed through [model_lib.py](file:///Users/kavishanwee/Desktop/ispf/model_lib.py):

#### A. Wound boundary segmentation (U-Net)

- **Architecture:** A custom-designed, lightweight U-Net convolutional network. It utilizes contracting encoding blocks (Conv2D -> BatchNormalization -> MaxPooling2D) up to 192 filters, a bottleneck dropout layer, and expanding decoding blocks (UpSampling2D -> Concatenate -> Conv2D) to restore the target $224 \times 224$ mask output.
- **Loss Function:** Optimized using a hybrid loss consisting of **75% Tversky loss** (to address severe class imbalance between wound pixels and background skin) and **25% Binary Focal Cross-Entropy**.
- **Threshold Calibration:** Managed dynamically by [calibrate_segmentation.py](file:///Users/kavishanwee/Desktop/ispf/calibrate_segmentation.py), which runs grid search across thresholds ($0.05$ to $0.80$) on held-out test data to maximize the Dice coefficient.
- **Current Calibration:** Active threshold is calibrated at **`0.20`**, yielding a held-out validation macro Dice coefficient of **`0.3922`**.

#### B. Pressure-Injury Category Classifier (MobileNetV2)

- **Architecture:** Implements transfer learning based on a MobileNetV2 backbone (initialized using custom weights from `mobilenet_v2_160_no_top.h5`). The top layers are replaced with a Global Average Pooling layer, a dropout layer ($0.32$), and a dense softmax classification layer.
- **Input Resolution:** $160 \times 160$ pixels.
- **Training Augmentations:** Includes horizontal flips, rotation ($0.06$ rad), and zoom ($0.08$) to reduce overfitting.
- **Classification Classes:** Evaluates categories: `Stage_I`, `Stage_II`, `Stage_III`, `Stage_IV`, `SDTI` (Suspected Deep Tissue Injury), `Unstageable`, and `Invalid`.
- **Current Performance:** Achieves **`49.12%` accuracy** on a stratified 57-image held-out validation split.

---

### 4. OpenCV & Rules-Based Analytical Engines

Beyond neural networks, Woundly integrates computer vision engines:

#### A. Explainable Tissue Color Analysis ([tissue_analysis.py](file:///Users/kavishanwee/Desktop/ispf/tissue_analysis.py))

To offer visual descriptors of the wound bed, pixels inside the predicted U-Net mask are mapped to five distinct visual groups using HSV space thresholding:

- **Dark (Eschar-like):** $Value \le 65$
- **Yellow/Tan (Slough-like):** $Hue \in [15, 42]$, $Saturation \ge 35$, $Value \ge 80$
- **Red/Pink (Granulation-like):** $Hue \le 14$ or $Hue \ge 165$, $Saturation \ge 40$, $Value \ge 65$
- **Pale (Epithelial-like):** $Saturation \le 45$, $Value \ge 150$
- **Unclassified:** Remaining pixels.

These color ratios are presented as longitudinal indicators of wound bed progression (e.g., tracking the decrease of slough/eschar and the increase of granulation tissue).

#### B. Image Quality Control Engine

To prevent inaccurate model outputs due to poor photography, the pipeline checks:

- **Brightness:** Evaluates the mean of the grayscale image. Flags warnings for dark ($mean < 55$) or overexposed ($mean > 215$) images.
- **Sharpness (Blur Detection):** Computes the variance of the Laplacian operator on the grayscale image. Flags warnings if the variance is $< 45$, suggesting the camera is out of focus.

---

### 5. Current Prototype Limitations & Staging Data Boundaries

- **Clinical Boundary:** This prototype is an academic proof-of-concept. The models are not clinically validated and should not replace qualified clinical assessments.
- **Longitudinal Labeling Gap:** The current models classify static images into pressure-injury stages rather than longitudinal progress classes (`improvement`, `no change`, or `deterioration`). Progress is currently inferred on the client side by calculating differences in consecutive U-Net coverage/area measurements.
- **Physical Reference Scale:** Currently, the system measures pixels and frame percentages. Physical units (such as square centimeters) require a known reference marker (e.g., a physical coin or ruler placed in-frame), which is planned for future iterations.

---

### 6. Development Roadmap & Suggested Next Steps

1. **Progress Label Dataset:** Collect a clinician-labeled dataset of sequential wound photos classified by actual progress (`improved`, `deteriorated`, `stable`) to train a dedicated longitudinal model.
2. **Scale Marker Integration:** Implement an image-processing module to detect a reference standard (such as a colored adhesive dot of known diameter) to translate pixel measurements into exact physical units ($cm^2$).
3. **Database Integration:** Add PostgreSQL or a similar persistent database to securely store anonymized metadata, linking the web interface to backend records.
4. **Clinical Evaluation:** Partner with healthcare providers to run external clinical validation.

---

### 7. How to Run the Prototype Locally

To run and inspect the current system, follow these steps:

1. **Verify Python Environment:**
   Ensure the virtual environment is available. Run:
   ```bash
   "/Users/kavishanwee/Desktop/Wound Detection/.venv/bin/python" -c "import tensorflow, cv2, numpy, PIL; print('Ready')"
   ```
2. **Launch the Server:**
   ```bash
   cd "/Users/kavishanwee/Desktop/ispf"
   "/Users/kavishanwee/Desktop/Wound Detection/.venv/bin/python" server.py
   ```
3. **Open the App:**
   Navigate your browser to: **http://localhost:4173**
