from __future__ import annotations

import base64
import io

import cv2
import numpy as np
from PIL import Image

TISSUE_COLORS = {
    "red_pink_like": (231, 92, 92, 205),
    "yellow_tan_like": (236, 185, 64, 205),
    "dark_like": (53, 61, 69, 215),
    "pale_like": (220, 226, 229, 205),
    "unclassified": (126, 147, 151, 150),
}


def analyze_tissue_colors(mask, image):
    """Estimate color composition inside a segmented wound boundary.

    These HSV groups are explainable visual descriptors. They are not clinical
    tissue labels and must not be presented as a diagnosis.
    """
    total_pixels = int(mask.sum())
    if not total_pixels:
        return _empty_result()

    rgb = np.uint8(np.clip(image, 0.0, 1.0) * 255)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    hue, saturation, value = cv2.split(hsv)

    remaining = mask.copy()
    groups = {}
    groups["dark_like"] = remaining & (value <= 65)
    remaining &= ~groups["dark_like"]
    groups["yellow_tan_like"] = remaining & (hue >= 15) & (hue <= 42) & (saturation >= 35) & (value >= 80)
    remaining &= ~groups["yellow_tan_like"]
    groups["red_pink_like"] = remaining & (((hue <= 14) | (hue >= 165)) & (saturation >= 40) & (value >= 65))
    remaining &= ~groups["red_pink_like"]
    groups["pale_like"] = remaining & (saturation <= 45) & (value >= 150)
    remaining &= ~groups["pale_like"]
    groups["unclassified"] = remaining

    percentages = {
        name: round(float(group.sum() / total_pixels * 100), 1)
        for name, group in groups.items()
    }
    dominant_group = max(percentages, key=percentages.get)
    return {
        "method": "segmented_hsv_color_groups_v1",
        "total_segmented_pixels": total_pixels,
        "percentages": percentages,
        "dominant_group": dominant_group,
        "overlay_data_url": _overlay_data_url(groups),
        "interpretation": (
            "HSV color groups describe pixel appearance inside the U-Net mask. "
            "They are sensitive to lighting and are not validated tissue diagnoses."
        ),
    }


def _overlay_data_url(groups):
    height, width = next(iter(groups.values())).shape
    overlay = np.zeros((height, width, 4), dtype=np.uint8)
    for name, group in groups.items():
        overlay[group] = TISSUE_COLORS[name]
    encoded = io.BytesIO()
    Image.fromarray(overlay, mode="RGBA").save(encoded, format="PNG")
    return "data:image/png;base64," + base64.b64encode(encoded.getvalue()).decode()


def _empty_result():
    return {
        "method": "segmented_hsv_color_groups_v1",
        "total_segmented_pixels": 0,
        "percentages": {name: 0.0 for name in TISSUE_COLORS},
        "dominant_group": "unclassified",
        "overlay_data_url": "",
        "interpretation": "No segmented wound pixels were available for color analysis.",
    }
