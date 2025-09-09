from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Any, TYPE_CHECKING
from enum import Enum, auto
import json
from PySide6.QtWidgets import QGraphicsObject, QGraphicsItem, QStyle, QStyleOptionGraphicsItem, QGraphicsSceneMouseEvent
from PySide6.QtCore import Qt, QRectF, QPointF, QSizeF, QMarginsF, Signal
from PySide6.QtGui import QPainter, QPixmap, QColor, QImage, QPen, QBrush,  QPageLayout, QPageSize, QTransform


from prototypyside.models.component_template import RenderMode, TabMode, RenderRoute

from prototypyside.services.proto_class import ProtoClass
from prototypyside.models.text_element import TextElement
from prototypyside.models.component_template import ComponentTemplate
from prototypyside.models.component import Component
from prototypyside.models.image_element import ImageElement
from prototypyside.models.vector_element import VectorElement
from prototypyside.utils.unit_converter import to_px, page_in_px, page_in_units, compute_scale_factor
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.units.unit_str_helpers import geometry_with_px_rect, geometry_with_px_pos
from prototypyside.config import PAGE_SIZES, DISPLAY_MODE_FLAGS, PAGE_UNITS
from prototypyside.utils.render_context import RenderContext, RenderMode, RenderRoute, TabMode
if TYPE_CHECKING:
    from prototypyside.services.proto_registry import ProtoRegistry


def _rotate_around(painter, center: QPointF, angle_deg: float):
    if not angle_deg:
        return
    t = QTransform()
    t.translate(center.x(), center.y())
    t.rotate(angle_deg)
    t.translate(-center.x(), -center.y())
    painter.setTransform(painter.transform() * t)

class LayoutSlot(QGraphicsObject):
    item_changed = Signal()
    def __init__(self, proto, pid, registry, geometry, row=0, column=0, name=None, parent=None):
        super().__init__(parent)
        self.proto = proto
        self._pid = pid
        self._registry = registry
        self._geometry = geometry
        self._row = row
        self._column = column
        self._name = registry.validate_name(proto, name)

        self._unit = registry.settings.unit
        self._dpi = registry.settings.dpi
        self._ldpi = registry.settings.ldpi

        self._content = None

        # setup flags
        self._display_mode = DISPLAY_MODE_FLAGS.get("stretch").get("aspect")
        self._cache_image = None
        self._render_text = True
        self._render_vector = True
        self._hovered = False
        self._set_print_mode = False
        self._rotation = 0
        self._component_pid = None

        self._hovered = False
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setFlag(QGraphicsObject.ItemIsSelectable, True)
        self.setFlag(QGraphicsObject.ItemIsFocusable, True)

    def boundingRect(self) -> QRectF:
        # LOCAL rect only (no x,y)
        return self._geometry.to("px", dpi=self.dpi).rect

    def setRect(self, new_rect: QRectF):
        if self._geometry.to(self.unit, dpi=self.dpi).rect == new_rect:
            return
        self.prepareGeometryChange()
        geometry_with_px_rect(self._geometry, new_rect, dpi=self.dpi)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        # This is called when the scene moves the item.
        if change == QGraphicsItem.ItemPositionChange and value != self.pos():
            # Block signals to prevent a recursive loop if a connected item
            # also tries to set the position.
            signals_blocked = self.signalsBlocked()
            self.blockSignals(True)
            geometry_with_px_pos(self._geometry, value, dpi=self.dpi)
            print(f"[ITEMCHANGE] Called with change={change}, value={value}")
            print(f"[ITEMCHANGE] Geometry.pos updated to: {self._geometry.to(self.unit, dpi=self.dpi).pos}")
            self.blockSignals(signals_blocked)

        # If other signals are emitted or updates called for, it breaks the undo stack.
        return super().itemChange(change, value)

    # --- property Getter/Setters ---#

    @property
    def registry(self):
        return self._registry

    @property
    def geometry(self):
        return self._geometry

    @geometry.setter
    def geometry(self, new_geom: UnitStrGeometry):
        if self._geometry == new_geom:
            return
        self.prepareGeometryChange()
        self._geometry = new_geom
        super().setPos(self._geometry.to(self.unit, dpi=self.dpi).pos)
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
    def name(self):
        return self._name

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
            if self._content:
                self._content.dpi = new
                for item in self._content.items:
                    item.dpi = new
                self.invalidate_cache()
                self.update()

    @property
    def render_text(self):
        return self._render_text

    @render_text.setter
    def render_text(self, new: bool):
        if new != self._render_text:
            self._render_text = new
            self.invalidate_cache()
            self.update()

    @property
    def render_vector(self):
        return self._render_vector

    @render_vector.setter
    def render_vector(self, new: bool):
        if new != self._render_vector:
            self._render_vector = new
            self.invalidate_cache()
            self.update()
                
    @property
    def unit(self) -> str:
        return self._unit

    @unit.setter
    def unit(self, new: str):
        if self._unit != new:
            self._unit = new
            if ProtoClass.isproto(self.content, ProtoClass.CC):
                for item in self._content.items:
                    item.unit = new

    def clear_content(self):
        if self._content:
            self.registry.deregister(self._content.pid)
        self.content = None

        
    # --- Addiontal Property Getter/Setters ---#
    @property
    def pid(self) -> str:
        return self._pid

    @pid.setter
    def pid(self, value):
        self._pid = value

    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, obj):
        self._content = obj
        self._component_pid = obj.pid if obj else None
        for item in obj.items:
            item._display_outline = False
        if ProtoClass.isproto(self.content, ProtoClass.CC):
            self._content.slot = self.pid
            # self.tpid = obj.pid if hasattr(obj, "pid") else None
            self._content.geometry = self.geometry
        self.invalidate_cache()
        self.update()

    @property
    def image(self):
        if self._cache_image is None:
            self._cache_image = self._render_to_image()
        return self._cache_image
        
    @property 
    def display_mode(self):
        return self._display_mode

    @display_mode.setter
    def display_mode(self, qflag):
        if qflag != self._display_mode:
            self._display_mode = qflag
            
    def receive_packet(self, packet):
        action = packet.get("action")
        if action == "clone_and_insert":
            template = self.registry.get(packet["template_pid"])
            clone = self.registry.get(packet["clone_pid"])
            if not clone:
                clone = self.registry.clone(template)
            self.content = clone
        elif action == "restore_previous_content":
            clone_pid = packet["clone_pid"]
            previous_pid = packet["previous_content_pid"]
            # Remove the new clone
            if clone_pid:
                self.registry.deregister(clone_pid)
            # Restore previous content if it existed
            if previous_pid:
                previous = self.registry.get(previous_pid)
                self.content = previous
            else:
                self.content = None

    @property
    def set_print_mode(self):
        return self._set_print_mode

    @set_print_mode.setter
    def set_print_mode(self, val):
        self._set_print_mode = val
        if self.content:
            for item in self.content.items:
                item.display_border = False
        self.invalidate_cache()

    def invalidate_cache(self):
        self._cache_image = None
        self.update()

    def clone(self):
        registry = self.registry
        return registry.clone(self)

    def to_dict(self):
        content_data = None
        if self._content:
            # Create a copy without parent references
            content_data = self._content.to_dict()
            # Remove recursive references
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
        """
        Hydrate or clone a LayoutSlot.

        Rules:
          - PID: normalize serialized PID; on clone, mint a fresh 'ls_<uuid>'.
          - Geometry: restore from dict and set position.
          - Content: if present (ComponentTemplate payload), rehydrate via factory;
                     on clone, clone the content (fresh pids) and record provenance.
          - Registration: register the slot once fully constructed (or earlier if your
                          naming needs it—but avoid double-register).
        """

        # --- PID ---
        serial_pid = data.get("pid")
        if not serial_pid:
            # fall back to minting with LS prefix
            serial_pid = f"{ProtoClass.LS.prefix}_{uuid.uuid4()}"

        # --- Geometry ---
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

        # --- Flags / misc ---
        inst._display_mode = data.get("display_mode", inst._display_mode)
        # inst._render_text   = bool(data.get("render_text",   inst._render_text))
        # inst._render_vector = bool(data.get("render_vector", inst._render_vector))

        # --- Content (ComponentTemplate) ---
        # handled by the registry now)

        return inst
   
    def paint(self, painter: QPainter, option, widget=None):
        # Create appropriate context based on current mode
        context = RenderContext(
            mode=RenderMode.GUI,
            tab_mode=TabMode.LAYOUT,
            route=RenderRoute.RASTER,  # Always raster for LayoutTab GUI
            dpi=self.dpi
        )
        
        # Render content as raster image for LayoutTab GUI
        if context.is_layout_tab and self._content:
            img = self._content.to_raster_image(context)
            painter.drawImage(QPointF(0, 0), img)
        elif self._content:
            self._content
            # Direct rendering for ComponentTab
            self._content.render(painter, context)

        # --- OUTLINE (last, on top) ---
        if context.mode is RenderMode.GUI:
            r = self.boundingRect()  # (0,0,w,h) in item-local coords
            painter.save()

            # Pen: cosmetic 1px cyan outline
            pen = QPen(QColor(0, 195, 255, 200))
            pen.setCosmetic(True)
            pen.setWidthF(1.0)
            painter.setPen(pen)

            # Brush: none by default; light fill on hover, stronger when selected
            if self.isSelected():
                brush = QBrush(QColor(0, 195, 255, 70))
            elif option.state & QStyle.State_MouseOver:
                brush = QBrush(QColor(0, 195, 255, 35))
            else:
                brush = Qt.NoBrush
            painter.setBrush(brush)

            # Inset so the 1px stroke doesn't get clipped
            r = r.adjusted(0.5, 0.5, -0.5, -0.5)
            painter.drawRect(r)
            painter.restore()

    def export_to_qimage(self, export_dpi: int) -> QImage:
        """
        Raster export method
        """
        assert self._content
        context = RenderContext(
            mode=RenderMode.EXPORT,
            tab_mode=TabMode.LAYOUT,
            route=RenderRoute.RASTER,
            dpi=export_dpi
        )
        return self._content.to_raster_image(context)
    
    def export_to_painter(self, painter: QPainter, vector_priority: bool = False):
        """
        Vector/Composite export method
        """
        assert self._content
        context = RenderContext(
            mode=RenderMode.EXPORT,
            tab_mode=TabMode.LAYOUT,
            route=RenderRoute.VECTOR_PRIORITY if vector_priority else RenderRoute.COMPOSITE,
            dpi=self._registry.settings.print_dpi,
            vector_priority=vector_priority
        )
        rect_px = self.geometry.to("px", dpi=self.dpi).rect
        painter.save()
        painter.translate(rect_px.topLeft())
        self._content.render(painter, context)
        painter.restore()

    def hoverEnterEvent(self, event):
        self._hovered = True
        print("Hover was toggled on")
        self.update()

    def hoverLeaveEvent(self, event):
        self._hovered = False
        print("Hover was toggled off")
        self.update()