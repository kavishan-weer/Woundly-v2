from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import tensorflow as tf
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from model_lib import CLASSIFICATION_META, CLASSIFICATION_MODEL
from train_models import DEFAULT_DATASET, classification_dataset

MODEL_DIR = Path(__file__).resolve().parent / "models"


def main():
    classes, _, validation_data = classification_dataset(DEFAULT_DATASET, batch_size=16)
    model = tf.keras.models.load_model(CLASSIFICATION_MODEL, compile=False)
    true_labels, predicted_labels = [], []
    for images, labels in validation_data:
        probabilities = model.predict(images, verbose=0)
        true_labels.extend(labels.numpy().tolist())
        predicted_labels.extend(np.argmax(probabilities, axis=1).tolist())

    segmentation = json.loads((MODEL_DIR / "segmentation_meta.json").read_text())
    results = {
        "segmentation": {
            "calibrated_threshold": segmentation["threshold"],
            "held_out_macro_dice": segmentation["validation_macro_dice"],
        },
        "classification": {
            "architecture": "MobileNetV2 transfer learning",
            "held_out_accuracy": round(float(accuracy_score(true_labels, predicted_labels)), 4),
            "report": classification_report(
                true_labels,
                predicted_labels,
                labels=list(range(len(classes))),
                target_names=classes,
                output_dict=True,
                zero_division=0,
            ),
            "confusion_matrix": confusion_matrix(
                true_labels, predicted_labels, labels=list(range(len(classes)))
            ).tolist(),
        },
    }
    (MODEL_DIR / "evaluation_results.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
