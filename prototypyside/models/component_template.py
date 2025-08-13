# component_template.py
from PySide6.QtCore import Qt, QObject, QRectF, QPointF, Signal # Import QObject and Signal
from PySide6.QtGui import QPainter, QPixmap, QColor, QImage, QBrush, QPen, QPainterPath
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject
from typing import List, Dict, Any, Optional, Callable, TYPE_CHECKING
import csv
import json
from pathlib import Path
from PySide6.QtWidgets import QMessageBox
import weakref
import gc
import traceback
from prototypyside.services.shape_factory import ShapeFactory
from prototypyside.models.component_element import ComponentElement
from prototypyside.models.image_element import ImageElement
from prototypyside.models.text_element import TextElement
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.units.unit_str_helpers import geometry_with_px_pos, geometry_with_px_rect
from prototypyside.utils.proto_helpers import get_prefix, resolve_pid
# Use TYPE_CHECKING for type hinting
if TYPE_CHECKING:
    from prototypyside.services.proto_registry import ProtoRegistry


class ComponentTemplate(QGraphicsObject):
    template_changed = Signal()
    item_z_order_changed = Signal()
    item_name_change = Signal()

    def __init__(
        self,
        pid: str,
        geometry: UnitStrGeometry = UnitStrGeometry(width="2.5in", height="3.5in", unit="in", dpi=300),
        shape_factory: Callable[[QRectF], QPainterPath] = None,
        parent=None,
        name: Optional[str] = None,
        registry=None,
        shape="rounded_rectangle",
        corner_radius: UnitStr = UnitStr("0.125in", unit="in", dpi=300),
        border_width: UnitStr = UnitStr("0.125in", unit="in", dpi=300),
        bleed=UnitStr("0.125in", unit="in", dpi=300)
    ):
        super().__init__(parent)
        self.pid = pid
        self.tpid = None
        self._name = name
        self.registry = registry

        # Unit geometry
        self._geometry = geometry
        self._dpi = 300
        self._unit = "px"

        # Shape path generator
        self._shape_factory = shape_factory or self._default_shape_factory

        # Visual properties
        self._corner_radius = corner_radius
        self._border_width = border_width
        self._bleed = bleed
        self._enable_bleed = False
        self._border_color = QColor(Qt.black)
        self._bg_color = QColor(Qt.white)
        self._background_image: Optional[Path] = None
        self._shape = QPainterPath  
        # Children
        self.items: List[ComponentElement] = []

        self._csv_path = None

    # ——— Shape Factory ———
    def _default_shape_factory(self, rect: QRectF) -> QPainterPath:
        path = QPainterPath()
        radius = self._corner_radius.to(self._unit, dpi=self._dpi)
        if radius > 0:
            path.addRoundedRect(rect, radius, radius)
        else:
            path.addRect(rect)
        return path

    # ——— Properties & Setters ———
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
            for item in self.items:
                item.unit = self._unit

    @property
    def unit(self) -> str:
        return self._unit

    @unit.setter
    def unit(self, new: str):
        if self._unit != new:
            self._unit = new
            for item in self.items:
                item.unit = self._unit

    @property
    def geometry(self):
        return self._geometry

    @geometry.setter
    def geometry(self, new_geom: UnitStrGeometry):
        if self._geometry == new_geom:
            return

        self.prepareGeometryChange()
        self._geometry = new_geom
        super().setPos(self._geometry.px.pos)
        if not self.tpid:
            self.template_dimensions_changed.emit()
        self.update()

    @property
    def width(self): return self._geometry.width

    @width.setter
    def width(self, value: UnitStr):
        if value != self._geometry.width:
            h = self._geometry.height
            self.geometry = UnitStrGeometry(width=value, height=height, unit=self._unit, dpi=self._dpi)

    @property
    def height(self): return self._geometry.height

    @height.setter
    def height(self, value: UnitStr):
        if value != self._geometry.height:
            print(f"Adjusting height to {value}")
            w = self._geometry.width
            self.geometry = UnitStrGeometry(width=w, height=value, unit=self._unit, dpi=self._dpi)

    def setRect(self, new_rect: QRectF):
        # Do not emit signals here. setRect shouldn't be called directly.
        if self._geometry.px.rect == new_rect:
            return
        self.prepareGeometryChange()
        geometry_with_px_rect(self._geometry, new_rect, dpi=self.dpi)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        if change == QGraphicsItem.ItemPositionChange and value != self.pos():
            # Block signals to prevent a recursive loop if a connected item
            # also tries to set the position.
            signals_blocked = self.signalsBlocked()
            self.blockSignals(True)
            geometry_with_px_pos(self._geometry, value, dpi=self.dpi)
            self.blockSignals(signals_blocked)

        # If other signals are emitted or updates called for, it breaks the undo stack.
        return super().itemChange(change, value)

    # ——— Bounding Rect ———
    def boundingRect(self) -> QRectF:
        # Use pixel dimensions for scene, so convert geometry to pixels directly
        base_rect: QRectF = self._geometry.px.rect
        # Build the shape in pixel coords
        shape: QPainterPath = self._shape_factory(base_rect)
        if self._enable_bleed:
            bleed_px = self._bleed.to("px", dpi=self._dpi)
            br = shape.boundingRect()
            return QRectF(
                br.x() - bleed_px,
                br.y() - bleed_px,
                br.width() + 2 * bleed_px,
                br.height() + 2 * bleed_px
            )
        return shape.boundingRect()

    # allows dynamic shape transformation of components
    @property
    def shape_factory(self) -> Callable[[QRectF], QPainterPath]:
        """Get or set the shape factory to change the component shape on the fly."""
        return self._shape_factory

    @shape_factory.setter
    def shape_factory(self, factory: Callable[[QRectF], QPainterPath]):
        if self._shape_factory == factory:
            return
        self.prepareGeometryChange()
        self._shape_factory = factory
        self.update()

    @property
    def enable_bleed(self) -> bool:
        return self._enable_bleed

    @enable_bleed.setter
    def enable_bleed(self, val: bool):
        if self._enable_bleed == val:
            return
        self.prepareGeometryChange()
        self._enable_bleed = val
        self.update()

    @property
    def bg_color(self) -> QColor:
        return QColor(self._bg_color)

    @bg_color.setter
    def bg_color(self, val):
        if isinstance(val, QColor):
            c = val
        else:
            c = QColor(val)
        if c != self._bg_color:
            self._bg_color = c
            self.update()

    @property
    def background_image(self) -> Optional[str]:
        return str(self._background_image) if self._background_image else None

    @background_image.setter
    def background_image(self, path):
        if not path:
            self._background_image = None
        else:
            p = Path(path)
            self._background_image = p if p.exists() else None
        self.update()

    @property
    def border_width(self):
        return self._border_width

    @border_width.setter
    def border_width(self, value):
        if value != self._border_width:
            self._border_width = value
            self.update()

    @property
    def corner_radius(self):
        return self._corner_radius

    @corner_radius.setter
    def corner_radius(self, value: UnitStr):
        if value != self._corner_radius:
            self._corner_radius = value
            self.update()
    
    @property
    def csv_path(self):
        return self._csv_path

    @csv_path.setter
    def csv_path(self, value):
        if value != self._csv_path:
            try:
                path = Path(value)
                self._csv_path = path
                self.template_changed.emit()
                self.update()
            except Exception:
                self._csv_path = None

    def add_item(self, item):
        item.nameChanged.connect(self.item_name_change)
        
        if item.pid in self.registry.orphans():
            self.registry.reinsert(item.pid)
        elif not self.registry.get(item.pid):
            self.registry.register(item)
        max_z = max([e.zValue() for e in self.items], default=0)
        item.setZValue(max_z + 100)
        self.items.append(item)
        self.item_z_order_changed.emit()

    def remove_item(self, item: 'ComponentElement'):
        if item in self.items:
            self.items.remove(item)
            self.template_changed.emit()
            self.item_z_order_changed.emit()
            self.registry.deregister(item)

    def reorder_item_z(self, item: 'ComponentElement', direction: int):
        if item not in self.items:
            return

        # Create a stable ordering using indices as secondary key
        sorted_items = sorted(
            enumerate(self.items),
            key=lambda x: (x[1].zValue(), x[0])
        )
        
        # Find current position
        current_idx = next((i for i, (idx, e) in enumerate(sorted_items) if e is item), -1)
        if current_idx == -1:
            return

        # Calculate new position
        new_idx = current_idx + direction
        
        # Validate move boundaries
        if new_idx < 0 or new_idx >= len(sorted_items):
            return

        # Get adjacent item
        adj_item = sorted_items[new_idx][1]
        
        # Swap z-values using robust method
        current_z = item.zValue()
        adj_z = adj_item.zValue()
        
        # Handle z-value collisions
        if direction > 0:
            new_z = adj_z + 1
        else:
            new_z = adj_z - 1
        
        # Apply new z-values
        item.setZValue(new_z)
        adj_item.setZValue(current_z)
        
        # Maintain unique z-values by resetting the entire stack
        self._normalize_z_values()
        self.item_z_order_changed.emit()
        if not self.tpid:
            self.template_changed.emit()

    def _normalize_z_values(self):
        """Ensure all items have unique, ordered z-values"""
        # Sort by current z-value
        sorted_items = sorted(self.items, key=lambda e: e.zValue())
        
        # Assign new values with fixed increments
        for z_value, el in enumerate(sorted_items, start=100):
            el.setZValue(z_value * 100)  # Fixed increment of 100
        
        # Sort internal list to match new order
        self.items.sort(key=lambda e: e.zValue())

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        # Draw everything in pixel coordinates
        geom_px = self._geometry.px
        base_rect: QRectF = geom_px.rect
        # 0) generate shape path in pixels
        shape: QPainterPath = self._shape_factory(base_rect)

        # 1) Bleed area (if enabled)
        if self._enable_bleed:
            bleed_px = self._bleed.to("px", dpi=self._dpi)
            ble_rect = shape.boundingRect().adjusted(-bleed_px, -bleed_px, bleed_px, bleed_px)
            thickness_px = self._border_width.to("px", dpi=self._dpi)
            painter.save()
            painter.setPen(QPen(Qt.black, thickness_px))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(ble_rect)
            painter.restore()

        # 2) Background clipped to shape
        painter.save()
        painter.setClipPath(shape)
        painter.setPen(Qt.NoPen)
        if self._background_image:
            img = QImage(str(self._background_image))
            if not img.isNull():
                painter.drawImage(shape.boundingRect(), img)
            else:
                painter.fillPath(shape, QBrush(self._bg_color))
        else:
            painter.fillPath(shape, QBrush(self._bg_color))
        painter.restore()

        # 3) Border drawn fully inside base_rect
        if self._border_width.value > 0:
            thickness_px = self._border_width.to("px", dpi=self._dpi)
            half_thick = thickness_px / 2.0
            # Inset rect by half the stroke to keep stroke inside
            inner_rect = base_rect.adjusted(
                half_thick, half_thick,
                -half_thick, -half_thick
            )
            # Compute adjusted corner radius (in px)
            if isinstance(self._corner_radius, UnitStr):
                orig_rad = self._corner_radius.to("px", dpi=self._dpi)
            else:
                orig_rad = float(self._corner_radius)
            adj_rad = max(0.0, orig_rad - half_thick)
            # Choose path: rounded rect for default, or shrink generic shape
            if self._shape_factory == self._default_shape_factory:
                border_shape = QPainterPath()
                border_shape.addRoundedRect(inner_rect, adj_rad, adj_rad)
            else:
                border_shape = self._shape_factory(inner_rect)
            painter.save()
            painter.setBrush(Qt.NoBrush)
            pen = QPen(Qt.black, thickness_px)
            painter.setPen(pen)
            painter.drawPath(border_shape)
            painter.restore()


# class ComponentTemplate(QGraphicsObject):
#     template_changed = Signal()
#     item_z_order_changed = Signal()

#     # border_width width and corner_radius are set based on a standard MTG card
#     def __init__(self, pid, geometry=UnitStrGeometry(width="2.5in", height="3.5in", dpi=300), parent = None, 
#         name=None, registry=None, corner_radius=UnitStr("0.125in", dpi=300), border_width=UnitStr("0.125in", dpi=300)):
#         super().__init__(parent)
#         self.tpid = None
#         self.lpid = None
#         self._path = None
#         # associated layouts if any
#         self._layouts = []
#         self._pid = pid
#         self._name = name
#         self._registry = registry
#         self._geometry = geometry
#         self._dpi = 300
#         self._unit = "px"
#         self._corner_radius = corner_radius
#         self.items: List['ComponentElement'] = []
#         self._bleed = UnitStr("0.125in", unit=self._unit, dpi=self._dpi)
#         self._enable_bleed = False
#         self._bg_color = Qt.white
#         self._background_image: Optional[str] = None
#         self._border_width = border_width
#         self._corner_radius = corner_radius
#         self._csv_row = []
#         self._csv_path: Path = None 
#         self.content = None

#     @property
#     def name(self):
#         return self._name

#     @name.setter
#     def name(self, value):
#         if self._name != value:
#             self._name = value
    
#     @property
#     def tpid(self):
#         return self.tpid if self.tpid else None

#     @tpid.setter
#     def tpid(self, pid):
#         if self.tpid != pid:
#             self.tpid = pid

#     @property
#     def registry(self):
#         return self._registry

#     @property
#     def pid(self) -> str:
#         return self._pid

#     @pid.setter
#     def pid(self, value):
#         self._pid = value
#         self.template_changed.emit()

#     @property
#     def csv_path(self):
#         return self._csv_path

#     @csv_path.setter
#     def csv_path(self, value):
#         if value != self._csv_path:
#             try:
#                 path = Path(value)
#                 self._csv_path = path
#             except Exception:
#                 self._csv_path = None
                




#     @bg_color.setter
#     def bg_color(self, val):
#         if self._bg_color != val:
#             self._bg_color = val
#             self.update()

#     def boundingRect(self) -> QRectF:
#         base = self.geometry.to(self.unit, dpi=self.dpi).rect

#         if self._enable_bleed:
#             bleed = self._bleed.to(self.unit, dpi=self.dpi)
#             return QRectF(
#                 base.x() - bleed,
#                 base.y() - bleed,
#                 base.width()  + 2 * bleed,
#                 base.height() + 2 * bleed
#             )

#         return base


#     # This method is for when ONLY the rectangle (size) changes,
#     # not the position.


#     @property
#     def bleed(self):
#         return self._bleed

#     @bleed.setter
#     def bleed(self, new):
#         self._bleed = new if self._bleed != new else self,_bleed
#         self.update()
    
#     @property
#     def width(self):
#         return self._geometry.px.width

#     @property
#     def height(self):
#         return self._geometry.px.height

#     @property
#     def corner_radius(self):
#         return self._corner_radius

#     @corner_radius.setter
#     def corner_radius(self, value:bool):
#         if self._corner_radius != value:
#             self._corner_radius = value
#             self.template_changed.emit()
#             self.update()

#     @property
#     def border_width(self):
#         return self._border_width

#     @border_width.setter
#     def border_width(self, value):
#         if self._border_width != value:
#             self._border_width = value
#             self.template_changed.emit()




#     def update_from_template(self, tpid):
#         if not self.tpid:
#             return
#         registry = self._registry
#         template = self.global_get(tpid)
#         self.geometry = template.geometry
#         self.items = [registry.clone(el) for el in template.items]




#     @property
#     def background_image(self):
#         return self._background_image

#     @background_image.setter
#     def background_image(self, path):
#         if not path:
#             self._background_image = None
#             return

#         path = Path(path)  # Only now that we know it's not None
#         if path.exists():
#             self._background_image = path
#             if not self.tpid:
#                 self.template_changed.emit()
#             self.update()
#         else:
#             self._background_image = None
#             print(f"[Warning] Background image not found: {path}")

#     def apply_row_data(self, row_data):
#         for item in [i for i in items if i.name.startswith("@")]:
#             setattr(i, "content", row_data.get(i.name))

    # def _draw_bleed_area(self, painter: QPainter, rect: QRectF):
    #     bleed = self._bleed.to(self.unit, dpi=self.dpi)
    #     bleed_rect = QRectF(
    #         rect.x() - bleed,
    #         rect.y() - bleed,
    #         rect.width() + 2 * bleed,
    #         rect.height() + 2 * bleed
    #     )

    #     # Rule 1: if border, stroke border around bleed_rect
    #     if self.border_width.value > 0:
    #         thickness = self.border_width.to(self.unit, dpi=self.dpi)
    #         inset = thickness / 2.0
    #         inner = bleed_rect.adjusted(inset, inset, -inset, -inset)
    #         max_radius = min(inner.width(), inner.height()) / 2.0
    #         radius = max(0.0, min(
    #             self._corner_radius.to(self.unit, dpi=self.dpi) - inset,
    #             max_radius
    #         ))

    #         path = QPainterPath()
    #         if radius > 0:
    #             path.addRoundedRect(inner, radius, radius)
    #         else:
    #             path.addRect(inner)

    #         painter.setPen(QPen(Qt.black, thickness))
    #         painter.setBrush(Qt.NoBrush)
    #         painter.drawPath(path)

    #     # Rule 2: background_image but no border
    #     elif self.background_image:
    #         img = QImage(self.background_image)
    #         if not img.isNull():
    #             painter.drawImage(bleed_rect, img)

    #     # Rule 3: neither border nor bg image, but bg_color
    #     elif self.bg_color:
    #         painter.fillRect(bleed_rect, QColor(self.bg_color))

    # # ——— 4. updated paint() ———
    # def paint(self, painter: QPainter, option, widget=None):
    #     painter.setRenderHint(QPainter.Antialiasing)
    #     rect = self.geometry.to(self.unit, dpi=self.dpi).rect

    #     # ——— Bleed ———
    #     if self._enable_bleed:
    #         painter.save()
    #         # no clipping here so we can draw outside `rect`
    #         self._draw_bleed_area(painter, rect)
    #         painter.restore()

    #     # ——— Background ———
    #     painter.save()
    #     painter.setClipRect(rect)
    #     painter.setPen(Qt.NoPen)

    #     if self.background_image:
    #         img = QImage(self.background_image)
    #         if not img.isNull():
    #             painter.drawImage(rect, img)
    #         else:
    #             painter.fillRect(rect, QColor(self.bg_color) if self.bg_color else Qt.white)
    #     else:
    #         painter.fillRect(rect, QColor(self.bg_color) if self.bg_color else Qt.white)
    #     painter.restore()

    #     # ——— Border ———
    #     if self.border_width.value > 0:
    #         painter.save()
    #         painter.setBrush(Qt.NoBrush)

    #         thickness = self.border_width.to(self.unit, dpi=self.dpi)
    #         inset = thickness / 2.0
    #         inner = QRectF(
    #             rect.x() + inset,
    #             rect.y() + inset,
    #             rect.width() - thickness,
    #             rect.height() - thickness
    #         )

    #         max_radius = min(inner.width(), inner.height()) / 2.0
    #         radius = max(0.0, min(
    #             self.corner_radius.to(self.unit, dpi=self.dpi) - inset,
    #             max_radius
    #         ))

    #         path = QPainterPath()
    #         if radius > 0:
    #             path.addRoundedRect(inner, radius, radius)
    #         else:
    #             path.addRect(inner)

    #         painter.setPen(QPen(Qt.black, thickness))
    #         painter.drawPath(path)
    #         painter.restore()
#     # def paint(self, painter: QPainter, option, widget=None):
#     #     """
#     #     Paints the template's background and border_width using the specified unit and dpi.

#     #     Parameters:
#     #         painter (QPainter): Painter object used by the scene or exporter.
#     #         option: QStyleOptionGraphicsItem from the scene (unused).
#     #         widget: Optional QWidget; unused.
#     #     """
#     #     rect = self.geometry.to(self.unit, dpi=self.dpi).rect
#     #     painter.setRenderHint(QPainter.Antialiasing)

#     #     # ——— Background ———
#     #     painter.save()
#     #     painter.setClipRect(rect)
#     #     painter.setPen(Qt.NoPen)

#     #     if self.background_image:
#     #         img = QImage(self.background_image)
#     #         if not img.isNull():
#     #             # Scales image to fill the rect while preserving aspect if needed
#     #             painter.drawImage(rect, img)
#     #         else:
#     #             painter.fillRect(rect, Qt.white)
#     #     else:
#     #         painter.fillRect(rect, Qt.white)
#     #     painter.restore()

#     #     # ——— Border ———
#     #     if self.border_width.value > 0:
#     #         painter.save()
#     #         painter.setBrush(Qt.NoBrush)

#     #         # Convert border_width thickness to unit
#     #         thickness = self.border_width.to(self.unit, dpi=self.dpi)
#     #         inset = thickness / 2.0

#     #         inner = QRectF(
#     #             rect.x() + inset,
#     #             rect.y() + inset,
#     #             rect.width() - thickness,
#     #             rect.height() - thickness
#     #         )

#     #         # Clamp the radius to avoid exceeding available space
#     #         max_radius = min(inner.width(), inner.height()) / 2.0
#     #         radius = max(0.0, min(self.corner_radius.to(self.unit, dpi=self.dpi) - inset, max_radius))

#     #         # Rounded or regular rect
#     #         path = QPainterPath()
#     #         if radius > 0.0:
#     #             path.addRoundedRect(inner, radius, radius)
#     #         else:
#     #             path.addRect(inner)

#     #         painter.setPen(QPen(Qt.black, thickness))
#     #         painter.drawPath(path)
#     #         painter.restore()


    def to_dict(self) -> Dict[str, Any]:
        print(f"serializing {self.pid}")
        data = {
            'pid': self.pid,
            'name': self.name,
            'geometry': self._geometry.to_dict(),
            'bg_color': self._bg_color.rgba(),
            'border_color': self._border_color.rgba(),
            'background_image': str(self.background_image) if self.background_image else None,
            'items': [e.to_dict() for e in self.items],
            'border_width': self.border_width.to_dict(),
            'corner_radius': self.corner_radius.to_dict(),
            'bleed': self._bleed.to_dict(),
            'csv_path': str(self.csv_path) if self.csv_path and Path(self.csv_path).exists else None,
            'tpid': self.tpid
        }
        return data

    @classmethod
    def from_dict(
        cls,
        data: dict,
        registry: "ProtoRegistry",
        is_clone: bool = False,
    ) -> "ComponentTemplate":
        # 1) Core properties & PID

        pid = resolve_pid("cc") if is_clone else data["pid"]
        geom = UnitStrGeometry.from_dict(data["geometry"])
        print("Rehydrating Template")
        inst = cls(
            pid=pid,
            registry=registry,
            geometry=geom,
            name=data.get("name"),
            border_width=UnitStr.from_dict(data.get("border_width")),
            corner_radius=UnitStr.from_dict(data.get("corner_radius")),
            bleed=UnitStr.from_dict(data.get("bleed"))
        )
        print("Made it past instancing")
        inst.tpid = data.get("pid") if is_clone else None
        csv_path = data.get("csv_path")
        inst.csv_path = Path(csv_path) if csv_path else None
        bg_color = data.get("bg_color", None)
        border_color = data.get("border_color", None)
        bleed = data.get("bleed")
        inst._bleed = UnitStr.from_dict(data.get("bleed")) if bleed else UnitStr("0.125 in", "in", dpi=300)
        inst._bg_color = QColor.fromRgba(bg_color) if bg_color else None
        inst._border_color = QColor.fromRgba(border_color) if border_color else None
        registry.register(inst)
        inst.name = registry.generate_name(inst)
        # 3) Child elements (images/text)
        inst.items = []
        for e in data.get("items", []):
            prefix = get_prefix(e.get("pid"))
            if prefix == "ie":
                el = ImageElement.from_dict(e, registry=registry, is_clone=is_clone)
            elif prefix == "te":
                el = TextElement.from_dict(e, registry=registry, is_clone=is_clone)
            elif prefix == "ve":
                from prototypyside.models.vector_element import VectorElement
                el = VectorElement.from_dict(e, registry=registry, is_clone=is_clone)
            else:
                raise ValueError(f"Unknown prefix {prefix}")
            inst.add_item(el)
            el.setParentItem(inst)

            
        return inst
