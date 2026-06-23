from __future__ import annotations

import sys
from hashlib import sha1
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .dataset import scan_yolo_dataset
from .exporter import export_relabel_dataset, load_selection_state, save_selection_state
from .image_viewer import ImageViewer
from .models import DatasetItem
from .yolo import parse_class_names


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("YOLO Dataset Reviewer")
        self.resize(1180, 760)

        self.dataset_root: Path | None = None
        self.items: list[DatasetItem] = []
        self.selected_indices: set[int] = set()
        self.delete_indices: set[int] = set()
        self.class_names: dict[int, str] = {}
        self.current_index = 0

        self.viewer = ImageViewer()
        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self.go_to_index)

        self.status_label = QLabel("未打开数据集")
        self.file_label = QLabel("-")
        self.detail_label = QLabel("-")
        self.detail_label.setWordWrap(True)
        self.selected_label = QLabel("待重标：0")
        self.clear_labels_checkbox = QCheckBox("导出时清空标签")

        self.open_button = QPushButton("打开数据集")
        self.previous_button = QPushButton("上一张")
        self.next_button = QPushButton("下一张")
        self.toggle_button = QPushButton("加入待重标")
        self.export_button = QPushButton("导出待重标")

        self.open_button.clicked.connect(self.open_dataset)
        self.previous_button.clicked.connect(self.previous_item)
        self.next_button.clicked.connect(self.next_item)
        self.toggle_button.clicked.connect(self.toggle_selected)
        self.export_button.clicked.connect(self.export_selected)

        self._build_layout()
        self._build_actions()
        self._update_controls()

    def _build_layout(self) -> None:
        side_panel = QWidget()
        side_layout = QVBoxLayout(side_panel)
        side_layout.addWidget(self.status_label)
        side_layout.addWidget(self.file_label)
        side_layout.addWidget(self.detail_label)
        side_layout.addWidget(self.selected_label)
        side_layout.addSpacing(8)
        side_layout.addWidget(self.open_button)
        side_layout.addWidget(self.toggle_button)
        side_layout.addWidget(self.clear_labels_checkbox)
        side_layout.addWidget(self.export_button)
        side_layout.addStretch(1)

        nav = QWidget()
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.addWidget(self.previous_button)
        nav_layout.addWidget(self.next_button)
        side_layout.addWidget(nav)

        splitter = QSplitter()
        splitter.addWidget(self.list_widget)
        splitter.addWidget(self.viewer)
        splitter.addWidget(side_panel)
        splitter.setSizes([260, 680, 240])
        self.setCentralWidget(splitter)

    def _build_actions(self) -> None:
        open_action = QAction("打开数据集", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.open_dataset)
        self.addAction(open_action)

        export_action = QAction("导出", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self.export_selected)
        self.addAction(export_action)

        for shortcut, handler in [
            ("A", self.previous_item),
            ("Left", self.previous_item),
            ("D", self.next_item),
            ("Right", self.next_item),
            ("Space", self.toggle_selected),
        ]:
            action = QAction(shortcut, self)
            action.setShortcut(shortcut)
            action.triggered.connect(handler)
            self.addAction(action)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in {Qt.Key_D, Qt.Key_Right}:
            self.next_item()
            return
        if key in {Qt.Key_A, Qt.Key_Left}:
            self.previous_item()
            return
        if key == Qt.Key_Space:
            self.toggle_selected()
            return
        super().keyPressEvent(event)

    def open_dataset(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择 YOLO 数据集目录")
        if not directory:
            return

        dataset_root = Path(directory)
        try:
            items = scan_yolo_dataset(dataset_root)
        except OSError as exc:
            QMessageBox.critical(self, "打开失败", f"无法扫描数据集：\n{exc}")
            return

        if not items:
            QMessageBox.warning(self, "未找到图片", "没有找到 jpg、jpeg、png、bmp 或 webp 图片。")
            return

        self.dataset_root = dataset_root
        self.items = items
        self.class_names = parse_class_names(dataset_root)
        self.selected_indices, self.delete_indices, saved_index = load_selection_state(self._state_path(), self.items)
        self.current_index = min(max(saved_index, 0), len(self.items) - 1)

        self._rebuild_list()
        self.list_widget.setCurrentRow(self.current_index)
        self._show_current()
        self._update_controls()

    def _rebuild_list(self) -> None:
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for index, item in enumerate(self.items):
            prefix = "*" if index in self.selected_indices else " "
            label = f"{prefix} {index + 1:05d}  {item.relative_image_path.as_posix()}  ({item.label_count})"
            self.list_widget.addItem(QListWidgetItem(label))
        self.list_widget.blockSignals(False)

    def _refresh_list_item(self, index: int) -> None:
        item = self.items[index]
        prefix = "*" if index in self.selected_indices else " "
        text = f"{prefix} {index + 1:05d}  {item.relative_image_path.as_posix()}  ({item.label_count})"
        self.list_widget.item(index).setText(text)

    def go_to_index(self, index: int) -> None:
        if 0 <= index < len(self.items):
            self.current_index = index
            self._show_current()
            self._save_state()

    def previous_item(self) -> None:
        if not self.items:
            return
        self.current_index = max(0, self.current_index - 1)
        self.list_widget.setCurrentRow(self.current_index)

    def next_item(self) -> None:
        if not self.items:
            return
        self.current_index = min(len(self.items) - 1, self.current_index + 1)
        self.list_widget.setCurrentRow(self.current_index)

    def toggle_selected(self) -> None:
        if not self.items:
            return
        if self.current_index in self.selected_indices:
            self.selected_indices.remove(self.current_index)
        else:
            self.selected_indices.add(self.current_index)
        self._refresh_list_item(self.current_index)
        self._show_current()
        self._save_state()

    def export_selected(self) -> None:
        if not self.items or not self.selected_indices:
            QMessageBox.information(self, "没有待导出图片", "请先把图片加入待重标。")
            return

        directory = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if not directory:
            return

        try:
            count = export_relabel_dataset(
                self.items,
                self.selected_indices,
                Path(directory),
                clear_labels=self.clear_labels_checkbox.isChecked(),
            )
        except OSError as exc:
            QMessageBox.critical(self, "导出失败", f"无法导出数据集：\n{exc}")
            return

        QMessageBox.information(self, "导出完成", f"已导出 {count} 张图片和对应标签。")

    def _show_current(self) -> None:
        if not self.items:
            self.viewer.clear()
            self.status_label.setText("未打开数据集")
            self.file_label.setText("-")
            self.detail_label.setText("-")
            self.selected_label.setText("待重标：0")
            return

        item = self.items[self.current_index]
        self.viewer.set_image(str(item.image_path), item.boxes, self.class_names)

        selected_flag = "已加入待重标" if self.current_index in self.selected_indices else "未选择"
        self.status_label.setText(f"{self.current_index + 1} / {len(self.items)}  |  {selected_flag}")
        self.file_label.setText(item.relative_image_path.as_posix())
        label_state = str(item.label_path) if item.label_path else "无对应 txt"
        class_summary = self._class_summary(item)
        self.detail_label.setText(f"目标框：{item.label_count}\n{class_summary}\n标签：{label_state}")
        self.selected_label.setText(f"待重标：{len(self.selected_indices)}")
        self.toggle_button.setText("取消待重标" if self.current_index in self.selected_indices else "加入待重标")

    def _class_summary(self, item: DatasetItem) -> str:
        if not item.boxes:
            return "类别：无"
        counts: dict[int, int] = {}
        for box in item.boxes:
            counts[box.class_id] = counts.get(box.class_id, 0) + 1
        parts = []
        for class_id, count in sorted(counts.items()):
            name = self.class_names.get(class_id, f"class {class_id}")
            parts.append(f"{name}:{count}")
        return "类别：" + ", ".join(parts)

    def _state_path(self) -> Path:
        assert self.dataset_root is not None
        key = sha1(str(self.dataset_root.resolve()).encode("utf-8")).hexdigest()
        state_root = Path.home() / ".yolo_dataset_reviewer" / "states"
        state_root.mkdir(parents=True, exist_ok=True)
        return state_root / f"{key}.json"

    def _save_state(self) -> None:
        if self.dataset_root is None:
            return
        try:
            save_selection_state(
                self._state_path(),
                self.selected_indices,
                self.delete_indices,
                self.current_index,
                self.items,
            )
        except OSError:
            pass

    def _update_controls(self) -> None:
        has_items = bool(self.items)
        self.previous_button.setEnabled(has_items)
        self.next_button.setEnabled(has_items)
        self.toggle_button.setEnabled(has_items)
        self.export_button.setEnabled(has_items)


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
