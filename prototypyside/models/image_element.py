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
    def __init__(self,
            proto: ProtoClass,
            pid: str, 
            registry: "ProtoRegistry", 
            geometry: UnitStrGeometry=None,
            name: Optional[str] = None,  
            parent: Optional[QGraphicsObject] = None
    ):
        super().__init__(
            proto=proto,
            pid=pid,
            registry=registry,
            geometry=geometry,
            name=name,
            parent=parent
        )
        
    def boundingRect(self) -> QRectF:
        ctx = self._ctx 
        return self.geometry.to(ctx.unit, dpi=ctx.dpi).rect

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
            
