from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import tensorflow as tf
from PIL import Image, ImageDraw

from model_lib import (
    SEGMENTATION_META,
    SEGMENTATION_INFERENCE_MODEL,
    SEGMENTATION_SIZE,
    WoundAnalyzer,
    load_mask,
    load_segmentation_image,
)
from train_models import DEFAULT_DATASET, image_files

OUTPUT = Path(__file__).resolve().parent / "segmentation_diagnostics"


def dice_score(truth, prediction):
    intersection = np.sum(truth * prediction)
    return float((2.0 * intersection + 1.0) / (np.sum(truth) + np.sum(prediction) + 1.0))


def largest_component(mask):
    return WoundAnalyzer._clean_mask(mask)


def overlay(image, mask, color):
    image = image.copy()
    tint = np.zeros_like(image)
    tint[..., :] = color
    image[mask] = (image[mask] * 0.45 + tint[mask] * 0.55).astype(np.uint8)
    return image


def diagnostic_tile(path, truth, prediction, probability, score):
    image = np.asarray(Image.open(path).convert("RGB").resize((256, 256)))
    truth = cv2.resize(truth.astype(np.uint8), (256, 256), interpolation=cv2.INTER_NEAREST).astype(bool)
    prediction = cv2.resize(prediction.astype(np.uint8), (256, 256), interpolation=cv2.INTER_NEAREST).astype(bool)
    probability = cv2.resize(probability, (256, 256), interpolation=cv2.INTER_LINEAR)
    probability = cv2.applyColorMap(np.uint8(np.clip(probability, 0, 1) * 255), cv2.COLORMAP_TURBO)
    probability = cv2.cvtColor(probability, cv2.COLOR_BGR2RGB)
    panels = [image, overlay(image, truth, (57, 189, 140)), overlay(image, prediction, (239, 100, 97)), probability]
    tile = Image.new("RGB", (1024, 284), "white")
    for index, panel in enumerate(panels):
        tile.paste(Image.fromarray(panel), (index * 256, 28))
    draw = ImageDraw.Draw(tile)
    draw.text((8, 7), f"{path.name} | Dice {score:.3f}", fill="black")
    draw.text((267, 7), "ground truth", fill="black")
    draw.text((523, 7), "prediction", fill="black")
    draw.text((779, 7), "probability", fill="black")
    return tile


def main():
    OUTPUT.mkdir(exist_ok=True)
    threshold = json.loads(SEGMENTATION_META.read_text())["threshold"]
    model = tf.keras.models.load_model(SEGMENTATION_INFERENCE_MODEL, compile=False)
    image_dir = DEFAULT_DATASET / "segmentation/images/test_images"
    mask_dir = DEFAULT_DATASET / "segmentation/masks/test_masks"
    paths = image_files(image_dir)
    images = np.stack([load_segmentation_image(path) for path in paths])
    truths = np.stack([load_mask(mask_dir / path.name)[..., 0] for path in paths]).astype(bool)
    probabilities = model.predict(images, batch_size=16, verbose=1)[..., 0]
    raw_predictions = probabilities >= threshold
    clean_predictions = np.stack([largest_component(mask) for mask in raw_predictions])
    raw_scores = np.asarray([dice_score(truth, prediction) for truth, prediction in zip(truths, raw_predictions)])
    clean_scores = np.asarray([dice_score(truth, prediction) for truth, prediction in zip(truths, clean_predictions)])
    summary = {
        "threshold": threshold,
        "raw_macro_dice": round(float(raw_scores.mean()), 4),
        "clean_macro_dice": round(float(clean_scores.mean()), 4),
        "empty_ground_truth_count": int(np.sum([not truth.any() for truth in truths])),
        "empty_clean_prediction_count": int(np.sum([not prediction.any() for prediction in clean_predictions])),
        "mean_truth_coverage_percent": round(float(truths.mean() * 100), 4),
        "mean_raw_prediction_coverage_percent": round(float(raw_predictions.mean() * 100), 4),
        "mean_clean_prediction_coverage_percent": round(float(clean_predictions.mean() * 100), 4),
        "mean_probability": round(float(probabilities.mean()), 4),
    }
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    selected = np.argsort(clean_scores)
    sample_indexes = list(selected[:4]) + list(selected[len(selected) // 2 - 2:len(selected) // 2 + 2]) + list(selected[-4:])
    sheet = Image.new("RGB", (1024, len(sample_indexes) * 284), "white")
    for row, index in enumerate(sample_indexes):
        tile = diagnostic_tile(paths[index], truths[index], clean_predictions[index], probabilities[index], clean_scores[index])
        sheet.paste(tile, (0, row * 284))
    sheet.save(OUTPUT / "current_model_samples.jpg", quality=92)


if __name__ == "__main__":
    main()
