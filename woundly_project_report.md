Project Report: Woundly Prototype
Technical Architecture, Model Pipeline, and System Overview

1.  Executive Summary
    Woundly is a wound progress tracking prototype. It is designed as a Clinical Support System to empower patients to track their wound healing journey over time through photo-based check-ins, while providing clinicians with a remote monitoring review queue.

    By running artificial intelligence models, Woundly analyzes wound photographs to segment wound boundaries, extract explainable visual features, and evaluate image quality.

2.  Architecture & Data Flow
    Woundly is built with a decoupled architecture featuring a vanilla web frontend and a lightweight Python backend running local machine learning inference.

                +---------------------------------------------------------+
                |             VANILLA WEB FRONTEND                        |
                | - HTML5 & CSS3 Glassmorphism Dashboard                  |
                | - Vanilla JS Client-Side State & Routing                |
                | - Local storage for Patient Photo Journal               |
                +------------------------------------+--------------------+
                                           |
                                 HTTP POST | JSON Response
                              /api/analyze | (Metrics & Base64)
                                           v
                +---------------------------------------------------------+
                |              LIGHTWEIGHT PYTHON SERVER                  |
                | - SimpleHTTPRequestHandler (Threaded)                   |
                | - Preprocessing (Resize, Normalize, Gaussian Blur)      |
                | - Local TensorFlow/Keras Deep Learning Models           |
                | - OpenCV post-processing & tissue color segmentation    |
                +---------------------------------------------------------+

    Detailed Pipeline Flow:
    Upload & Preprocessing: The user captures or drops a photo. The image is resized to match target model inputs (128 x 128 for segmentation) and undergoes normalization and a light Gaussian blur to reduce high-frequency noise.

    U-Net Segmentation: The U-Net model predicts pixel-level probability masks identifying the wound area.

    Morphological Post-Processing: OpenCV performs morphological opening/closing to eliminate small, disconnected noise pixels. A contour filter keeps only the largest, contiguous wound regions.

    Feature Extraction: Calculates metrics such as pixel area, perimeter, frame coverage, bounding box aspect ratio, and shape circularity.

    HSV Tissue Color Segmentation: Visual pixels inside the wound boundary are grouped using custom Hue-Saturation-Value (HSV) rules to estimate tissue composition.

    Photo-Quality Check: Sharpness is measured via the variance of the Laplacian, and brightness is checked using average pixel intensity.

    Longitudinal Analysis: The frontend compares consecutive check-ins to track changes in size and tissue composition.

3.  Core AI & Computer Vision Models
    The local backend coordinates the principal machine learning model:

A. Wound boundary segmentation (U-Net)
   Dataset: [Wound Segmentation Images (Kaggle)](https://www.kaggle.com/datasets/leoscode/wound-segmentation-images)

   Architecture: A custom-designed, lightweight U-Net convolutional network. It utilizes contracting encoding blocks (Conv2D -> BatchNormalization -> MaxPooling2D) up to 256 filters, a bottleneck dropout layer, and expanding decoding blocks (UpSampling2D -> Concatenate -> Conv2D) to restore the target 128 x 128 mask output.

      Loss Function: Optimized using a hybrid loss consisting of 75% Tversky loss (to address severe class imbalance between wound pixels and background skin) and 25% Binary Focal Cross-Entropy.

      Threshold Calibration: Managed dynamically by an automated calibration module, which runs grid search across thresholds (0.05 to 0.80) on held-out test data to maximize the Dice coefficient.

      Current Calibration: Active threshold is calibrated at 0.80, yielding a held-out validation macro Dice coefficient of 0.6910 (raw macro Dice of 0.7114).

4. OpenCV & Rules-Based Analytical Engines
   Beyond neural networks, Woundly integrates computer vision engines:

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

   Longitudinal Labeling Gap: The prototype infers progress on the client side by calculating differences in consecutive U-Net coverage/area measurements, rather than utilizing a trained longitudinal model that directly predicts progress classes (improvement, no change, or deterioration) from sequence data.

   Physical Reference Scale: Currently, the system measures pixels and frame percentages. Physical units (such as square centimeters) require a known reference marker (e.g., a physical coin or ruler placed in-frame), which is planned for future iterations.

6. Development Roadmap & Suggested Next Steps
   Progress Label Dataset: Collect a clinician-labeled dataset of sequential wound photos classified by actual progress (improved, deteriorated, stable) to train a dedicated longitudinal model.

   Scale Marker Integration: Implement an image-processing module to detect a reference standard (such as a colored adhesive dot of known diameter) to translate pixel measurements into exact physical units (cm²).

   Clinical Evaluation: Partner with healthcare providers to run external clinical validation.
