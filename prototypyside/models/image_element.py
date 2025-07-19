# image_element.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPixmap, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsSceneDragDropEvent,
)

from prototypyside.models.component_elements import ComponentElement
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry

class ImageElement(ComponentElement):
    _subclass_serializable = {
        "keep_aspect": ("keep_aspect",
                        lambda x: bool(x),
                        lambda b: b,
                        True),
    }

    def __init__(self, pid, geometry: UnitStrGeometry, tpid = None, 
            parent: Optional[QGraphicsObject] = None, name: str = None):
        super().__init__(pid, geometry, tpid, parent, name)

        self._pixmap: Optional[QPixmap] = None
        # _content is handled by ComponentElement
        self._alignment = "Center"
        # Image-specific properties
        self._keep_aspect = True
        self.showPlaceholderText = True

        self.setAcceptDrops(True)

    # override the content getter/setter
    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, new_content: Optional[str]):
        # always clear pixmap if new_content is None or invalid
        if not new_content or not Path(new_content).exists():
            self._pixmap = None
            self._content = None
        else:
            pm = QPixmap(new_content)
            self._pixmap = pm if not pm.isNull() else None
            self._content = new_content
        self.item_changed.emit()
        self.update()



    # --- Image-specific Property Getters and Setters ---
    @property
    def keep_aspect(self) -> bool:
        return self._keep_aspect

    @keep_aspect.setter
    def keep_aspect(self, value: bool):
        if self._keep_aspect != value:
            self._keep_aspect = value
            self.item_changed.emit()
            self.update()

    # --- End Image-specific Property Getters and Setters ---

    def paint(self, painter: QPainter, option, widget=None):
        """
        Paints an image inside the bounding rect, respecting aspect ratio and logical units.
        Always draws the border *after* the content so it sits on top.
        """
        # 1) figure out our rect & size
        rect = self.geometry.to(self.unit, dpi=self.dpi).rect
        size = self.geometry.to(self.unit, dpi=self.dpi).size
        w = size.width()
        h = size.height()
        # 2) draw the image *first*
        if self._pixmap:
            if self._keep_aspect:
                scaled = self._pixmap.scaled(
                    w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                x = rect.x() + (rect.width() - scaled.width()) / 2
                y = rect.y() + (rect.height() - scaled.height()) / 2
                painter.drawPixmap(QPointF(x, y), scaled)
            else:
                painter.drawPixmap(
                    rect.topLeft(),
                    self._pixmap.scaled(size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                )

        # 3) or draw placeholder text *instead* (still before the border)
        elif self.showPlaceholderText:
            painter.save()
            painter.setPen(QPen(Qt.darkGray))
            font = painter.font()
            font.setPointSize(10)
            font.setItalic(True)
            painter.setFont(font)
            painter.drawText(rect, self.alignment_flags,
                             "Drop Image\nor Double Click to Set")
            painter.restore()

        # 4) finally, draw the border on top
        super().paint(painter, option, widget)


    def to_dict(self):
        data = super().to_dict()  # ← include base fields
        for attr, (key, _, to_fn, default) in self._subclass_serializable.items():
            val = getattr(self, f"_{attr}", default)
            data[key] = to_fn(val)
        return data

    @classmethod
    def from_dict(cls, data: dict, registry, is_clone=False):
        inst = super().from_dict(data, registry, is_clone)
        for attr, (key, from_fn, _, default) in cls._subclass_serializable.items():
            raw = data.get(key, default)
            if hasattr(inst, f"{attr}"):
                setattr(inst, f"{attr}", from_fn(raw))
            else:
                setattr(inst, f"_{attr}", from_fn(raw))
        return inst

    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0]
            file_path = url.toLocalFile()
            if file_path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif")):
                self.content = file_path
            event.acceptProposedAction()

    def mouseDoubleClickEvent(self, event):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(None, "Select Image", "", "Images (*.png *.jpg *.bmp *.gif)")
        if path:
            self.content = path
            
