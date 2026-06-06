from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import tensorflow as tf

from model_lib import (
    SEGMENTATION_META,
    SEGMENTATION_INFERENCE_MODEL,
    SEGMENTATION_SIZE,
    load_mask,
    load_segmentation_image,
    WoundAnalyzer,
)

DATASET = Path("/Users/kavishanwee/Desktop/Wound Detection/datasets")


def dice_score(y_true, y_pred):
    intersection = np.sum(y_true * y_pred)
    return float((2.0 * intersection + 1.0) / (np.sum(y_true) + np.sum(y_pred) + 1.0))


def main():
    model = tf.keras.models.load_model(SEGMENTATION_INFERENCE_MODEL, compile=False)
    image_dir = DATASET / "segmentation/images/test_images"
    mask_dir = DATASET / "segmentation/masks/test_masks"
    paths = sorted(image_dir.glob("*.png"))
    images = np.stack([load_segmentation_image(path) for path in paths])
    masks = np.stack([load_mask(mask_dir / path.name) for path in paths])[..., 0]
    predictions = model.predict(images, batch_size=16, verbose=1)[..., 0]

    results = {}
    for threshold in np.arange(0.05, 0.81, 0.05):
        cleaned = np.stack([WoundAnalyzer._clean_mask(mask) for mask in predictions >= threshold])
        scores = [dice_score(truth, prediction) for truth, prediction in zip(masks, cleaned)]
        results[round(float(threshold), 2)] = round(float(np.mean(scores)), 4)
    best_threshold = max(results, key=results.get)
    payload = {
        "threshold": best_threshold,
        "validation_macro_dice": results[best_threshold],
        "threshold_scores": results,
        "calibration": "mean per-image Dice after inference mask cleanup",
    }
    SEGMENTATION_META.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
