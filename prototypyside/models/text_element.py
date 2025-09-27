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

from prototypyside.views.overlays.element_outline import ElementOutline #TextOutline
from prototypyside.models.component_template import RenderRoute
from prototypyside.utils.render_context import RenderContext, RenderMode, RenderRoute, TabMode

pc = ProtoClass

class TextElement(ComponentElement):
    text_changed = Signal(object, str, object, object)
    
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
            parent=parent)


        self._content = "This is a sample text that is intentionally made long enough to demonstrate the overset behavior you would typically see in design software like Adobe InDesign. When this text cannot fit within the defined boundaries of the text frame, a small red plus icon will appear, indicating that there is more text than is currently visible."
        self.wrap_mode = QTextOption.WordWrap

        self._padding = UnitStr("10px", dpi=self._ctx.dpi)
        self._wants_overflow = False

    @property
    def wants_overflow(self):
        return self._wants_overflow

    @wants_overflow.setter
    def wants_overflow(self, state):
        if state == self._wants_overflow:
            return
        self._wants_overflow = state
        self.update()
    
    @property
    def padding(self) -> UnitStr:
        return self._padding

    @padding.setter
    def padding(self, val: UnitStr) -> None:
        if val == self._padding:
            return
        self._padding = val
        self.update()

    def boundingRect(self) -> QRectF:
        ctx = self.ctx
        r = self._geometry.to(ctx.unit, dpi=self.ctx.dpi).rect
        #    if ctx.is_gui and ctx.is_component_tab:
        pad_px = "12.0px"
        pad = UnitStr(pad_px, unit=ctx.unit, dpi=self.ctx.dpi).value
        return r.adjusted(-pad, -pad, pad, pad)

    @property
    def outline(self):
        return self._outline

    # def to_dict(self):
    #     data = super().to_dict()  # ← include base fields
    #     for attr, (key, _, to_fn, default) in self._subclass_serializable.items():
    #         val = getattr(self, f"_{attr}", default)
    #         data[key] = to_fn(val)

    #     return data

    # @classmethod
    # def from_dict(cls, data: dict, registry):
    #     inst = super().from_dict(data, registry=registry)
    #     for attr, (key, from_fn, _, default) in cls._subclass_serializable.items():
    #         raw = data.get(key, default)
    #         if hasattr(inst, f"{attr}"):
    #             setattr(inst, f"{attr}", from_fn(raw))
    #         else:
    #             setattr(inst, f"_{attr}", from_fn(raw))
    #     return inst
