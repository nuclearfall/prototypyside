# image_element.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF, QSize 
from PySide6.QtGui import QPainter, QPixmap, QPen, QPainterPath
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsSceneDragDropEvent,
)
from prototypyside.models.component_element import ComponentElement
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.units.unit_str_font import UnitStrFont
from prototypyside.utils.valid_path import ValidPath

class ImageElement(ComponentElement):
    _subclass_serializable = {
        "keep_aspect": ("keep_aspect",
                        lambda x: bool(x),
                        lambda b: b,
                        True),
    }

    def __init__(self,
            proto: ProtoClass,
            pid: str, 
            registry: "ProtoRegistry", 
            ctx,
            geometry: UnitStrGeometry=None,
            name: Optional[str] = None,  
            parent: Optional[QGraphicsObject] = None
    ):
        super().__init__(
            proto=proto,
            pid=pid,
            registry=registry,
            ctx=ctx,
            geometry=geometry,
            name=name,
            parent=parent
        )
        
        # Image-specific properties
        self._keep_aspect = True
        self.showPlaceholderText = True

        self.setSelected(True)
        self.setAcceptDrops(True)

    def boundingRect(self) -> QRectF:
        ctx = self._ctx 
        return self.geometry.to(ctx.unit, dpi=ctx.dpi).rect

    @property
    def keep_aspect(self) -> bool:
        return self._keep_aspect

    @keep_aspect.setter
    def keep_aspect(self, value: bool):
        if self._keep_aspect != value:
            self._keep_aspect = value
            self.item_changed.emit()
            self.update()

    def to_dict(self):
        data = super().to_dict()  # ← include base fields
        for attr, (key, _, to_fn, default) in self._subclass_serializable.items():
            val = getattr(self, f"_{attr}", default)
            data[key] = to_fn(val)

        return data
        
    @classmethod
    def from_dict(cls, data: dict, registry):
        inst = super().from_dict(data, registry=registry)
        for attr, (key, from_fn, _, default) in cls._subclass_serializable.items():
            raw = data.get(key, default)
            if hasattr(inst, f"{attr}"):
                setattr(inst, f"{attr}", from_fn(raw))
            else:
                setattr(inst, f"_{attr}", from_fn(raw))
        content = data.get("content", None)
        inst._content = content
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
            
