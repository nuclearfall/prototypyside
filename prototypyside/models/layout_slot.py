from typing import List, Optional, Dict, Tuple, Any, TYPE_CHECKING
import uuid

from PySide6.QtWidgets import QGraphicsObject, QGraphicsItem, QStyle
from PySide6.QtCore import Qt, QRectF, QPointF, QSizeF, Signal
from PySide6.QtGui import QPainter, QPixmap, QColor, QImage, QPen, QBrush, QTransform, QPainterPath

from prototypyside.config import DISPLAY_MODE_FLAGS
from prototypyside.services.proto_class import ProtoClass
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.units.unit_str_helpers import geometry_with_px_rect, geometry_with_px_pos
from prototypyside.utils.render_context import RenderContext, RenderMode, RenderRoute, TabMode

if TYPE_CHECKING:
    from prototypyside.services.proto_registry import ProtoRegistry


def _rotate_around(painter: QPainter, center: QPointF, angle_deg: float):
    if not angle_deg:
        return
    t = QTransform()
    t.translate(center.x(), center.y())
    t.rotate(angle_deg)
    t.translate(-center.x(), -center.y())
    painter.setTransform(painter.transform() * t)


class LayoutSlot(QGraphicsObject):
    """
    A parent container for a single component on a layout page.

    Rules:
      - GUI/RASTER route: parent paints a scaled raster of the child; child has no contents.
      - Export (VECTOR/COMPOSITE): parent does not paint the child; child paints itself.
      - Child component is parented to this slot and positioned at (0,0) in slot-local coords.
    """
    item_changed = Signal()

    def __init__(self, proto, pid, registry, geometry=None, row=0, column=0, name=None, parent=None):
        super().__init__(parent)
        self.proto = proto
        self._pid = pid
        self._registry = registry
        self._ctx = registry.settings.ctx
        self._geometry: UnitStrGeometry = geometry
        self._row = row
        self._column = column
        self._name = registry.validate_name(proto, name)
        self._ldpi = registry.settings.ldpi

        self._content = None  # Component clone / instance assigned into this slot

        # Visual & state flags
        self._display_mode = DISPLAY_MODE_FLAGS.get("stretch").get("aspect")
        self._hovered = False
        self._rotation = 0

        # Cache for GUI raster
        self._cache_image: Optional[QImage] = None

        # Interaction flags
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setFlag(QGraphicsObject.ItemIsSelectable, True)
        self.setFlag(QGraphicsObject.ItemIsFocusable, True)

        # Make sure our QGraphicsItem position matches geometry pos
        super().setPos(self._geometry.to(self._ctx.unit, dpi=self._ctx.dpi).pos)

        # Safe defaults (only used if you wire these via UI)
        self._render_text = True
        self._render_vector = False

    # ---------------- QGraphicsItem geometry ---------------- #

    def boundingRect(self) -> QRectF:
        # LOCAL rect only (no x,y)
        rect = self._geometry.to(self.ctx.unit, dpi=self.ctx.dpi).rect
        return QRectF(0, 0, rect.width(), rect.height())

    def shape(self) -> QPainterPath:
        # Prefer the child’s shape path if available; otherwise, rect.
        path = QPainterPath()
        if self._content and hasattr(self._content, "shape_path"):
            try:
                sp = self._content.shape_path()
                if not sp.isEmpty():
                    return sp
            except Exception:
                pass
        path.addRect(self.boundingRect())
        return path

    def setRect(self, new_rect: QRectF):
        if self._geometry.to(self.ctx.unit, dpi=self.ctx.dpi).rect == new_rect:
            return
        self.prepareGeometryChange()
        geometry_with_px_rect(self._geometry, new_rect, dpi=self.ctx.dpi)
        self._sync_child_geometry()
        self.invalidate_cache()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        if change == QGraphicsItem.ItemPositionChange and value != self.pos():
            signals_blocked = self.signalsBlocked()
            self.blockSignals(True)
            self.geometry = geometry_with_px_pos(self._geometry, value, dpi=self.ctx.dpi)
            self.blockSignals(signals_blocked)
        return super().itemChange(change, value)

    # ---------------- properties ---------------- #
    @property
    def pid(self) -> str:
        return self._pid

    @pid.setter
    def pid(self, value):
        self._pid = value
        
    @property
    def registry(self):
        return self._registry

    @property
    def ctx(self) -> RenderContext:
        return self._ctx

    @ctx.setter
    def ctx(self, new_ctx: RenderContext):
        self._ctx = new_ctx
        if new_ctx.is_raster:
            self.invalidate_cache()
        self.update()

    @property
    def geometry(self) -> UnitStrGeometry:
        return self._geometry

    @geometry.setter
    def geometry(self, new_geom: UnitStrGeometry):
        if self._geometry == new_geom:
            return
        self.prepareGeometryChange()
        self._geometry = new_geom
        super().setPos(self._geometry.to(self.ctx.unit, dpi=self.ctx.dpi).pos)
        self._sync_child_geometry()
        self.invalidate_cache()
        self.update()

    @property
    def row(self): return self._row

    @row.setter
    def row(self, new):
        if new != self._row:
            self._row = new
            self.item_changed.emit()

    @property
    def column(self): return self._column

    @column.setter
    def column(self, new):
        if new != self._column:
            self._column = new
            self.item_changed.emit()

    @property
    def name(self): return self._name

    @name.setter
    def name(self, value):
        if value != self._name:
            self._name = value

    @property
    def dpi(self) -> int:
        return self._dpi

    @dpi.setter
    def dpi(self, new: int):
        if self._dpi != new:
            self._dpi = new
            # cascade to child + invalidate raster cache
            if self._content:
                self._content.dpi = new
            self.invalidate_cache()
            self.update()

    # ---------------- content management ---------------- #
    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, obj):
        # Clear
        if obj is None:
            if self._content:
                self._content = None
            self.invalidate_cache()
            self.update()
            return

        # Accept only component clones/instances
        if ProtoClass.isproto(obj, ProtoClass.CC):
            self._content = obj
            obj.ctx = self._ctx
            
            # Hide editor outlines in layout
            for item in obj.items:
                item.ctx = self._ctx

            # Parent inside the slot and zero local pos.
            self._content.setParentItem(self)
            self._content.setPos(QPointF(0, 0))

            # IMPORTANT: Reset all element positions to be relative to component origin
            for item in getattr(self._content, "items", []):
                try:
                    # Get element's current geometry
                    el_geom = item.geometry
                    # Create new geometry with same size but position relative to component
                    new_geom = UnitStrGeometry(
                        width=el_geom.width,
                        height=el_geom.height,
                        x=el_geom.x,  # Keep original x relative to component
                        y=el_geom.y,  # Keep original y relative to component
                        unit=el_geom.unit,
                        dpi=el_geom.dpi
                    )
                    item.geometry = new_geom
                    item.setPos(QPointF(el_geom.x.to(self.ctx.unit, dpi=self.ctx.dpi), 
                                       el_geom.y.to(self.ctx.unit, dpi=self.ctx.dpi)))
                except Exception:
                    pass
            # if self.ctx.is_gui:
            #     self._content.setFlag(QGraphicsItem.ItemHasNoContents, self._ctx.is_raster)
            # else:
            #     self._content.setFlag(QGraphicsItem.ItemHasNoContents, not self._ctx.is_gui)
            self.invalidate_cache()
            self.update()

    def clear_content(self):
        if self._content:
            self.registry.deregister(self._content.pid)
        self._content = None
        self.invalidate_cache()
        self.update()

    # ---------------- caching ---------------- #

    def invalidate_cache(self):
        self._cache_image = None

    @property
    def image(self) -> Optional[QImage]:
        if self._cache_image is None and self._content:
            self._cache_image = self._render_to_image()
        return self._cache_image

    def _render_to_image(self) -> Optional[QImage]:
        """
        Ask the child to rasterize itself for GUI display.
        The result is scaled to the slot rect during paint.
        """
        if not self._content:
            return None
        # Prefer component's own rasterization API
        if hasattr(self._content, "to_raster_image"):
            return self._content.to_raster_image(self._ctx)
        if hasattr(self._content, "render_to_image"):
            return self._content.render_to_image()
        return None

    # ---------------- serialization ---------------- #

    def clone(self):
        return self.registry.clone(self)

    def to_dict(self):
        content_data = None
        if self._content and hasattr(self._content, "to_dict"):
            content_data = self._content.to_dict()
            for item in content_data.get("items", []):
                item.pop("parent", None)
        return {
            "pid": self._pid,
            "geometry": self._geometry.to_dict(),
            "row": self._row,
            "column": self._column,
            "name": self._name,
            "content": content_data
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        registry: "ProtoRegistry",
    ) -> "LayoutSlot":
        serial_pid = data.get("pid") or f"ls_{uuid.uuid4()}"
        geom = UnitStrGeometry.from_dict(data["geometry"])
        inst = cls(
            proto=ProtoClass.LS,
            pid=serial_pid,
            geometry=geom,
            registry=registry,
            row=int(data.get("row", 0)),
            column=int(data.get("column", 0)),
            parent=None,
        )
        return inst

    # ---------------- painting ---------------- #

    def paint(self, painter: QPainter, option, widget=None):
        # Optional GUI outline (helpful affordance in editor)
        if self._ctx.is_raster and self._ctx.mode == RenderMode.GUI:
            r = self.geometry.to(self.ctx.unit, dpi=self.ctx.dpi).rect
            painter.save()
            pen = QPen(QColor(0, 195, 255, 200))
            pen.setCosmetic(True)
            pen.setWidthF(1.0)
            painter.setPen(pen)
            if self.isSelected():
                painter.setBrush(QColor(0, 195, 255, 70))
            elif option.state & QStyle.State_MouseOver:
                painter.setBrush(QColor(0, 195, 255, 35))
            else:
                painter.setBrush(Qt.NoBrush)
            painter.drawRect(r)
            painter.restore()

        if not self._content:
            return

        # GUI/RASTER: parent draws a raster; child suppressed (ItemHasNoContents=True)
        if self._ctx.is_raster:
            img = self.image
            if img is None or img.isNull():
                return

            # Clip to component shape if provided
            shape_path = self.shape()
            painter.save()
            painter.setClipPath(shape_path, Qt.IntersectClip)

            # SCALE raster to the slot rect (prevents “huge image” at 72 dpi)
            r = self.geometry.to(self.ctx.unit, dpi=self.ctx.dpi).rect
            painter.drawImage(r, img, img.rect())

            painter.restore()

        else:
            # VECTOR/COMPOSITE routes:
            # Do NOT paint here; the child paints itself (no double render).
            # Child has ItemHasNoContents=False (set in context setter).
            pass

    # ---------------- hover feedback ---------------- #

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()

    # ---------------- helpers ---------------- #

    def _sync_child_geometry(self):
        """Keep child geometry sized to slot and positioned at (0,0)."""
        if not self._content:
            return
        try:
            geom0 = UnitStrGeometry.from_dict(self._geometry.to_dict())
            geometry_with_px_pos(geom0, QPointF(0, 0), dpi=self.ctx.dpi)
            self._content.geometry = geom0
            self._content.setPos(QPointF(0, 0))
        except Exception:
            self._content.geometry = self._geometry
            self._content.setPos(QPointF(0, 0))



#     def paint(self, painter: QPainter, option, widget=None):

#         if self.ctx.route == RenderRoute.RASTER:
#             if self.ctx.mode == RenderMode.GUI:
#                 r = self.geometry.to(self.ctx.unit, dpi=self.ctx.dpi)
#                 painter.save()
#                 pen = QPen(QColor(0, 195, 255, 200))
#                 pen.setCosmetic(True)
#                 pen.setWidthF(1.0)
#                 painter.setPen(pen)

#                 # Light fill on hover, stronger when selected
#                 if self.isSelected():
#                     painter.setBrush(QColor(0, 195, 255, 70))
#                 elif option.state & QStyle.State_MouseOver:
#                     painter.setBrush(QColor(0, 195, 255, 35))
#                 else:
#                     painter.setBrush(Qt.NoBrush)

#                 painter.drawRect(self.geometry.to(self.ctx.unit, dpi=self.ctx.dpi).rect)
#                 painter.restore()

#         if not self.content:
#             return

#         # Get the component's shape path and use it for clipping
#         shape_path = self._content.shape_path()
#         painter.save()
#         painter.setClipPath(shape_path, Qt.IntersectClip)

#         # Render the component's raster image
#         # img = self._content.to_raster_image(self.ctx)
#         # painter.drawImage(self.geometry.to(self.ctx.unit, dpi=self.ctx.dpi).rect, img, img.rect())
#         painter.restore()

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()