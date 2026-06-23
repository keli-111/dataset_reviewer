from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .models import DatasetItem


def export_relabel_dataset(
    items: Iterable[DatasetItem],
    selected_indices: Iterable[int],
    output_root: Path,
    *,
    clear_labels: bool,
) -> int:
    item_list = list(items)
    selected = _valid_indices(selected_indices, len(item_list))
    records = _copy_group(item_list, selected, output_root, clear_labels=clear_labels)
    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "clear_labels": clear_labels,
        "count": len(records),
        "items": records,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "review_selection.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return len(records)


def export_split_dataset(
    items: Iterable[DatasetItem],
    *,
    relabel_indices: Iterable[int],
    delete_indices: Iterable[int],
    output_root: Path,
    clear_relabel_labels: bool,
    include_qualified: bool = True,
) -> dict[str, int]:
    output_root = output_root.expanduser().resolve()
    item_list = list(items)
    relabel = _valid_indices(relabel_indices, len(item_list))
    delete = _valid_indices(delete_indices, len(item_list)) - relabel
    qualified = set(range(len(item_list))) - relabel - delete if include_qualified else set()

    records = {
        "relabel": _copy_group(item_list, relabel, output_root / "relabel", clear_labels=clear_relabel_labels),
        "delete": _copy_group(item_list, delete, output_root / "delete", clear_labels=False),
        "qualified": _copy_group(item_list, qualified, output_root / "qualified", clear_labels=False),
    }
    counts = {name: len(group_records) for name, group_records in records.items()}

    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "clear_relabel_labels": clear_relabel_labels,
        "counts": counts,
        "groups": records,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "review_split_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return counts


def _valid_indices(indices: Iterable[int], item_count: int) -> set[int]:
    return {int(index) for index in indices if 0 <= int(index) < item_count}


def _copy_group(
    items: list[DatasetItem],
    indices: set[int],
    group_root: Path,
    *,
    clear_labels: bool,
) -> list[dict[str, object]]:
    images_root = group_root / "images"
    labels_root = group_root / "labels"
    images_root.mkdir(parents=True, exist_ok=True)
    labels_root.mkdir(parents=True, exist_ok=True)

    records = []
    for index in sorted(indices):
        item = items[index]
        target_image = images_root / item.relative_image_path
        target_label = labels_root / item.relative_label_path
        target_image.parent.mkdir(parents=True, exist_ok=True)
        target_label.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(item.image_path, target_image)
        if clear_labels:
            target_label.write_text("", encoding="utf-8")
        elif item.label_path and item.label_path.exists():
            shutil.copy2(item.label_path, target_label)
        else:
            target_label.write_text("", encoding="utf-8")

        records.append(
            {
                "index": index,
                "source_image": str(item.image_path),
                "source_label": str(item.label_path) if item.label_path else None,
                "output_image": str(target_image),
                "output_label": str(target_label),
                "box_count": item.label_count,
            }
        )
    return records


def save_selection_state(
    path: Path,
    relabel_indices: Iterable[int],
    delete_indices: Iterable[int] | int | None = None,
    current_index: int | None = None,
    items: Iterable[DatasetItem] | None = None,
) -> None:
    if isinstance(delete_indices, int) and current_index is None:
        current_index = delete_indices
        delete_indices = set()
    if delete_indices is None:
        delete_indices = set()
    if current_index is None:
        current_index = 0

    item_list = list(items) if items is not None else None
    relabel_set = set(relabel_indices)
    delete_set = set(delete_indices)
    payload = {
        "current_index": current_index,
        "relabel_indices": sorted(relabel_set),
        "delete_indices": sorted(delete_set),
    }
    if item_list is not None:
        payload["current_path"] = _index_to_path(item_list, current_index)
        payload["relabel_paths"] = _indices_to_paths(item_list, relabel_set)
        payload["delete_paths"] = _indices_to_paths(item_list, delete_set)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_selection_state(path: Path, items: Iterable[DatasetItem] | None = None) -> tuple[set[int], set[int], int]:
    if not path.exists():
        return set(), set(), 0

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set(), set(), 0

    item_list = list(items) if items is not None else None
    if item_list is not None and ("relabel_paths" in payload or "delete_paths" in payload):
        path_to_index = {item.relative_image_path.as_posix(): index for index, item in enumerate(item_list)}
        relabel = {path_to_index[value] for value in payload.get("relabel_paths", []) if value in path_to_index}
        delete = {path_to_index[value] for value in payload.get("delete_paths", []) if value in path_to_index} - relabel
        current_path = payload.get("current_path")
        current_index = path_to_index.get(current_path, int(payload.get("current_index", 0)))
    else:
        relabel_values = payload.get("relabel_indices", payload.get("selected_indices", []))
        delete_values = payload.get("delete_indices", [])
        relabel = {int(value) for value in relabel_values}
        delete = {int(value) for value in delete_values} - relabel
        current_index = int(payload.get("current_index", 0))
    return relabel, delete, current_index


def _indices_to_paths(items: list[DatasetItem], indices: set[int]) -> list[str]:
    return [
        items[index].relative_image_path.as_posix()
        for index in sorted(indices)
        if 0 <= index < len(items)
    ]


def _index_to_path(items: list[DatasetItem], index: int) -> str | None:
    if 0 <= index < len(items):
        return items[index].relative_image_path.as_posix()
    return None
