# text_element.py
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QObject, QRectF, QPointF, QSize, Signal, QEvent
from PySide6.QtGui import (
    QColor,
    QFont,
    QPen,
    QBrush,
    QTextDocument,
    QTextOption,
    QPainter,
    QPixmap,
    QPalette,
    QAbstractTextDocumentLayout,
    QTextCursor, 
    QTextBlockFormat,
    QPainterPath,
    QKeyEvent,
)
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QTextEdit, QGraphicsProxyWidget
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.units.unit_str_helpers import geometry_with_px_rect, geometry_with_px_pos
from prototypyside.services.proto_class import ProtoClass
from prototypyside.models.component_element import ComponentElement
from prototypyside.utils.units.unit_str_font import UnitStrFont
from prototypyside.widgets.proto_text_renderer import ProtoTextRenderer
from prototypyside.views.overlays.element_outline import TextOutline
from prototypyside.models.component_template import RenderRoute
from prototypyside.utils.render_context import RenderContext, RenderMode, RenderRoute, TabMode

pc = ProtoClass

class TextElement(ComponentElement):
    is_vector = True
    is_raster = False
    _subclass_serializable = {
        "font": ("font",
                 UnitStrFont.from_dict,
                 lambda u: u.to_dict(),
                 UnitStrFont(QFont("Arial", 10))),
    }
    text_changed = Signal(object, str, object, object)
    def __init__(self,
            proto: ProtoClass,
            pid: str, 
            registry: "ProtoRegistry", 
            geometry: UnitStrGeometry,
            name: Optional[str] = None,  
            font: Optional[UnitStrFont] = None, 
            parent: Optional[QGraphicsObject] = None
    ):
        super().__init__(
            proto=proto,
            pid=pid, 
            registry=registry, 
            geometry=geometry, 
            name=name, 
            parent=parent)

        self._font: UnitStrFont = font or UnitStrFont(QFont("Arial", 14))
        self._h_align = Qt.AlignLeft
        self._v_align = Qt.AlignTop
        self._content = "This is a sample text that is intentionally made long enough to demonstrate the overset behavior you would typically see in design software like Adobe InDesign. When this text cannot fit within the defined boundaries of the text frame, a small red plus icon will appear, indicating that there is more text than is currently visible."
        self.wrap_mode = QTextOption.WordWrap
        
        self._renderer = ProtoTextRenderer(
            dpi=self.dpi,
            ldpi=self.ldpi,
            font=self.font,
            h_align=self._h_align,
            v_align=self._v_align,
            wrap_mode=self.wrap_mode,
            color=Qt.black
        )
        self._full_text_view = False

        # Attach the decoupled outline/handle overlay
        self._outline = TextOutline(self, parent=self)
        # Show/hide via your existing flag if you like
        # self._outline.setEnabled(self.display_outline)
        # self._outline.setVisible(self.display_outline)
        self.setSelected(True)

    @property
    def renderer(self):
        return self._renderer

    def boundingRect(self) -> QRectF:
        if getattr(self, "_display_outline", False) and hasattr(self._outline, "united_rect"):
            return self._outline.united_rect()
        return self.geometry.to("px", dpi=self.dpi).rect

    @property
    def font(self) -> UnitStrFont:
        return self._font

    @font.setter
    def font(self, value: UnitStrFont) -> None:
        self.prepareGeometryChange()
        self._font = value
        self._renderer.font = value
        self.item_changed.emit()
        ### TODO: must have a signal to emit this.
        # self.new_default_font.emit(value)
        ###
        self.update()

    @property
    def h_align(self) -> Qt.Alignment:
        return self._h_align

    @h_align.setter
    def h_align(self, value: Qt.Alignment):
        if self._h_align != value:
            self._h_align = value
            self._renderer.h_align = self._h_align
            self.item_changed.emit()
            self.update()

    @property
    def v_align(self) -> Qt.Alignment:
        return self._v_align

    @v_align.setter
    def v_align(self, value: Qt.Alignment):
        if self._v_align != value:
            self._v_align = value
            self._renderer.v_align = self._v_align
            self.item_changed.emit()
            self.update()

    def clone(self):
        super().clone(self)

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
        return inst

    def render_with_context(self, painter: QPainter, context: RenderContext):
        """Render text with the given context"""
        rect_local = self.geometry.to("px", dpi=self.dpi).rect
        
        if context.vector_priority and context.is_export:
            self._paint_text_vector(painter, rect_local)
        else:
            self._paint_text_raster(painter, rect_local)
            
        # if self.display_outline and context.is_gui:
        #     self._outline.paint(painter, None, None)

    def _paint_text_raster(self, painter: QPainter, rect_local: QRectF):
        # Configure renderer from current element state
        r = self._renderer
        r.text      = self._content or ""
        r.font      = self._font
        r.h_align   = self._h_align
        r.v_align   = self._v_align
        r.wrap_mode = self.wrap_mode
        if hasattr(self, "_color"):
            r._color = self._color

        # Expand/full-text state is already chosen by _effective_text_rect_px
        # but ProtoTextRenderer may also need the boolean to alter layout strategy:
        r.is_expanded = self._use_overset_now()

        # Draw in LOCAL coords (0,0,w,h)
        r.render(painter, rect_local)

    def _paint_text_vector(self, painter: QPainter, rect_local: QRectF):
        """
        Simple vectorization using addText baseline; replace with your UnitStrFont/QTextLayout glyph-run path if needed.
        """
        painter.save()
        font: QFont = getattr(self, "_font", QFont())
        painter.setFont(font)

        text = self._content or ""
        baseline = rect_local.top() + font.pointSizeF()
        path = QPainterPath()
        path.addText(rect_local.left(), baseline, font, text)

        painter.setPen(Qt.NoPen)
        painter.setBrush(getattr(self, "_color", Qt.black))
        painter.drawPath(path)
        painter.restore()

    def paint(self, painter: QPainter, option, widget=None):
        painter.save()
        rect_local = self.boundingRect()
        self.renderer.render(painter, rect_local)
        parent_tpl = self.parentItem()
        vector_priority = getattr(parent_tpl, "render_route", RenderRoute.COMPOSITE) == RenderRoute.VECTOR_PRIORITY
        if vector_priority:
            self._paint_text_vector(painter, rect_local)
        else:
            self._paint_text_raster(painter, rect_local)

        # Check the render route of the parent template
        parent_template = self.parentItem()
        if parent_template.render_mode == RenderMode.EXPORT:
            if parent_template.render_route == RenderRoute.VECTOR_PRIORITY:
                # Vectorize the text
                self._paint_text_vector(painter, rect_local)
            else:
                self._paint_text_raster(painter, rect_local)
        else:
            self._paint_text_raster(painter, rect_local)

        painter.restore()

    def toggle_overset(self) -> bool:
        """
        GUI: if outline is visible and says expanded, honor it unconditionally.
        Export: honor _full_text_view (you can still expand even if no overflow).
        """
        self._full_text_view = not self._full_text_view
   
    def render_content(self, painter: QPainter, context: RenderContext, rect: QRectF):
        """
        Render text content based on the rendering context
        """
        if context.vector_priority and context.is_export:
            self._paint_text_vector(painter, rect)
        else:
            self._paint_text_raster(painter, rect)
    
    def _paint_text_raster(self, painter: QPainter, rect: QRectF):
        """
        Render text using raster method (QTextDocument)
        """
        # Configure renderer
        r = self._renderer
        r.text = self._content or ""
        r.font = self._font
        r.h_align = self._h_align
        r.v_align = self._v_align
        r.wrap_mode = self.wrap_mode
        r._color = self._color
        
        # Render text
        r.render(painter, rect)
    
    def _paint_text_vector(self, painter: QPainter, rect: QRectF):
        """
        Render text as vector paths (for vector priority export)
        """
        painter.save()
        font = self._font.scale(ldpi=self.ldpi, dpi=self.dpi).px.qfont
        painter.setFont(font)
        
        text = self._content or ""
        baseline = rect.top() + font.pointSizeF()
        path = QPainterPath()
        path.addText(rect.left(), baseline, font, text)

        painter.setPen(Qt.NoPen)
        painter.setBrush(self._color)
        painter.drawPath(path)
        painter.restore()