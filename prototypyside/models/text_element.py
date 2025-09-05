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
from prototypyside.config import HandleType, ALIGNMENT_MAP
# from prototypyside.widgets.overset_plus_item import OversetPlusItem
from prototypyside.services.proto_class import ProtoClass
from prototypyside.models.component_element import ComponentElement
from prototypyside.utils.units.unit_str_font import UnitStrFont
from prototypyside.widgets.proto_text_renderer import ProtoTextRenderer
from prototypyside.views.graphics_items import ResizeHandle
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

        self._font: UnitStrFont = font or UnitStrFont(QFont("Arial", 10))
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
        self._outline = TextOutline(
            target_element=self
            # get_hit_rect=lambda frame, dpi: self._overset_hit_rect(frame)  # reuse your placement
        )
        # Show/hide via your existing flag if you like
        self._outline.setEnabled(self.display_outline)
        self._outline.setVisible(self.display_outline)

    @property
    def renderer(self):
        return self._renderer

    def boundingRect(self) -> QRectF:
        if getattr(self, "_display_outline", False) and hasattr(self._outline, "united_rect"):
            return self._outline.united_rect()
        return self._draw_rect_px()

    # def boundingRect(self) -> QRectF:
    #     if self._display_outline:
    #         return self._outline.united_rect()

    #     # When outlines are hidden (export path), expand to overset_rect if available.
    #     r = self._renderer
    #     if r and r.has_overflow and isinstance(r.overset_rect, QRectF):
    #         templat
    #         return r.overset_rect

    #     return self._geometry.to(self._unit, dpi=self._dpi).rect


    @property
    def font(self) -> UnitStrFont:
        return self._font

    @font.setter
    def font(self, value: UnitStrFont) -> None:
        if pc.isproto(self.parentItem(), pc.CT):
            raise TypeError(f"font must be a UnitStrFont not {type(value)}")
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
            
        if self.display_outline and context.is_gui:
            self._outline.paint(painter, None, None)

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
        rect_local = self._draw_rect_px()

        # clip to your local shape if you have rounded corners; otherwise a rect is fine:
        # painter.setClipRect(rect_local, Qt.ReplaceClip)

        parent_tpl = self.parentItem()
        vector_priority = getattr(parent_tpl, "render_route", RenderRoute.COMPOSITE) == RenderRoute.VECTOR_PRIORITY
        if vector_priority:
            self._paint_text_vector(painter, rect_local)
        else:
            self._paint_text_raster(painter, rect_local)

        if self.display_outline:
            self._outline.paint(painter, option=option, widget=widget)

        # Check the render route of the parent template
        parent_template = self.parentItem()
        if pc.isproto(parent_template, pc.CT):
            if parent_template.render_route == RenderRoute.VECTOR_PRIORITY and parent_template.render_mode == RenderMode.EXPORT:
                # Vectorize the text
                self._paint_text_vector(painter, rect_local)
            else:
                self._paint_text_raster(painter, rect_local)
        else:
            self._paint_text_raster(painter, rect_local)

        painter.restore()

    def _use_overset_now(self) -> bool:
        """
        GUI: if outline is visible and says expanded, honor it unconditionally.
        Export: honor _full_text_view (you can still expand even if no overflow).
        """
        if self.display_outline and hasattr(self, "_outline"):
            return bool(self._outline.is_expanded)

        # Export / no outline
        return bool(getattr(self, "_full_text_view", False))

    def _draw_rect_px(self) -> QRectF:
        geo = self._geometry.to("px", dpi=self._dpi).rect
        w, h = geo.width(), geo.height()
        if self.display_outline and hasattr(self, "_outline"):
            fr = self._outline.frame_rect()
            if isinstance(fr, QRectF) and not fr.isNull():
                return QRectF(0, 0, fr.width(), fr.height())
        # export: optionally honor full text view
        r = getattr(self, "_renderer", None)
        if not self.display_outline and getattr(self, "_full_text_view", False) and r and isinstance(getattr(r, "overset_rect", None), QRectF):
            ow, oh = r.overset_rect.width(), r.overset_rect.height()
            return QRectF(0, 0, max(w, ow), max(h, oh))
        return QRectF(0, 0, w, h)


   
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
        
        if hasattr(self, "_color"):
            r._color = self._color
            
        # Set expanded state based on context
        r.is_expanded = self._use_overset_now()
        
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

    # def paint(self, painter: QPainter, option, widget=None):
    #     """
    #     Completely overrides the ComponentElement paint class
    #     """
    #     painter.save()
    #     path = self.shape_path()

    #     # --- Background (fill inside shape) ---
    #     painter.save()
    #     painter.setPen(Qt.NoPen)
    #     painter.setBrush(QBrush(self._bg_color))
    #     painter.fillPath(path, painter.brush())
    #     painter.restore()

    #     # --- Content (clip to shape); subclasses can draw inside this clip ---
    #     rect = self.geometry.to("px", dpi=self.dpi).rect
    #     painter.save()
    #     painter.setClipPath(path)
    #     self._paint_content_inside_clip(painter, rect)  # hook for subclasses
    #     painter.restore()

        
    #     pos = QPointF(rect.x(), rect.y())
    #     # self.geometry.to("px", dpi=self.dpi).pos
        
    #     # --- Background Fill ---
    #     bg = self._bg_color
    #     color = self._color
    #     border_col = self._border_color

    #     painter.setBrush(QBrush(bg))
    #     painter.setPen(Qt.NoPen)
        
    #     # Draw background with or without rounded corners
    #     if hasattr(self, 'corner_radius') and self.corner_radius.to("px", dpi=self.dpi) > 0:
    #         cr = self.corner_radius.to("px", dpi=self.dpi)
    #         painter.drawRoundedRect(rect, cr, cr)
    #     else:
    #         painter.drawRect(rect)
        
    #     # --- Border ---
    #     bw = self.border_width.to("px", dpi=self.dpi)
    #     if bw > 0:
    #         pen = QPen(border_col)
    #         pen.setWidthF(bw)
    #         painter.setPen(pen)
    #         painter.setBrush(Qt.NoBrush)
            
    #         # Draw border with or without rounded corners
    #         if hasattr(self, 'corner_radius') and self.corner_radius.to("px", dpi=self.dpi) > 0:
    #             cr = self.corner_radius.to("px", dpi=self.dpi)
    #             painter.drawRoundedRect(rect, cr, cr)
    #         else:
    #             painter.drawRect(rect)

    #     # --- Text via renderer (pass view-state, not overflow booleans)
    #     r = self._renderer
    #     r.text      = self._content or ""
    #     r.font      = self._font
    #     r.h_align   = self._h_align
    #     r.v_align   = self._v_align
    #     r.wrap_mode = self.wrap_mode
    #     if hasattr(self, "_color"):
    #         r._color = self._color

    #     # NEW: expand when display_outline is False (export), otherwise follow outline’s toggle
    #     r.is_expanded = self._full_text_view and not self.display_outline

    #     r.render(painter, rect)
   
 
    #     if self.display_outline:
    #         self._outline.paint(painter, option=option, widget=widget)

    #     painter.restore()