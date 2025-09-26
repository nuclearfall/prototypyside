from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QPointF, QSize, Signal, QObject
from PySide6.QtGui import (QColor, QFont, QPen, QBrush, QPainter, QPixmap, QPalette,
            QAbstractTextDocumentLayout, QTransform, QPainterPath, QPainterPathStroker)
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QGraphicsSceneMouseEvent, QGraphicsSceneDragDropEvent, QStyleOptionGraphicsItem, QStyle
from typing import Optional, Dict, Any, Union, TYPE_CHECKING

# from prototypyside.views.graphics_items import ResizeHandle
from prototypyside.models.proto_paintable import ProtoPaintable
from prototypyside.views.overlays.element_outline import ElementOutline
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.units.unit_str_helpers import geometry_with_px_rect, geometry_with_px_pos
from prototypyside.config import HMAP, VMAP, HMAP_REV, VMAP_REV
from prototypyside.utils.graphics_item_helpers import rotate_by
from prototypyside.services.proto_class import ProtoClass
from prototypyside.utils.render_context import RenderContext, RenderMode, RenderRoute, TabMode
from prototypyside.views.shape_mixin import ShapeableElementMixin

from prototypyside.services.proto_paint import ProtoPaint
if TYPE_CHECKING:
    from prototypyside.services.proto_registry import ProtoRegistry

pc = ProtoClass

class ComponentElement(ProtoPaintable):

    def __init__(self,
        proto: ProtoClass,
        pid: str, 
        registry: "ProtoRegistry", 
        geometry: UnitStrGeometry,
        name: Optional[str] = None,   
        parent = None
    ):
        super().__init__(proto, pid, registry, geometry, name, parent)

        self._shape = "rect"
        self._geometry = geometry or UnitStrGeometry(width="0.75in", height="0.5in", x="10 px", y="10 px", dpi=self._ctx.dpi)

        self._outline = ElementOutline(self, parent=self)
        self._corner_radius = UnitStr(".125 in", dpi=self._ctx.dpi)

        self._group_drag_active = False
        self._group_drag_items = []
        self._group_drag_start_pos = {}
        self._group_anchor_pos = QPointF()

        if self._ctx.is_component_tab and self._ctx.is_gui:
            self._outline.setEnabled(True)
            self._outline.setVisible(True)
            self.setSelected(True)
            self.setAcceptDrops(True)
            self.setFlag(QGraphicsItem.ItemIsSelectable, True)
            self.setFlag(QGraphicsItem.ItemIsMovable, True)
            self.setAcceptedMouseButtons(Qt.LeftButton)
            self.setAcceptHoverEvents(True)     
        
    def boundingRect(self) -> QRectF:
        ctx = self.ctx
        r = self._geometry.to(ctx.unit, dpi=ctx.dpi).rect
        # if ctx.is_gui and ctx.is_component_tab:
        #     pad = 12.0
        #     return r.adjusted(-pad, -pad, pad, pad)
        # else:
        return r

    @property
    def outline(self):
        return self._outline

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.isSelected():
            items = self.scene().selectedItems() if self.scene() else [self]
            self._group_drag_items = [it for it in items
                                      if (it is self) or (it.flags() & QGraphicsItem.ItemIsMovable)]
            self._group_drag_start_pos = {it: it.pos() for it in self._group_drag_items}
            self._group_anchor_pos = self.pos()
            self._group_drag_active = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._group_drag_active:
            super().mouseMoveEvent(event)  # move the lead item (snapping/constraints happen here)
            delta = self.pos() - self._group_anchor_pos
            if not delta.isNull():
                for it in self._group_drag_items:
                    if it is self: 
                        continue
                    it.setPos(self._group_drag_start_pos[it] + delta)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        try:
            super().mouseReleaseEvent(event)
        finally:
            if self._group_drag_active:
                ends = {it: it.pos() for it in self._group_drag_items}
                # Only emit if anything actually moved
                moved = any(ends[it] != self._group_drag_start_pos[it] for it in self._group_drag_items)
                if moved:
                    self.moveCommitted.emit(self._group_drag_items, self._group_drag_start_pos, ends)
            # cleanup
            self._group_drag_active = False
            self._group_drag_items = []
            self._group_drag_start_pos = {}
            self._group_anchor_pos = QPointF()