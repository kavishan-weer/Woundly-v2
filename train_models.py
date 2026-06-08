from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import cv2
import numpy as np
import tensorflow as tf
from PIL import Image
from sklearn.model_selection import train_test_split

from model_lib import (
    MODEL_DIR,
    SEGMENTATION_MODEL,
    SEGMENTATION_SIZE,
    build_unet,
    dice_coefficient,
    load_mask,
    load_rgb_image,
    load_segmentation_image,
    segmentation_loss,
)

DEFAULT_DATASET = Path("/Users/kavishanwee/Desktop/Wound Detection/datasets")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def image_files(directory):
    return sorted(
        path for path in Path(directory).iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


class SegmentationSequence(tf.keras.utils.Sequence):
    def __init__(self, image_paths, mask_dir, batch_size=16, shuffle=True, augment=False):
        super().__init__()
        self.image_paths = list(image_paths)
        self.mask_dir = Path(mask_dir)
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.augment = augment
        self.indexes = np.arange(len(self.image_paths))

        self.cached_images = []
        self.cached_masks = []
        print(f"Caching {len(self.image_paths)} images and masks in memory...")
        for path in self.image_paths:
            img = Image.open(path).convert("RGB").resize((SEGMENTATION_SIZE, SEGMENTATION_SIZE), Image.Resampling.BILINEAR)
            self.cached_images.append(np.asarray(img, dtype=np.uint8))
            
            m_path = self.mask_dir / path.name
            mask = Image.open(m_path).convert("L").resize((SEGMENTATION_SIZE, SEGMENTATION_SIZE), Image.Resampling.NEAREST)
            self.cached_masks.append(np.asarray(mask, dtype=np.uint8))
            
        self.cached_images = np.array(self.cached_images, dtype=np.uint8)
        self.cached_masks = np.expand_dims(np.array(self.cached_masks, dtype=np.uint8), axis=-1)
        print("Caching complete!")
        self.on_epoch_end()

    def __len__(self):
        return int(np.ceil(len(self.image_paths) / self.batch_size))

    def __getitem__(self, index):
        indexes = self.indexes[index * self.batch_size:(index + 1) * self.batch_size]
        images = self.cached_images[indexes].astype(np.float32) / 255.0
        masks = (self.cached_masks[indexes] > 127).astype(np.float32)

        images = np.stack([cv2.GaussianBlur(img, (3, 3), 0) for img in images])

        if self.augment:
            images, masks = self._augment_batch(images, masks)
        return images, masks

    def on_epoch_end(self):
        if self.shuffle:
            np.random.shuffle(self.indexes)

    @staticmethod
    def _augment_batch(images, masks):
        for index in range(len(images)):
            if np.random.random() < 0.5:
                images[index] = np.flip(images[index], axis=1)
                masks[index] = np.flip(masks[index], axis=1)
            if np.random.random() < 0.35:
                images[index] = np.flip(images[index], axis=0)
                masks[index] = np.flip(masks[index], axis=0)
            rotations = np.random.randint(0, 4)
            if rotations:
                images[index] = np.rot90(images[index], rotations)
                masks[index] = np.rot90(masks[index], rotations)
            
            if np.random.random() < 0.6:
                img_uint8 = np.uint8(images[index] * 255)
                hsv = cv2.cvtColor(img_uint8, cv2.COLOR_RGB2HSV).astype(np.float32)
                hue_shift = np.random.uniform(-20, 20)
                hsv[..., 0] = (hsv[..., 0] + hue_shift) % 180
                sat_scale = np.random.uniform(0.75, 1.25)
                hsv[..., 1] = np.clip(hsv[..., 1] * sat_scale, 0, 255)
                val_scale = np.random.uniform(0.85, 1.15)
                hsv[..., 2] = np.clip(hsv[..., 2] * val_scale, 0, 255)
                img_rgb = cv2.cvtColor(np.uint8(hsv), cv2.COLOR_HSV2RGB)
                images[index] = img_rgb.astype(np.float32) / 255.0
            else:
                brightness = np.random.uniform(0.88, 1.12)
                images[index] = np.clip(images[index] * brightness, 0.0, 1.0)

            if np.random.random() < 0.3:
                contrast_factor = np.random.uniform(0.8, 1.2)
                mean = images[index].mean(axis=(0, 1), keepdims=True)
                images[index] = np.clip((images[index] - mean) * contrast_factor + mean, 0.0, 1.0)
        return images, masks


def train_segmenter(dataset, epochs, batch_size):
    train_image_dir = dataset / "segmentation/images/train_images"
    train_mask_dir = dataset / "segmentation/masks/train_masks"
    test_image_dir = dataset / "segmentation/images/test_images"
    test_mask_dir = dataset / "segmentation/masks/test_masks"
    train_paths = image_files(train_image_dir)
    test_paths = image_files(test_image_dir)
    print(f"Segmentation pairs: {len(train_paths)} train, {len(test_paths)} test")

    model = build_unet()
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss=segmentation_loss,
        metrics=[dice_coefficient, tf.keras.metrics.BinaryIoU(target_class_ids=[1])],
    )
    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(
            SEGMENTATION_MODEL, monitor="val_dice_coefficient", mode="max", save_best_only=True
        ),
        tf.keras.callbacks.EarlyStopping(
            monitor="val_dice_coefficient", mode="max", patience=8, restore_best_weights=True
        ),
    ]
    model.fit(
        SegmentationSequence(train_paths, train_mask_dir, batch_size=batch_size, augment=True),
        validation_data=SegmentationSequence(test_paths, test_mask_dir, batch_size=batch_size, shuffle=False),
        epochs=epochs,
        callbacks=callbacks,
        verbose=1,
    )
    model = tf.keras.models.load_model(SEGMENTATION_MODEL, compile=False)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss=segmentation_loss,
        metrics=[dice_coefficient, tf.keras.metrics.BinaryIoU(target_class_ids=[1])],
    )
    results = model.evaluate(
        SegmentationSequence(test_paths, test_mask_dir, batch_size=batch_size, shuffle=False),
        verbose=0,
        return_dict=True,
    )
    print("Segmentation evaluation:", {key: round(float(value), 4) for key, value in results.items()})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--seg-epochs", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()
    MODEL_DIR.mkdir(exist_ok=True)
    tf.keras.utils.set_random_seed(42)
    train_segmenter(args.dataset, args.seg_epochs, args.batch_size)


if __name__ == "__main__":
    main()
