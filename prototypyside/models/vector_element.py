from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QGraphicsSceneDragDropEvent, QGraphicsObject, QFileDialog

from prototypyside.models.component_element import ComponentElement
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry


class VectorElement(ComponentElement):
    """A component element that renders SVG vector graphics."""

    def __init__(self, pid, geometry: UnitStrGeometry, tpid=None,
                 parent: Optional[QGraphicsObject] = None, name: str = None):
        super().__init__(pid, geometry, tpid, parent, name)
        self._renderer: Optional[QSvgRenderer] = None
        self.showPlaceholderText = True
        self.setAcceptDrops(True)

    # Override content so it loads the SVG file
    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, new_content: Optional[str]):
        if not new_content or not Path(new_content).exists():
            self._renderer = None
            self._content = None
        else:
            renderer = QSvgRenderer(new_content)
            if renderer.isValid():
                self._renderer = renderer
                self._content = new_content
            else:
                self._renderer = None
                self._content = None
        self.item_changed.emit()
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.geometry.to("px", dpi=self.dpi).rect
        if self._renderer:
            self._renderer.render(painter, rect)
        elif self.showPlaceholderText:
            painter.save()
            painter.setPen(QPen(Qt.darkGray))
            font = painter.font()
            font.setPointSize(10)
            font.setItalic(True)
            painter.setFont(font)
            painter.drawText(rect, self.alignment_flags,
                             "Drop SVG\nor Double Click to Set")
            painter.restore()
        super().paint(painter, option, widget)

    @classmethod
    def from_dict(cls, data: dict, registry, is_clone=False):
        inst = super().from_dict(data, registry, is_clone)
        content = data.get("content")
        inst.content = None
        inst.content = content
        return inst

    # --- Drag and drop / double click ---
    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0]
            file_path = url.toLocalFile()
            if file_path.lower().endswith(".svg"):
                self.content = file_path
            event.acceptProposedAction()

    def mouseDoubleClickEvent(self, event):
        path, _ = QFileDialog.getOpenFileName(None, "Select SVG", "", "SVG Files (*.svg)")
        if path:
            self.content = path
