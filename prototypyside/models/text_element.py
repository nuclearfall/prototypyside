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
            parent: Optional[QGraphicsObject] = None
    ):
        super().__init__(
            proto=proto,
            pid=pid, 
            registry=registry, 
            geometry=geometry, 
            name=name, 
            parent=parent)

        self._font = registry.settings.default_font
        print(self._font) # Correctly prints the font
        self._h_align = Qt.AlignLeft
        self._v_align = Qt.AlignTop
        self._content = "This is a sample text that is intentionally made long enough to demonstrate the overset behavior you would typically see in design software like Adobe InDesign. When this text cannot fit within the defined boundaries of the text frame, a small red plus icon will appear, indicating that there is more text than is currently visible."
        self.wrap_mode = QTextOption.WordWrap

        self._padding = UnitStr("10 pt", dpi=self.dpi)
        self._renderer = ProtoTextRenderer(
            dpi=self.dpi,
            unit=self.unit,
            ldpi=self.ldpi,
            font=self._font,
            geometry=self._geometry,
            h_align=self._h_align,
            v_align=self._v_align,
            padding=self.padding,
            wrap_mode=self.wrap_mode,
            color=Qt.black,
            content=self._content,
            context=self._context
        )
        self._renderer.setParentItem(self)
        self._full_text_view = False

        # Attach the decoupled outline/handle overlay
        self._outline = TextOutline(self, parent=self)
        # Show/hide via your existing flag if you like
        # self._outline.setEnabled(self.display_outline)
        # self._outline.setVisible(self.display_outline)
        self.setSelected(True)

    @property
    def padding(self) -> UnitStr:
        return self._padding

    @padding.setter
    def padding(self, val: UnitStr) -> None:
        self._renderer.padding = val
        self._padding = val
    
    @property
    def renderer(self):
        return self._renderer

    def boundingRect(self) -> QRectF:
        if getattr(self, "_display_outline", False) and hasattr(self._outline, "united_rect"):
            return self._outline.united_rect()
        return self.geometry.to(self.unit, dpi=self.dpi).rect

    @property
    def font(self) -> UnitStrFont:
        return self._font

    @font.setter
    def font(self, value: UnitStrFont) -> None:
        self.prepareGeometryChange()
        self._font = UnitStrFont(value)
        self._renderer.font = value
        self.item_changed.emit()
        ### TODO: must have a signal to emit this.
        # self.new_default_font.emit(value)
        ###
        self.update()

    @property
    def content(self) -> Optional[str]:
        return self._content

    @content.setter
    def content(self, content: str):
        self._content = content
        self._renderer.content = content
        self._outline.content = content 
        self.item_changed.emit()
        self.update()

    @property
    def outline(self):
        return self._outline
    
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

    def paint(self, painter: QPainter, option, widget=None):
        painter.save()
        font = self.font
        r = self._renderer
        r.geometry = self.geometry
        r.unit = self.unit
        r.dpi       = self.dpi
        r.text      = self._content or ""
        r.font      = font
        r.h_align   = self._h_align
        r.v_align   = self._v_align
        r.wrap_mode = self.wrap_mode
        if hasattr(self, "_color"):
            r._color = self._color
        r.context = self.context
        # Expand/full-text state is already chosen by _effective_text_rect_px
        # but ProtoTextRenderer may also need the boolean to alter layout strategy:
        # Draw in LOCAL coords (0,0,w,h)
        if r.is_expanded:
            r.render(painter, r.overset_rect)
        else:
            print(f"Renderer receiving geometry: {self.geometry}")
            r.render(painter)
        painter.restore()