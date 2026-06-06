# Woundly Prototype Architecture

This prototype follows the interim report's selected **Mobile-First Clinical
Support System**. The browser UI, local inference API, and trained proof-of-
concept model artifacts are implemented.

## Implemented local data flow

```text
Mobile or web upload
  -> preprocessing (resize, normalization, and Gaussian blur)
  -> U-Net segmentation model
  -> feature extraction (area, perimeter, frame coverage, shape, and color)
  -> segmented HSV color-group estimation
  -> image-quality checks (brightness and sharpness)
  -> MobileNetV2 category classifier
  -> cautious frame-coverage comparison against prior photo check-ins
  -> patient dashboard and provider review queue
```

Texture features, persistent cloud records, and clinician-reviewed progress
labels remain future work.

## Required API contract

### Implemented: `POST /api/analyze`

JSON request:

- `image`: browser-generated image data URL

Response:

```json
{
  "segmentation": {
    "mask_data_url": "data:image/png;base64,...",
    "pixel_area": 4210,
    "perimeter_pixels": 273.4,
    "coverage_percent": 25.7,
    "mean_probability": 0.402
  },
  "features": {
    "shape_circularity": 0.73,
    "bounding_box_aspect_ratio": 1.18,
    "mean_wound_rgb": [173.2, 92.4, 81.7]
  },
  "photo_quality": {
    "brightness": 126.3,
    "sharpness": 88.1,
    "status": "good",
    "notes": []
  },
  "tissue_color_analysis": {
    "method": "segmented_hsv_color_groups_v1",
    "total_segmented_pixels": 4210,
    "percentages": {
      "red_pink_like": 61.2,
      "yellow_tan_like": 14.8,
      "dark_like": 3.5,
      "pale_like": 7.1,
      "unclassified": 13.4
    },
    "dominant_group": "red_pink_like",
    "overlay_data_url": "data:image/png;base64,..."
  },
  "classification": {
    "label": "Stage_II",
    "confidence": 0.76,
    "probabilities": {
      "Stage_I": 0.03,
      "Stage_II": 0.76
    }
  },
  "model": {
    "segmentation": "supplied_224px_wound_unet",
    "classification": "mobilenetv2_pressure_injury_classifier"
  }
}
```

The browser keeps photo-analysis entries in local storage for the proof of
concept. A production backend would persist these records.

The HSV color groups are computed only inside the U-Net mask. They are
mutually exclusive visual descriptors and are not validated clinical tissue
labels. Longitudinal color changes can suggest that a photo deserves review,
but lighting differences can affect the estimates.

## Current model implementation

The current runtime loads:

- `my model/unet_wound_segmentation.h5`: supplied `224x224` U-Net trained on
  paired wound images and masks with Gaussian-blurred RGB inputs.
- `models/pressure_injury_classifier.keras`: MobileNetV2 transfer-learning
  classifier trained on the staged pressure-injury image folders.
- `models/evaluation_results.json`: held-out metrics and the classification
  confusion matrix.

`train_models.py` remains available for reproducible local retraining of the
fallback U-Net and category classifier.

Current held-out baseline metrics:

- segmentation macro Dice coefficient: `0.3922` at the calibrated `0.20` threshold;
- classification accuracy: `49.12%` on a 57-image stratified held-out split.

## Dataset-label decision required

The current classification folders are `Stage_I`, `Stage_II`, `Stage_III`,
`Stage_IV`, `SDTI`, `Unstageable`, and `Invalid`. These labels describe
pressure-injury categories. They do **not** directly train the report's proposed
longitudinal output: `improvement`, `no change`, or `deterioration`.

For a valid progress tracker, choose one of these paths:

1. Use the existing folders to train a pressure-injury category classifier,
   present that output separately, and calculate progress only by comparing
   repeated measurements across check-ins.
2. Create a paired longitudinal dataset with clinician-reviewed progress labels
   and train a separate progress classifier.

The first path is the practical academic proof-of-concept route with the current
data.

## Suggested implementation sequence

1. Complete preprocessing and dataset split verification.
2. Train and evaluate the segmentation model with Dice coefficient and IoU.
3. Export a versioned segmentation artifact.
4. Train the pressure-injury category classifier and report accuracy, precision,
   recall, and F1 score.
5. Add persistent records with PostgreSQL and images/masks in object storage.
6. Add a calibrated measurement reference to report physical units such as
   square centimetres instead of image-frame coverage.
7. Run external clinical validation before considering real-world use.
