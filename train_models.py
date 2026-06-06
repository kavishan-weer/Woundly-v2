from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np
import tensorflow as tf
from sklearn.model_selection import train_test_split

from model_lib import (
    CLASSIFICATION_META,
    CLASSIFICATION_MODEL,
    CLASSIFICATION_SIZE,
    MODEL_DIR,
    SEGMENTATION_MODEL,
    SEGMENTATION_SIZE,
    build_classifier,
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
        self.on_epoch_end()

    def __len__(self):
        return int(np.ceil(len(self.image_paths) / self.batch_size))

    def __getitem__(self, index):
        indexes = self.indexes[index * self.batch_size:(index + 1) * self.batch_size]
        paths = [self.image_paths[i] for i in indexes]
        images = np.stack([load_segmentation_image(path) for path in paths])
        masks = np.stack([load_mask(self.mask_dir / path.name) for path in paths])
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
            brightness = np.random.uniform(0.88, 1.12)
            images[index] = np.clip(images[index] * brightness, 0.0, 1.0)
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
            monitor="val_dice_coefficient", mode="max", patience=2, restore_best_weights=True
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


def classification_dataset(dataset, batch_size):
    classification_dir = dataset / "classification"
    classes = sorted(path.name for path in classification_dir.iterdir() if path.is_dir())
    paths, labels = [], []
    for class_index, class_name in enumerate(classes):
        for path in image_files(classification_dir / class_name):
            paths.append(str(path))
            labels.append(class_index)
    train_paths, val_paths, train_labels, val_labels = train_test_split(
        paths, labels, test_size=0.22, random_state=42, stratify=labels
    )

    def decode_image(path, label):
        raw = tf.io.read_file(path)
        image = tf.io.decode_image(raw, channels=3, expand_animations=False)
        image.set_shape([None, None, 3])
        image = tf.image.resize(image, [CLASSIFICATION_SIZE, CLASSIFICATION_SIZE])
        return tf.cast(image, tf.float32) / 255.0, label

    def make(paths_list, labels_list, training):
        ds = tf.data.Dataset.from_tensor_slices((paths_list, labels_list))
        if training:
            ds = ds.shuffle(len(paths_list), seed=42)
        return ds.map(decode_image, num_parallel_calls=tf.data.AUTOTUNE).batch(batch_size).prefetch(tf.data.AUTOTUNE)

    return classes, make(train_paths, train_labels, True), make(val_paths, val_labels, False)


def train_classifier(dataset, epochs, batch_size):
    classes, train_data, val_data = classification_dataset(dataset, batch_size)
    print(f"Classification classes: {classes}")
    model = build_classifier(len(classes))
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=8e-4),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(
            CLASSIFICATION_MODEL, monitor="val_accuracy", mode="max", save_best_only=True
        ),
        tf.keras.callbacks.EarlyStopping(
            monitor="val_accuracy", mode="max", patience=4, restore_best_weights=True
        ),
    ]
    model.fit(train_data, validation_data=val_data, epochs=epochs, callbacks=callbacks, verbose=1)
    model = tf.keras.models.load_model(CLASSIFICATION_MODEL, compile=False)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=8e-4),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    CLASSIFICATION_META.write_text(json.dumps({"classes": classes}, indent=2))
    results = model.evaluate(val_data, verbose=0, return_dict=True)
    print("Classification evaluation:", {key: round(float(value), 4) for key, value in results.items()})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--seg-epochs", type=int, default=14)
    parser.add_argument("--class-epochs", type=int, default=14)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--only", choices=["segmentation", "classification", "both"], default="both")
    args = parser.parse_args()
    MODEL_DIR.mkdir(exist_ok=True)
    tf.keras.utils.set_random_seed(42)
    if args.only in ("segmentation", "both"):
        train_segmenter(args.dataset, args.seg_epochs, args.batch_size)
    if args.only in ("classification", "both"):
        train_classifier(args.dataset, args.class_epochs, args.batch_size)


if __name__ == "__main__":
    main()
