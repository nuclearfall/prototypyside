from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QGraphicsSceneDragDropEvent, QGraphicsObject, QFileDialog

from prototypyside.models.component_element import ComponentElement
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.units.unit_str_font import UnitStrFont
from prototypyside.utils.valid_path import ValidPath


class VectorElement(ComponentElement):
    """A component element that renders SVG vector graphics."""
    is_vector = True
    is_raster = False
    
    def __init__(self,
            proto: ProtoClass,
            pid: str, 
            registry: "ProtoRegistry", 
            geometry: UnitStrGeometry,
            name: Optional[str] = None,  
            parent: Optional[QGraphicsObject] = None
    ):
        super().__init__(
            proto=proto,
            pid=pid, 
            registry=registry, 
            geometry=geometry, 
            name=name,  
            parent=parent)

        self._v_align = Qt.AlignVCenter
        self._h_align = Qt.AlignHCenter

        self._renderer: Optional[QSvgRenderer] = None
        self.showPlaceholderText = True
        self.setAcceptDrops(True)


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
        """
        Paints a vector image inside the bounding rect, respecting aspect ratio and logical 
        units. Always draws the border *after* the content so it sits on top.
        """
        rect = self.geometry.to("px", dpi=self.dpi).rect
        
        # Set up clipping if corner radius is > 0 (regardless of border width)
        if hasattr(self, 'corner_radius') and self.corner_radius.to("px", dpi=self.dpi) > 0:
            cr = self.corner_radius.to("px", dpi=self.dpi)
            path = QPainterPath()
            path.addRoundedRect(rect, cr, cr)
            painter.setClipPath(path)
        
        if self._renderer:
            self._renderer.render(painter, rect)

        elif self.showPlaceholderText:
            painter.save()
            painter.setPen(QPen(Qt.darkGray))
            # font = painter.font()
            ustr_font = UnitStrFont(family="Arial", size=9, italic=True)
            font = ustr_font.scale(ldpi=self.ldpi, dpi=self.dpi).px.qfont
            #font.setPixelSize(int(font.pointSize()*self._dpi/self.ldpi))
            #font.setPointSize(10)
            # font.setItalic(True)
            painter.setFont(font)
            painter.drawText(rect, (self.v_align | self.h_align),
                             "Drop SVG\nor Double Click to Set")
            painter.restore()
        
        # Remove clipping before drawing border (if any)
        painter.setClipping(False)
        super().paint(painter, option, widget)

    @classmethod
    def from_dict(cls, data: dict, registry):
        inst = super().from_dict(data, registry=registry)
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

    def paint(self, painter: QPainter, option, widget=None):
        rect_px = self.geometry.to("px", dpi=self.dpi).rect
        painter.save()
        # draw your vector paths in local coords, e.g.:
        # painter.drawPath(self._path) or similar, no translation by rect.x/y
        painter.restore()
