"""Validate and fine-tune YOLOv8n on the specialised traffic dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from ultralytics import YOLO


SCRIPT_DIR = Path(__file__).resolve().parent


def read_data_config(config_path: Path) -> tuple[dict, Path]:
    with config_path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file)

    required = {"path", "train", "val", "names"}
    missing = required - config.keys()
    if missing:
        raise ValueError(f"Dataset YAML is missing required keys: {', '.join(sorted(missing))}")

    dataset_root = (config_path.parent / config["path"]).resolve()
    return config, dataset_root


def image_label_path(image_path: Path, images_dir: Path, labels_dir: Path) -> Path:
    relative = image_path.relative_to(images_dir).with_suffix(".txt")
    return labels_dir / relative


def validate_split(dataset_root: Path, split: str, max_class_id: int) -> int:
    images_dir = dataset_root / "images" / split
    labels_dir = dataset_root / "labels" / split
    if not images_dir.is_dir() or not labels_dir.is_dir():
        raise FileNotFoundError(
            f"Expected both '{images_dir}' and '{labels_dir}'. "
            "Create the standard YOLO images/<split> and labels/<split> folders."
        )

    images = [
        path
        for extension in ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.webp")
        for path in images_dir.rglob(extension)
    ]
    if not images:
        raise ValueError(f"No images found in '{images_dir}'.")

    for image_path in images:
        label_path = image_label_path(image_path, images_dir, labels_dir)
        if not label_path.exists():
            # Unlabelled images are valid negatives in YOLO.
            continue
        for line_number, row in enumerate(label_path.read_text(encoding="utf-8").splitlines(), start=1):
            if not row.strip():
                continue
            fields = row.split()
            if len(fields) != 5:
                raise ValueError(f"{label_path}:{line_number} must contain exactly 5 values.")
            class_id = int(fields[0])
            coordinates = [float(value) for value in fields[1:]]
            if not 0 <= class_id <= max_class_id:
                raise ValueError(f"{label_path}:{line_number} has invalid class ID {class_id}.")
            if not all(0.0 <= value <= 1.0 for value in coordinates):
                raise ValueError(f"{label_path}:{line_number} has a coordinate outside 0..1.")
    return len(images)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune YOLOv8n for specialised traffic objects")
    parser.add_argument("--data", default="traffic_specialized.yaml", help="Dataset YAML path")
    parser.add_argument("--model", default="../yolov8n.pt", help="Pretrained YOLOv8 weights")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=960, help="Use 960 for small road users; lower if memory is limited")
    parser.add_argument("--batch", type=int, default=-1, help="-1 selects an automatically sized batch")
    parser.add_argument("--device", default=None, help="For example: 0 for first GPU, or cpu")
    parser.add_argument("--project", default="../runs/traffic_specialized")
    parser.add_argument("--name", default="yolov8n")
    args = parser.parse_args()

    config_path = (SCRIPT_DIR / args.data).resolve()
    model_path = (SCRIPT_DIR / args.model).resolve()
    if not model_path.exists():
        raise FileNotFoundError(f"Pretrained model not found: {model_path}")

    config, dataset_root = read_data_config(config_path)
    class_count = len(config["names"])
    train_count = validate_split(dataset_root, "train", class_count - 1)
    val_count = validate_split(dataset_root, "val", class_count - 1)
    print(f"Dataset validated: {train_count} training images, {val_count} validation images, {class_count} classes.")

    model = YOLO(str(model_path))
    train_options = {
        "data": str(config_path),
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "project": str((SCRIPT_DIR / args.project).resolve()),
        "name": args.name,
        "pretrained": True,
        "patience": 25,
        "seed": 42,
    }
    if args.device is not None:
        train_options["device"] = args.device
    model.train(**train_options)


if __name__ == "__main__":
    main()
