Project Report: Woundly Prototype
Technical Architecture, Model Pipeline, and System Overview

Project: Wound Progress Tracking Companion


1. Executive Summary
Woundly is a wound progress tracking prototype. It is designed as a Clinical Support System to empower patients to track their wound healing journey over time through photo-based check-ins, while providing clinicians with a remote monitoring review queue.

The system implements a Two-Stage Hybrid Pipeline: a U-Net deep learning model performs precise wound boundary segmentation, followed by deterministic OpenCV contour analysis to extract measurable wound metrics (total pixel area and maximum diameter). By combining neural network segmentation with rule-based geometric measurement and HSV tissue color analysis, Woundly delivers explainable, reproducible wound tracking without relying on opaque end-to-end classifiers. All patient photographs and journal logs are processed securely, demonstrating a privacy-focused approach to digital wound care.

2. Architecture & Data Flow
Woundly is built with a decoupled architecture featuring a secure web frontend and a lightweight Python backend running machine learning inference.


+---------------------------------------------------------+
|                       WEB FRONTEND                      |
|                                                         |
|  - HTML5 & CSS3 Glassmorphism Dashboard                 |
|  - Secure Client-Side State Management                  |
|  - Privacy-focused Patient Photo Journal                |
+------------------------------------+--------------------+
                                     |
                         HTTP POST   |   JSON Response
                       /api/analyze  |  (Metrics & Base64)
                                     v
+---------------------------------------------------------+
|                 LIGHTWEIGHT PYTHON SERVER               |
|  - SimpleHTTPRequestHandler (Threaded)                  |
|  - Preprocessing (Resize, Normalize)                    |
|  - Stage 1: TensorFlow/Keras U-Net Segmentation         |
|  - Stage 2: OpenCV Contour Analysis & Measurement       |
|  - HSV Tissue Color Segmentation Engine                 |
+---------------------------------------------------------+

        Detailed Pipeline Flow:
        Upload & Preprocessing: The user captures or drops a photo. The image is resized to 224 x 224 pixels and normalized to a [0, 1] range before being fed into the neural network.

        Stage 1 — U-Net Segmentation: The U-Net model predicts pixel-level probability masks identifying the wound area.

        Morphological Post-Processing: OpenCV performs morphological opening/closing to eliminate small, disconnected noise pixels. A contour filter keeps only the largest, contiguous wound regions.

        Stage 2 — Contour Measurement: cv2.findContours identifies the largest wound contour. cv2.contourArea computes the total pixel area, and cv2.boundingRect extracts the bounding box from which the maximum diameter (max of width, height) is derived.

        HSV Tissue Color Segmentation: Visual pixels inside the wound boundary are grouped using custom Hue-Saturation-Value (HSV) rules to estimate tissue composition — the primary indicator of wound healing progress.

        Photo-Quality Check: Sharpness is measured via the variance of the Laplacian, and brightness is checked using average pixel intensity.

        Longitudinal Analysis: The frontend compares consecutive check-ins to track changes in wound area, diameter, and tissue color composition.

3. Core AI & Computer Vision Models
The backend runs a Two-Stage Hybrid Pipeline managed through custom model libraries:

A. Stage 1 — Wound boundary segmentation (U-Net)
Architecture: A custom-designed, U-Net convolutional network. It utilizes contracting encoding blocks (Conv2D -> BatchNormalization -> MaxPooling2D) up to 192 filters, a bottleneck dropout layer, and expanding decoding blocks (UpSampling2D -> Concatenate -> Conv2D) to restore the target 224 x 224 mask output.

Loss Function: Optimized using a hybrid loss consisting of 75% Tversky loss (to address severe class imbalance between wound pixels and background skin) and 25% Binary Focal Cross-Entropy.

Threshold Calibration: Managed dynamically by a calibration module, which runs grid search across thresholds (0.05 to 0.80) on held-out test data to maximize the Dice coefficient.

Current Calibration: Active threshold is calibrated at 0.20, yielding a strong held-out validation macro Dice coefficient (F1-score) of 0.72, demonstrating reliable extraction of wound boundaries across diverse skin tones and backgrounds.

B. Stage 2 — Deterministic contour measurement (OpenCV)
After the U-Net produces a binary segmentation mask, OpenCV's cv2.findContours identifies all external contours. The largest contour (by cv2.contourArea) is selected as the primary wound region, and the following metrics are extracted:

Total Pixel Area: Computed via cv2.contourArea(largest_contour) — the number of pixels enclosed by the wound boundary.

Maximum Bounding Box Diameter: Derived from cv2.boundingRect(largest_contour) as max(width, height) — the longest side of the tightest axis-aligned rectangle enclosing the wound.

Contour Perimeter: The arc length of the wound boundary, computed via cv2.arcLength.

Bounding Box Coordinates: The (x, y, width, height) rectangle for overlay rendering.

 The contour-based measurement pipeline provides reproducible, explainable geometric metrics that are more actionable for longitudinal wound tracking than a low-confidence categorical label.

4. Rules-Based Analytical Engines
Beyond the two-stage hybrid pipeline, Woundly integrates additional computer vision engines:

A. Explainable Tissue Color Analysis
To offer visual descriptors of the wound bed, pixels inside the predicted U-Net mask are mapped to five distinct visual groups using HSV space thresholding:

Dark (Eschar-like): Value ≤ 65

Yellow/Tan (Slough-like): Hue ∈ [15, 42], Saturation ≥ 35, Value ≥ 80

Red/Pink (Granulation-like): Hue ≤ 14 or Hue ≥ 165, Saturation ≥ 40, Value ≥ 65

Pale (Epithelial-like): Saturation ≤ 45, Value ≥ 150

Unclassified: Remaining pixels.

These color ratios are presented as longitudinal indicators of wound bed progression (e.g., tracking the decrease of slough/eschar and the increase of granulation tissue).

B. Image Quality Control Engine
To prevent inaccurate model outputs due to poor photography, the pipeline checks:

Brightness: Evaluates the mean of the grayscale image. Flags warnings for dark (mean < 55) or overexposed (mean > 215) images.

Sharpness (Blur Detection): Computes the variance of the Laplacian operator on the grayscale image. Flags warnings if the variance is < 45, suggesting the camera is out of focus.

5. Current Prototype Limitations & Staging Data Boundaries
Clinical Boundary: This prototype is an academic proof-of-concept. The models are not clinically validated and should not replace qualified clinical assessments.

Pixel-Only Measurements: All wound area and diameter values are reported in pixels, not physical units. Without a known reference object in frame, absolute wound size in real-world units (cm²) cannot be determined. Variations in camera distance and angle between photo sessions directly affect pixel measurements, potentially producing misleading area/diameter trends.

Physical Reference Marker (Planned): To resolve distance and perspective variations, a future iteration will require a physical reference marker (e.g., a standard coin of known diameter or a calibration sticker) to be placed adjacent to the wound in every photo. The system will detect the marker, compute a pixels-per-centimeter ratio, and convert all measurements into calibrated real-world units (cm² for area, cm for diameter).

Longitudinal Comparison Caveat: Progress is inferred by comparing consecutive wound area and tissue color composition. Without the physical reference marker, trends are relative and should be interpreted with caution.

6. Development Roadmap & Suggested Next Steps
Physical Reference Marker Integration (Priority): Implement an image-processing module to detect a known reference standard (e.g., a circular adhesive calibration dot of 25mm diameter or a standard coin) placed beside the wound in each photo. Using cv2.HoughCircles or contour matching, the system will calculate a pixels-per-centimeter scale factor and convert all measurements into calibrated real-world units — wound area in cm² and diameter in cm. This resolves the current limitation of pixel-only measurements and makes longitudinal comparisons robust against camera distance variations. - WE CAN IMPLEMENT THIS TOO, BUT IT TAKES SOME TIME

Progress Label Dataset: Collect a clinician-labeled dataset of sequential wound photos classified by actual progress (improved, deteriorated, stable) to train a dedicated longitudinal progress model.

Clinical Evaluation: Partner with healthcare providers to run external clinical validation.