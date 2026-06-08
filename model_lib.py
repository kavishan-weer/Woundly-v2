from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import cv2
import numpy as np
import tensorflow as tf
from PIL import Image
from tensorflow.keras import layers, models

from tissue_analysis import analyze_tissue_colors

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "models"
SEGMENTATION_MODEL = MODEL_DIR / "wound_segmentation_unet.keras"
SUPPLIED_SEGMENTATION_MODEL = ROOT / "my model/unet_wound_segmentation.h5"
SEGMENTATION_INFERENCE_MODEL = (
    SUPPLIED_SEGMENTATION_MODEL if SUPPLIED_SEGMENTATION_MODEL.exists() else SEGMENTATION_MODEL
)
SEGMENTATION_META = MODEL_DIR / "segmentation_meta.json"
SEGMENTATION_SIZE = 128


def dice_coefficient(y_true, y_pred):
    y_true = tf.cast(y_true, tf.float32)
    y_pred = tf.cast(y_pred, tf.float32)
    intersection = tf.reduce_sum(y_true * y_pred, axis=(1, 2, 3))
    denominator = tf.reduce_sum(y_true, axis=(1, 2, 3)) + tf.reduce_sum(
        y_pred, axis=(1, 2, 3)
    )
    return tf.reduce_mean((2.0 * intersection + 1.0) / (denominator + 1.0))


def dice_loss(y_true, y_pred):
    return 1.0 - dice_coefficient(y_true, y_pred)


def tversky_loss(y_true, y_pred, alpha=0.7, beta=0.3):
    y_true = tf.cast(y_true, tf.float32)
    y_pred = tf.cast(y_pred, tf.float32)
    true_positive = tf.reduce_sum(y_true * y_pred, axis=(1, 2, 3))
    false_negative = tf.reduce_sum(y_true * (1.0 - y_pred), axis=(1, 2, 3))
    false_positive = tf.reduce_sum((1.0 - y_true) * y_pred, axis=(1, 2, 3))
    score = (true_positive + 1.0) / (
        true_positive + alpha * false_negative + beta * false_positive + 1.0
    )
    return 1.0 - tf.reduce_mean(score)


def segmentation_loss(y_true, y_pred):
    focal = tf.keras.losses.binary_focal_crossentropy(
        y_true, y_pred, apply_class_balancing=True, alpha=0.75, gamma=2.0
    )
    return 0.75 * tversky_loss(y_true, y_pred) + 0.25 * tf.reduce_mean(focal)


def build_unet(input_shape=(SEGMENTATION_SIZE, SEGMENTATION_SIZE, 3)):
    inputs = layers.Input(shape=input_shape)

    def conv_block(x, filters):
        x = layers.Conv2D(filters, 3, padding="same", activation="relu")(x)
        x = layers.BatchNormalization()(x)
        x = layers.Conv2D(filters, 3, padding="same", activation="relu")(x)
        return x

    c1 = conv_block(inputs, 32)
    p1 = layers.MaxPooling2D()(c1)
    c2 = conv_block(p1, 64)
    p2 = layers.MaxPooling2D()(c2)
    c3 = conv_block(p2, 128)
    p3 = layers.MaxPooling2D()(c3)

    bridge = conv_block(p3, 256)
    bridge = layers.Dropout(0.15)(bridge)

    u3 = layers.UpSampling2D()(bridge)
    u3 = layers.Concatenate()([u3, c3])
    c4 = conv_block(u3, 128)
    u2 = layers.UpSampling2D()(c4)
    u2 = layers.Concatenate()([u2, c2])
    c5 = conv_block(u2, 64)
    u1 = layers.UpSampling2D()(c5)
    u1 = layers.Concatenate()([u1, c1])
    c6 = conv_block(u1, 32)
    outputs = layers.Conv2D(1, 1, activation="sigmoid")(c6)
    return models.Model(inputs, outputs, name="compact_wound_unet")





def load_rgb_image(path_or_bytes, size):
    if isinstance(path_or_bytes, (str, Path)):
        image = Image.open(path_or_bytes)
    else:
        image = Image.open(io.BytesIO(path_or_bytes))
    image = image.convert("RGB").resize((size, size), Image.Resampling.BILINEAR)
    return np.asarray(image, dtype=np.float32) / 255.0


def load_segmentation_image(path_or_bytes):
    image = load_rgb_image(path_or_bytes, SEGMENTATION_SIZE)
    return cv2.GaussianBlur(image, (3, 3), 0)


def load_mask(path, size=SEGMENTATION_SIZE):
    mask = Image.open(path).convert("L").resize((size, size), Image.Resampling.NEAREST)
    return (np.asarray(mask, dtype=np.float32) > 127).astype(np.float32)[..., None]


class WoundAnalyzer:
    def __init__(self):
        if not SEGMENTATION_INFERENCE_MODEL.exists():
            raise FileNotFoundError("Train models first with: python train_models.py")
        self.segmenter = tf.keras.models.load_model(SEGMENTATION_INFERENCE_MODEL, compile=False)
        self.mask_threshold = 0.5
        if SEGMENTATION_META.exists():
            self.mask_threshold = json.loads(SEGMENTATION_META.read_text()).get("threshold", 0.5)

    def analyze(self, image_bytes):
        seg_image = load_segmentation_image(image_bytes)
        color_image = load_rgb_image(image_bytes, SEGMENTATION_SIZE)
        probabilities = self.segmenter.predict(seg_image[None, ...], verbose=0)[0, ..., 0]
        binary_mask = probabilities >= self.mask_threshold
        binary_mask = self._clean_mask(binary_mask)

        return {
            "segmentation": self._segmentation_result(binary_mask, probabilities),
            "features": self._feature_result(binary_mask, color_image),
            "tissue_color_analysis": analyze_tissue_colors(binary_mask, color_image),
            "photo_quality": self._photo_quality(seg_image),
            "model": {
                "segmentation": "supplied_224px_wound_unet",
                "mask_threshold": self.mask_threshold,
            },
        }

    @staticmethod
    def _clean_mask(mask):
        mask_uint8 = mask.astype(np.uint8) * 255
        kernel = np.ones((3, 3), np.uint8)
        mask_uint8 = cv2.morphologyEx(mask_uint8, cv2.MORPH_OPEN, kernel)
        mask_uint8 = cv2.morphologyEx(mask_uint8, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return mask_uint8.astype(bool)
        largest_area = max(cv2.contourArea(contour) for contour in contours)
        minimum_area = max(12.0, largest_area * 0.04)
        clean = np.zeros_like(mask_uint8)
        meaningful = [contour for contour in contours if cv2.contourArea(contour) >= minimum_area]
        cv2.drawContours(clean, meaningful, -1, 255, thickness=cv2.FILLED)
        return clean.astype(bool)

    @staticmethod
    def _segmentation_result(mask, probabilities):
        mask_uint8 = mask.astype(np.uint8) * 255
        contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        perimeter = sum(cv2.arcLength(contour, True) for contour in contours)
        pixel_area = int(mask.sum())
        coverage = round(pixel_area / mask.size * 100, 2)
        encoded = io.BytesIO()
        Image.fromarray(mask_uint8, mode="L").save(encoded, format="PNG")
        mask_data_url = "data:image/png;base64," + base64.b64encode(encoded.getvalue()).decode()
        return {
            "mask_data_url": mask_data_url,
            "pixel_area": pixel_area,
            "perimeter_pixels": round(float(perimeter), 1),
            "coverage_percent": coverage,
            "mean_probability": round(float(probabilities.mean()), 4),
        }

    @staticmethod
    def _feature_result(mask, image):
        mask_uint8 = mask.astype(np.uint8) * 255
        contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        pixel_area = int(mask.sum())
        perimeter = sum(cv2.arcLength(contour, True) for contour in contours)
        circularity = 0.0
        aspect_ratio = 0.0
        if contours and pixel_area:
            x, y, width, height = cv2.boundingRect(np.concatenate(contours))
            aspect_ratio = width / height if height else 0.0
            circularity = 4.0 * np.pi * pixel_area / (perimeter * perimeter) if perimeter else 0.0
        mean_rgb = image[mask].mean(axis=0) * 255 if pixel_area else np.zeros(3)
        return {
            "shape_circularity": round(float(min(circularity, 1.0)), 3),
            "bounding_box_aspect_ratio": round(float(aspect_ratio), 3),
            "mean_wound_rgb": [round(float(value), 1) for value in mean_rgb],
        }

    @staticmethod
    def _photo_quality(image):
        image_uint8 = np.uint8(np.clip(image, 0.0, 1.0) * 255)
        gray = cv2.cvtColor(image_uint8, cv2.COLOR_RGB2GRAY)
        brightness = float(gray.mean())
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        notes = []
        if brightness < 55:
            notes.append("Image is dark; use brighter, even lighting next time.")
        elif brightness > 215:
            notes.append("Image is very bright; reduce glare next time.")
        if sharpness < 45:
            notes.append("Image may be blurry; hold the camera steady and refocus.")
        return {
            "brightness": round(brightness, 1),
            "sharpness": round(sharpness, 1),
            "status": "review" if notes else "good",
            "notes": notes,
        }
