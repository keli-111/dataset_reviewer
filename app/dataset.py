from __future__ import annotations

from pathlib import Path

from .models import DatasetItem
from .yolo import parse_yolo_label_file


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
IMAGE_DIR_NAMES = ("images", "JPEGImages", "imgs", "image")
LABEL_DIR_NAMES = ("labels", "yolo_labels", "YOLOLabels", "Annotations", "labels_yolo")
EXCLUDED_IMAGE_DIR_NAMES = {
    "visualization",
    "visualizations",
    "vis",
    "preview",
    "previews",
    "render",
    "renders",
    "result",
    "results",
}


def scan_yolo_dataset(dataset_root: Path) -> list[DatasetItem]:
    dataset_root = dataset_root.expanduser().resolve()
    images_root = _first_existing_child(dataset_root, IMAGE_DIR_NAMES) or dataset_root
    labels_root = _first_existing_child(dataset_root, LABEL_DIR_NAMES) or dataset_root

    items: list[DatasetItem] = []
    for image_path in sorted(_iter_images(images_root), key=lambda path: path.as_posix().lower()):
        relative_image_path = image_path.relative_to(images_root)
        relative_label_path = relative_image_path.with_suffix(".txt")
        label_path = labels_root / relative_label_path
        actual_label_path = label_path if label_path.exists() else None
        boxes = parse_yolo_label_file(actual_label_path) if actual_label_path else ()

        items.append(
            DatasetItem(
                image_path=image_path,
                label_path=actual_label_path,
                relative_image_path=relative_image_path,
                relative_label_path=relative_label_path,
                boxes=boxes,
            )
        )

    return items


def _first_existing_child(root: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        path = root / name
        if path.exists() and path.is_dir():
            return path
    return None


def _iter_images(images_root: Path):
    for path in images_root.rglob("*"):
        if any(part.lower() in EXCLUDED_IMAGE_DIR_NAMES for part in path.relative_to(images_root).parts[:-1]):
            continue
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path
