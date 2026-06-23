from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .models import YoloBox


BOX_COLORS = [
    QColor("#e53935"),
    QColor("#1e88e5"),
    QColor("#43a047"),
    QColor("#fb8c00"),
    QColor("#8e24aa"),
    QColor("#00acc1"),
    QColor("#fdd835"),
    QColor("#6d4c41"),
]


class ImageViewer(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(520, 420)
        self.setFocusPolicy(Qt.StrongFocus)
        self._image = QImage()
        self._boxes: tuple[YoloBox, ...] = ()
        self._class_names: dict[int, str] = {}
        self._message = "打开数据集后显示图片"

    def set_image(self, image_path: str, boxes: tuple[YoloBox, ...], class_names: dict[int, str]) -> None:
        self._image = QImage(image_path)
        self._boxes = boxes
        self._class_names = class_names
        self._message = "图片加载失败" if self._image.isNull() else ""
        self.update()

    def clear(self, message: str = "打开数据集后显示图片") -> None:
        self._image = QImage()
        self._boxes = ()
        self._message = message
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#202124"))

        if self._image.isNull():
            painter.setPen(QColor("#d7dce2"))
            painter.setFont(QFont("Microsoft YaHei", 14))
            painter.drawText(self.rect(), Qt.AlignCenter, self._message)
            return

        target = self._target_rect()
        painter.drawImage(target, self._image)
        self._draw_boxes(painter, target)

    def _target_rect(self) -> QRectF:
        image_width = self._image.width()
        image_height = self._image.height()
        available = self.rect().adjusted(12, 12, -12, -12)

        scale = min(available.width() / image_width, available.height() / image_height)
        width = image_width * scale
        height = image_height * scale
        x = available.x() + (available.width() - width) / 2
        y = available.y() + (available.height() - height) / 2
        return QRectF(x, y, width, height)

    def _draw_boxes(self, painter: QPainter, target: QRectF) -> None:
        if not self._boxes:
            return

        image_width = self._image.width()
        image_height = self._image.height()
        scale_x = target.width() / image_width
        scale_y = target.height() / image_height

        for box in self._boxes:
            color = BOX_COLORS[box.class_id % len(BOX_COLORS)]
            x1 = (box.x_center - box.width / 2) * image_width
            y1 = (box.y_center - box.height / 2) * image_height
            x2 = (box.x_center + box.width / 2) * image_width
            y2 = (box.y_center + box.height / 2) * image_height

            rect = QRectF(
                target.left() + x1 * scale_x,
                target.top() + y1 * scale_y,
                max(1.0, (x2 - x1) * scale_x),
                max(1.0, (y2 - y1) * scale_y),
            )

            painter.setPen(QPen(color, 2))
            painter.drawRect(rect)

            label = self._class_names.get(box.class_id, f"class {box.class_id}")
            text = f"{label}"
            metrics = painter.fontMetrics()
            text_rect = QRectF(rect.left(), max(target.top(), rect.top() - 22), metrics.horizontalAdvance(text) + 10, 20)
            painter.fillRect(text_rect, color)
            painter.setPen(QColor("#111111"))
            painter.drawText(text_rect.adjusted(5, 0, -5, 0), Qt.AlignVCenter | Qt.AlignLeft, text)

