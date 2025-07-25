from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Any, TYPE_CHECKING
from enum import Enum, auto
import json
from PySide6.QtWidgets import QGraphicsObject, QGraphicsItem, QStyleOptionGraphicsItem
from PySide6.QtCore import Qt, QRectF, QPointF, QSizeF, QMarginsF, Signal
from PySide6.QtGui import QPainter, QPixmap, QColor, QImage, QPen, QBrush,  QPageLayout, QPageSize
from prototypyside.models.text_element import TextElement
from prototypyside.models.component_template import ComponentTemplate
from prototypyside.models.image_element import ImageElement
from prototypyside.utils.unit_converter import to_px, page_in_px, page_in_units, compute_scale_factor
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.ustr_helpers import geometry_with_px_rect, geometry_with_px_pos
from prototypyside.config import PAGE_SIZES, DISPLAY_MODE_FLAGS, PAGE_UNITS
from prototypyside.utils.proto_helpers import get_prefix, resolve_pid
if TYPE_CHECKING:
    from prototypyside.services.proto_registry import ProtoRegistry

class LayoutSlot(QGraphicsObject):
    item_changed = Signal()
    def __init__(self, pid, geometry, registry, row=0, column=0, parent=None):
        super().__init__(parent)
        self._registry = registry
        self._pid = pid
        self._tpid = None # This will hold a reference to the template which will be instanced to fill it.
        self._hovered = False
        self._geometry = geometry
        self._row = row
        self._column = column
        self._content = None
        self._unit = "px"
        self._dpi = 300
        self._display_flag = DISPLAY_MODE_FLAGS.get("stretch").get("aspect")
        self._cache_image = None
        self._geometry = geometry
        self._render_text = True
        self.setAcceptHoverEvents(True)

    # --- Geometric Property Getter/Setters ---#
    @property
    def registry(self):
        return self._registry
    
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
    def unit(self) -> str:
        return self._unit

    @unit.setter
    def unit(self, new: str):
        if self._unit != new:
            self._unit = new
            for item in self.content:
                item.unit = new

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

    def boundingRect(self) -> QRectF:
        return self._geometry.to(self.unit, dpi=self.dpi).rect

    # This method is for when ONLY the rectangle (size) changes,
    # not the position.
    def setRect(self, new_rect: QRectF):
        if self._geometry.to(self.unit, dpi=self.dpi).rect == new_rect:
            return
        self.prepareGeometryChange()
        geometry_with_px_rect(self._geometry, new_rect, dpi=self.dpi)
        # self.update()

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

        # It's crucial to call the base class implementation. This will update geometry.
        # If other signals are emitted or updates called for, it breaks the undo stack.
        return super().itemChange(change, value)

    # --- Addiontal Property Getter/Setters ---#
    @property
    def pid(self) -> str:
        return self._pid

    @pid.setter
    def pid(self, value):
        self._pid = value

    @property
    def tpid(self) -> str: return self._tpid

    def tpid(self, value):
        if self._tpid != value:
            self._tpid = value
            self.template_changed.emit()

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
    def content(self):
        return self._content

    @content.setter
    def content(self, obj):
        self._content = obj

        ### Next 4 lines are DEBUGGING ONLY 
        geometry = self.geometry if isinstance(self._content, ComponentTemplate) else None
        if geometry:
            print(f"Slot {self._pid} has content sized: {geometry.rect.width()}x{geometry.rect.height()}")
        # print(f"Slot content items are {self._content.items}")
        self.invalidate_cache()
        self.update()

    @property
    def image(self):
        if self._cache_image is None:
            self._cache_image = self._render_to_image()
        return self._cache_image
        
    @property 
    def display_flag(self):
        return self._display_flag

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

    @display_flag.setter
    def display_flag(self, qflag):
        if qflag != self._display_flag:
            self._display_flag = qflag

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()

    def paint(self, painter, option, widget=None):
        """
        Paints the layout slot including its border, hover state, and rendered content
        (if any). The rendered content is drawn using unit-scaled QImage.

        Parameters:
            painter: QPainter used by the scene or exporter
            option: QStyleOptionGraphicsItem from the scene
            widget: Optional widget context (unused)
            unit (str): 'px', 'in', 'mm', etc.
            dpi (int): Dots-per-inch used for physical unit conversion
        """
        rect = self.geometry.to(self.unit, dpi=self.dpi).rect

        # --- Base fill and border ---
        fill = QBrush(QColor(230, 230, 230, 80))
        border = QPen(QColor(80, 80, 80), 1)
        painter.setPen(border)
        painter.setBrush(fill)
        painter.drawRect(rect)

        # --- Hover overlay ---
        if self._hovered:
            painter.setBrush(QBrush(QColor(70, 120, 240, 120)))
            painter.setPen(Qt.NoPen)
            painter.drawRect(rect)

        # --- Placeholder if no content ---
        if self._content is None:
            pen = QPen(QColor(100, 100, 100, 120), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)
            return

        # --- Content rendering ---
        if self._cache_image is None:
            self._cache_image = self._render_to_image()

        painter.drawImage(rect, self._cache_image)


    def _render_to_image(self):
        """
        Renders the content (ComponentTemplate) of this slot to an offscreen image.

        This image is DPI-aware and scaled based on the logical unit.
        """
        rect = self.geometry.to(self.unit, dpi=self.dpi).rect
        # The value has to be greater than 0 but can't be 1 if we're dealing with physical units
        w, h = max(.01, int(rect.width())), max(.01, int(rect.height()))

        option = QStyleOptionGraphicsItem()
        image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)

        img_painter = QPainter(image)
        img_painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        # Align drawing to image origin
        img_painter.translate(-rect.topLeft())

        # Render template background + border

        self._content.paint(img_painter, option)

        # Render elements in z-order
        for item in sorted(self._content.items, key=lambda e: e.zValue()):
            if not self.render_text and isinstance(item, TextElement):
                pass ### Instead we'll draw it at export as vector.
            img_painter.save()
            img_painter.translate(item.pos())

            item_bounds = item.boundingRect()
            img_painter.setClipRect(QRectF(0, 0, item_bounds.width(), item_bounds.height()))

            # rotation = getattr(item, "rotation", lambda: 0)()
            # if rotation:
            #     img_painter.rotate(rotation)

            item.paint(img_painter, option, widget=None)
            img_painter.restore()

        return image

    #### COMMENTING OUT JUST UNTIL I MAKE SURE THEY'RE NOT BEING MYSTERIOUSLY USED ELSEWHERE
    # def _render_items(self, painter: QPainter) -> None:
    #     """
    #     Paints every item inside this slot's content template onto the given QPainter.

    #     - The painter is assumed to be pre-scaled for physical units (e.g., 1 inch = dpi pixels).
    #     - All geometry values should be used in logical units (from `UnitStrGeometry.to(self.unit, dpi)`).
    #     - Items are drawn in z-order (lowest to highest).
    #     - Each item's own `paint(...)` method is reused to support custom rendering.

    #     Parameters
    #     ----------
    #     painter : QPainter
    #         A painter already set up and scaled to match the target export resolution.
    #     unit : str
    #         The logical unit system (e.g., 'px', 'in', 'mm'). Used for size/position.
    #     dpi : int
    #         The dots-per-inch to convert units into physical pixels.
    #     """
    #     option = QStyleOptionGraphicsItem()

    #     # Draw background/border of template itself
    #     self._content.paint(painter, option, widget=None)

    #     # Draw each item in z-order
    #     for item in sorted(self._content.items, key=lambda e: e.zValue()):
    #         painter.save()

    #         # Logical position of the item in the template
    #         pos = item.geometry.to(self.unit, dpi=self.dpi).pos
    #         painter.translate(pos.x(), pos.y())

    #         # Optional rotation
    #         rotation = getattr(item, "rotation", lambda: 0)()
    #         if rotation:
    #             painter.rotate(rotation)

    #         # Delegate to the item's own unit-aware paint method
    #         item.paint(painter, option, widget=None)

    #         painter.restore()

    # def _render_background(self, painter: QPainter):
    #     """
    #     Draw the background color or image for this slot's content template.

    #     Parameters
    #     ----------
    #     painter : QPainter
    #         A QPainter instance already aligned with the page coordinate system.
    #     unit : str
    #         Logical unit system (e.g., 'px', 'in', 'mm') for resolution conversion.
    #     dpi : int
    #         Dots-per-inch to convert unit-based geometry to physical pixels.
    #     """
    #     rect = self.geometry.to(self.unit, dpi=self.dpi).rect

    #     bg_color = getattr(self._content, "background_color", None)
    #     bg_image_path = getattr(self._content, "background_image", None)

    #     if bg_color:
    #         painter.fillRect(rect, QColor(bg_color))

    #     if bg_image_path:
    #         pixmap = QPixmap(bg_image_path)
    #         if not pixmap.isNull():
    #             painter.drawPixmap(rect, pixmap, pixmap.rect())

    def invalidate_cache(self):
        self._cache_image = None
        self.update()

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
            "content": content_data
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        registry: "ProtoRegistry",
        is_clone: bool = False,
    ) -> "LayoutSlot":
        """
        Hydrate or clone a LayoutSlot. Regenerates pid on clone,
        restores geometry, flags, and re‐registers in the registry.
        """
        # PID logic
        pid = resolve_pid("ls") if is_clone else data.get("pid")

        # Geometry
        geom = UnitStrGeometry.from_dict(data.get("geometry"))

        # Instantiate with registry set explicitly
        inst = cls(
            pid=pid,
            geometry=geom,
            registry=registry,
            row=data.get("row", 0),
            column=data.get("column", 0),
            parent=None,
        )
        
        # Assign registry immediately after instantiation
        inst._registry = registry

        # Rehydrate content explicitly after setting registry
        content_data = data.get("content", None)
        if content_data:
            content_template = ComponentTemplate.from_dict(content_data, registry=registry, is_clone=is_clone)
            inst.content = content_template

        # Restore display flags if needed
        inst._display_flag = data.get("display_flag", inst._display_flag)

        # Register the fully initialized instance at the end
        registry.register(inst)

        return inst
