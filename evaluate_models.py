from __future__ import annotations

import json
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent / "models"


def main():
    segmentation = json.loads((MODEL_DIR / "segmentation_meta.json").read_text())
    results = {
        "segmentation": {
            "calibrated_threshold": segmentation["threshold"],
            "held_out_macro_dice": segmentation["validation_macro_dice"],
        }
    }
    (MODEL_DIR / "evaluation_results.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
