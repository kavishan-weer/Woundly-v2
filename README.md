# Woundly

Woundly is a local-first wound progress tracking prototype. It lets a user:

- upload and save wound photos on their own device;
- review a longitudinal photo journal;
- compare image-based measurements across photo uploads;
- preview a clinician-facing remote review queue;
- run a real segmentation overlay, visual feature extraction, photo-quality
  checks, pressure-injury category prediction, and segmented HSV color-group
  estimates.

## Run locally

```bash
cd "/Users/kavishanwee/Desktop/ispf"
"/Users/kavishanwee/Desktop/Wound Detection/.venv/bin/python" server.py
```

Then open `http://localhost:4173`.

## Train the models

The exported Keras models are generated from the existing datasets:

```bash
cd "/Users/kavishanwee/Desktop/ispf"
"/Users/kavishanwee/Desktop/Wound Detection/.venv/bin/python" train_models.py
"/Users/kavishanwee/Desktop/Wound Detection/.venv/bin/python" calibrate_segmentation.py
"/Users/kavishanwee/Desktop/Wound Detection/.venv/bin/python" evaluate_models.py
```

## Important prototype boundary

The prototype runs the supplied `224x224` U-Net segmentation model from
`my model/unet_wound_segmentation.h5` and a MobileNetV2 transfer-learning
pressure-injury category classifier. The current held-out results are:

- segmentation macro Dice coefficient: `0.3922` with a calibrated `0.20` mask threshold;
- classification accuracy: `49.12%` on a 57-image held-out split.

These are academic proof-of-concept artifacts, not clinically validated medical
devices. They cannot diagnose infection, assess treatment needs, or replace a
qualified healthcare professional. The current staging folders contain only 258
classification images, and the segmentation and classification datasets do not
share the same image distribution. More clinician-reviewed data and external
validation are required before real-world use.

The segmented HSV color-group estimates are explainable visual descriptors, not
validated tissue diagnoses. They are sensitive to lighting and should be used
to enrich longitudinal comparisons rather than make clinical decisions.

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the implemented inference pipeline and
API response format.
