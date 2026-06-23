from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class YoloBox:
    class_id: int
    x_center: float
    y_center: float
    width: float
    height: float
    source_line: int


@dataclass(frozen=True)
class DatasetItem:
    image_path: Path
    label_path: Path | None
    relative_image_path: Path
    relative_label_path: Path
    boxes: tuple[YoloBox, ...]

    @property
    def file_name(self) -> str:
        return self.image_path.name

    @property
    def label_count(self) -> int:
        return len(self.boxes)

