from __future__ import annotations

import hashlib
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageFont, ImageTk

from .dataset import scan_yolo_dataset
from .exporter import export_split_dataset, load_selection_state, save_selection_state
from .models import DatasetItem, YoloBox
from .yolo import parse_class_names


BOX_COLORS = [
    "#e53935",
    "#1e88e5",
    "#43a047",
    "#fb8c00",
    "#8e24aa",
    "#00acc1",
    "#fdd835",
    "#6d4c41",
]


class TkMainWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("YOLO Dataset Reviewer")
        self.root.geometry("1180x760")
        self.root.minsize(900, 560)

        self.dataset_root: Path | None = None
        self.items: list[DatasetItem] = []
        self.relabel_indices: set[int] = set()
        self.delete_indices: set[int] = set()
        self.class_names: dict[int, str] = {}
        self.current_index = 0
        self.current_photo: ImageTk.PhotoImage | None = None
        self.current_display_image: Image.Image | None = None

        self.status_var = tk.StringVar(value="未打开数据集")
        self.group_var = tk.StringVar(value="当前分组：-")
        self.file_var = tk.StringVar(value="-")
        self.detail_var = tk.StringVar(value="-")
        self.selected_var = tk.StringVar(value="待重标：0 | 删除：0 | 合格：0")
        self.clear_labels_var = tk.BooleanVar(value=False)

        self._build_layout()
        self._bind_shortcuts()
        self._update_controls()

    def _build_layout(self) -> None:
        root_frame = ttk.Frame(self.root, padding=8)
        root_frame.pack(fill=tk.BOTH, expand=True)

        self.listbox = tk.Listbox(root_frame, width=28, activestyle="dotbox")
        self.listbox.pack(side=tk.LEFT, fill=tk.Y)
        self.listbox.bind("<<ListboxSelect>>", self._on_list_select)

        center = ttk.Frame(root_frame, padding=(8, 0))
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(center, bg="#202124", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda _event: self._show_current())

        side = ttk.Frame(root_frame, width=190)
        side.pack(side=tk.RIGHT, fill=tk.Y)
        side.pack_propagate(False)

        ttk.Label(side, textvariable=self.status_var, wraplength=175).pack(anchor=tk.W, pady=(0, 6))
        self.group_label = tk.Label(
            side,
            textvariable=self.group_var,
            font=("Microsoft YaHei", 15, "bold"),
            fg="#1f2933",
            bg="#d7dce2",
            padx=8,
            pady=7,
            anchor=tk.CENTER,
        )
        self.group_label.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(side, textvariable=self.file_var, wraplength=175).pack(anchor=tk.W, pady=(0, 8))
        ttk.Label(side, textvariable=self.detail_var, wraplength=175, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 8))
        ttk.Label(side, textvariable=self.selected_var).pack(anchor=tk.W, pady=(0, 12))

        self.open_button = ttk.Button(side, text="打开 (Ctrl+O)", command=self.open_dataset, takefocus=False)
        self.toggle_button = ttk.Button(side, text="待重标 (Space)", command=self.toggle_relabel, takefocus=False)
        self.delete_button = ttk.Button(side, text="删除 (W/Delete)", command=self.toggle_delete, takefocus=False)
        self.export_button = ttk.Button(side, text="导出 (Ctrl+E)", command=self.export_split, takefocus=False)
        self.previous_button = ttk.Button(side, text="上一张 (A/←)", command=self.previous_item, takefocus=False)
        self.next_button = ttk.Button(side, text="下一张 (D/→)", command=self.next_item, takefocus=False)

        self.open_button.pack(fill=tk.X, pady=3)
        self.toggle_button.pack(fill=tk.X, pady=3)
        self.delete_button.pack(fill=tk.X, pady=3)
        ttk.Checkbutton(side, text="导出时清空标签", variable=self.clear_labels_var).pack(anchor=tk.W, pady=6)
        self.export_button.pack(fill=tk.X, pady=3)

        ttk.Separator(side).pack(fill=tk.X, pady=12)
        self.previous_button.pack(fill=tk.X, pady=3)
        self.next_button.pack(fill=tk.X, pady=3)

    def _bind_shortcuts(self) -> None:
        self.root.bind_all("<Control-o>", lambda _event: self._run_shortcut(self.open_dataset))
        self.root.bind_all("<Control-e>", lambda _event: self._run_shortcut(self.export_split))
        self.root.bind_all("<Left>", lambda _event: self._run_shortcut(self.previous_item))
        self.root.bind_all("<Right>", lambda _event: self._run_shortcut(self.next_item))
        self.root.bind_all("a", lambda _event: self._run_shortcut(self.previous_item))
        self.root.bind_all("A", lambda _event: self._run_shortcut(self.previous_item))
        self.root.bind_all("d", lambda _event: self._run_shortcut(self.next_item))
        self.root.bind_all("D", lambda _event: self._run_shortcut(self.next_item))
        self.root.bind_all("<space>", lambda _event: self._run_shortcut(self.toggle_relabel))
        self.root.bind_all("<Delete>", lambda _event: self._run_shortcut(self.toggle_delete))
        self.root.bind_all("w", lambda _event: self._run_shortcut(self.toggle_delete))
        self.root.bind_all("W", lambda _event: self._run_shortcut(self.toggle_delete))

    def _run_shortcut(self, action) -> str:
        action()
        self.canvas.focus_set()
        return "break"

    def open_dataset(self) -> None:
        directory = filedialog.askdirectory(title="选择 YOLO 数据集目录")
        if not directory:
            return

        dataset_root = Path(directory)
        try:
            items = scan_yolo_dataset(dataset_root)
        except OSError as exc:
            messagebox.showerror("打开失败", f"无法扫描数据集：\n{exc}")
            return

        if not items:
            messagebox.showwarning("未找到图片", "没有找到 jpg、jpeg、png、bmp 或 webp 图片。")
            return

        self.dataset_root = dataset_root
        self.items = items
        self.class_names = parse_class_names(dataset_root)
        self.relabel_indices, self.delete_indices, saved_index = load_selection_state(self._state_path(), self.items)
        self.current_index = min(max(saved_index, 0), len(self.items) - 1)

        self._rebuild_list()
        self._select_current_list_row()
        self._show_current()
        self._update_controls()
        self.canvas.focus_set()

    def previous_item(self) -> None:
        if not self.items:
            return
        self.current_index = max(0, self.current_index - 1)
        self._select_current_list_row()
        self._show_current()
        self._save_state()

    def next_item(self) -> None:
        if not self.items:
            return
        self.current_index = min(len(self.items) - 1, self.current_index + 1)
        self._select_current_list_row()
        self._show_current()
        self._save_state()

    def toggle_relabel(self) -> None:
        if not self.items:
            return
        if self.current_index in self.relabel_indices:
            self.relabel_indices.remove(self.current_index)
        else:
            self.relabel_indices.add(self.current_index)
            self.delete_indices.discard(self.current_index)
        self._refresh_list_item(self.current_index)
        self._show_current()
        self._save_state()

    def toggle_delete(self) -> None:
        if not self.items:
            return
        if self.current_index in self.delete_indices:
            self.delete_indices.remove(self.current_index)
        else:
            self.delete_indices.add(self.current_index)
            self.relabel_indices.discard(self.current_index)
        self._refresh_list_item(self.current_index)
        self._show_current()
        self._save_state()

    def export_split(self) -> None:
        if not self.items:
            messagebox.showinfo("没有数据集", "请先打开数据集。")
            return

        directory = filedialog.askdirectory(title="选择导出目录")
        if not directory:
            return

        try:
            counts = export_split_dataset(
                self.items,
                relabel_indices=self.relabel_indices,
                delete_indices=self.delete_indices,
                output_root=Path(directory),
                clear_relabel_labels=self.clear_labels_var.get(),
            )
        except OSError as exc:
            messagebox.showerror("导出失败", f"无法导出数据集：\n{exc}")
            return

        messagebox.showinfo(
            "导出完成",
            "已导出三份数据集：\n"
            f"待重标：{counts['relabel']} 张\n"
            f"删除：{counts['delete']} 张\n"
            f"合格：{counts['qualified']} 张",
        )

    def _on_list_select(self, _event) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        index = int(selection[0])
        if 0 <= index < len(self.items) and index != self.current_index:
            self.current_index = index
            self._show_current()
            self._save_state()

    def _rebuild_list(self) -> None:
        self.listbox.delete(0, tk.END)
        for index in range(len(self.items)):
            self.listbox.insert(tk.END, self._list_text(index))

    def _refresh_list_item(self, index: int) -> None:
        self.listbox.delete(index)
        self.listbox.insert(index, self._list_text(index))
        self._select_current_list_row()

    def _list_text(self, index: int) -> str:
        item = self.items[index]
        if index in self.relabel_indices:
            prefix = "R"
        elif index in self.delete_indices:
            prefix = "D"
        else:
            prefix = "Q"
        return f"{prefix} {index + 1:05d}  {item.relative_image_path.as_posix()}  ({item.label_count})"

    def _select_current_list_row(self) -> None:
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(self.current_index)
        self.listbox.activate(self.current_index)
        self.listbox.see(self.current_index)

    def _show_current(self) -> None:
        self.canvas.delete("all")
        if not self.items:
            self.canvas.create_text(
                self.canvas.winfo_width() / 2,
                self.canvas.winfo_height() / 2,
                fill="#d7dce2",
                text="打开数据集后显示图片",
                font=("Microsoft YaHei", 14),
            )
            return

        item = self.items[self.current_index]
        try:
            image = Image.open(item.image_path).convert("RGB")
        except OSError:
            self.canvas.create_text(
                self.canvas.winfo_width() / 2,
                self.canvas.winfo_height() / 2,
                fill="#d7dce2",
                text="图片加载失败",
                font=("Microsoft YaHei", 14),
            )
            return

        display_image = self._draw_display_image(image, item.boxes)
        self.current_display_image = display_image
        self.current_photo = ImageTk.PhotoImage(display_image)
        self.canvas.create_image(
            self.canvas.winfo_width() / 2,
            self.canvas.winfo_height() / 2,
            image=self.current_photo,
            anchor=tk.CENTER,
        )
        self._update_info(item)

    def _draw_display_image(self, image: Image.Image, boxes: tuple[YoloBox, ...]) -> Image.Image:
        canvas_width = max(1, self.canvas.winfo_width() - 24)
        canvas_height = max(1, self.canvas.winfo_height() - 24)
        image_width, image_height = image.size
        scale = min(canvas_width / image_width, canvas_height / image_height)
        display_size = (max(1, int(image_width * scale)), max(1, int(image_height * scale)))
        display_image = image.resize(display_size, Image.Resampling.LANCZOS)

        draw = ImageDraw.Draw(display_image)
        font = ImageFont.load_default()
        scale_x = display_size[0] / image_width
        scale_y = display_size[1] / image_height

        for box in boxes:
            color = BOX_COLORS[box.class_id % len(BOX_COLORS)]
            x1 = (box.x_center - box.width / 2) * image_width * scale_x
            y1 = (box.y_center - box.height / 2) * image_height * scale_y
            x2 = (box.x_center + box.width / 2) * image_width * scale_x
            y2 = (box.y_center + box.height / 2) * image_height * scale_y
            draw.rectangle((x1, y1, x2, y2), outline=color, width=2)

            label = self.class_names.get(box.class_id, f"class {box.class_id}")
            bbox = draw.textbbox((0, 0), label, font=font)
            label_width = bbox[2] - bbox[0] + 8
            label_height = bbox[3] - bbox[1] + 6
            label_y = max(0, y1 - label_height)
            draw.rectangle((x1, label_y, x1 + label_width, label_y + label_height), fill=color)
            draw.text((x1 + 4, label_y + 3), label, fill="#111111", font=font)

        return display_image

    def _update_info(self, item: DatasetItem) -> None:
        selected_flag = self._current_status_text()
        self.status_var.set(f"{self.current_index + 1} / {len(self.items)}  |  {selected_flag}")
        self.group_var.set(f"当前分组：{selected_flag}")
        bg, fg = self._group_colors(selected_flag)
        self.group_label.configure(bg=bg, fg=fg)
        self.file_var.set(item.relative_image_path.as_posix())
        label_state = str(item.label_path) if item.label_path else "无对应 txt"
        self.detail_var.set(f"目标框：{item.label_count}\n{self._class_summary(item)}\n标签：{label_state}")
        qualified_count = len(self.items) - len(self.relabel_indices) - len(self.delete_indices)
        self.selected_var.set(
            f"待重标：{len(self.relabel_indices)} | 删除：{len(self.delete_indices)} | 合格：{qualified_count}"
        )
        self.toggle_button.configure(text="取消待重标 (Space)" if self.current_index in self.relabel_indices else "待重标 (Space)")
        self.delete_button.configure(text="取消删除 (W/Delete)" if self.current_index in self.delete_indices else "删除 (W/Delete)")

    def _current_status_text(self) -> str:
        if self.current_index in self.relabel_indices:
            return "待重标"
        if self.current_index in self.delete_indices:
            return "删除"
        return "合格"

    def _group_colors(self, status: str) -> tuple[str, str]:
        if status == "待重标":
            return "#ffcc80", "#3e2723"
        if status == "删除":
            return "#ef9a9a", "#4a0f0f"
        return "#a5d6a7", "#0f3315"

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
        key = hashlib.sha1(str(self.dataset_root.resolve()).encode("utf-8")).hexdigest()
        state_root = Path.home() / ".yolo_dataset_reviewer" / "states"
        state_root.mkdir(parents=True, exist_ok=True)
        return state_root / f"{key}.json"

    def _save_state(self) -> None:
        if self.dataset_root is None:
            return
        try:
            save_selection_state(
                self._state_path(),
                self.relabel_indices,
                self.delete_indices,
                self.current_index,
                self.items,
            )
        except OSError:
            pass

    def _update_controls(self) -> None:
        state = tk.NORMAL if self.items else tk.DISABLED
        self.previous_button.configure(state=state)
        self.next_button.configure(state=state)
        self.toggle_button.configure(state=state)
        self.delete_button.configure(state=state)
        self.export_button.configure(state=state)


def main() -> None:
    root = tk.Tk()
    TkMainWindow(root)
    root.mainloop()
