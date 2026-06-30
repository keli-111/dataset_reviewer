from __future__ import annotations

import ast
import re
from pathlib import Path

from .models import YoloBox


def parse_yolo_label_file(path: Path) -> tuple[YoloBox, ...]:
    if not path.exists():
        return ()

    boxes: list[YoloBox] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        if len(parts) < 5:
            continue

        try:
            class_id = int(float(parts[0]))
            x_center, y_center, width, height = (float(value) for value in parts[1:5])
        except ValueError:
            continue

        boxes.append(
            YoloBox(
                class_id=class_id,
                x_center=x_center,
                y_center=y_center,
                width=width,
                height=height,
                source_line=line_number,
            )
        )

    return tuple(boxes)


def parse_class_names(dataset_root: Path) -> dict[int, str]:
    yaml_path = dataset_root / "data.yaml"
    if not yaml_path.exists():
        yaml_path = dataset_root / "dataset.yaml"
    if not yaml_path.exists():
        return _parse_classes_file(dataset_root)

    text = yaml_path.read_text(encoding="utf-8", errors="replace")
    names = _parse_inline_names(text)
    if names:
        return names
    names = _parse_block_names(text)
    if names:
        return names
    return _parse_classes_file(dataset_root)


def _parse_classes_file(dataset_root: Path) -> dict[int, str]:
    for filename in ("classes.txt", "classes", "obj.names"):
        path = dataset_root / filename
        if not path.exists() or not path.is_file():
            continue

        result: dict[int, str] = {}
        for index, raw_line in enumerate(_read_text(path).splitlines()):
            name = raw_line.strip()
            if name:
                result[index] = name
        if result:
            return result
    return {}


def _read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _parse_inline_names(text: str) -> dict[int, str]:
    match = re.search(r"(?m)^\s*names\s*:\s*(.+?)\s*$", text)
    if not match:
        return {}

    raw_value = match.group(1).strip()
    if not raw_value or raw_value in {"|", ">"}:
        return {}

    try:
        value = ast.literal_eval(raw_value)
    except (ValueError, SyntaxError):
        return {}

    if isinstance(value, list):
        return {index: str(name) for index, name in enumerate(value)}
    if isinstance(value, dict):
        result: dict[int, str] = {}
        for key, name in value.items():
            try:
                result[int(key)] = str(name)
            except (TypeError, ValueError):
                continue
        return result
    return {}


def _parse_block_names(text: str) -> dict[int, str]:
    lines = text.splitlines()
    result: dict[int, str] = {}
    in_names = False
    next_index = 0

    for raw_line in lines:
        if re.match(r"^\s*names\s*:\s*$", raw_line):
            in_names = True
            continue

        if not in_names:
            continue

        if raw_line and not raw_line.startswith((" ", "\t", "-")):
            break

        stripped = raw_line.strip()
        if not stripped:
            continue

        list_match = re.match(r"^-\s*(.+)$", stripped)
        if list_match:
            result[next_index] = _clean_yaml_scalar(list_match.group(1))
            next_index += 1
            continue

        map_match = re.match(r"^([0-9]+)\s*:\s*(.+)$", stripped)
        if map_match:
            result[int(map_match.group(1))] = _clean_yaml_scalar(map_match.group(2))

    return result


def _clean_yaml_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
