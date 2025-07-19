# component_template.py

from PySide6.QtCore import Qt, QObject, QRectF, QPointF, Signal # Import QObject and Signal
from PySide6.QtGui import QPainter, QPixmap, QColor, QImage, QBrush, QPen, QPainterPath
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject
from typing import List, Dict, Any, Optional, TYPE_CHECKING
import csv
import json
from pathlib import Path
from PySide6.QtWidgets import QMessageBox
<<<<<<< Updated upstream

from prototypyside.models.component_elements import ImageElement, TextElement
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
=======
from prototypyside.models.component_template_model import ComponentTemplateModel
from prototypyside.models.component_elements import ImageElement, TextElement
from prototypyside.utils.unit_str import UnitStr
from prototypyside.utils.unit_str_geometry import UnitStrGeometry
>>>>>>> Stashed changes
from prototypyside.utils.ustr_helpers import geometry_with_px_pos, geometry_with_px_rect
from prototypyside.utils.proto_helpers import get_prefix, issue_pid
# Use TYPE_CHECKING for type hinting
if TYPE_CHECKING:
    from prototypyside.services.proto_registry import ProtoRegistry


class ComponentTemplate(QGraphicsObject):
    template_changed = Signal()
    item_z_order_changed = Signal()
    property_update = Signal(str, str, dict)  # (tpid, target_pid, packet(dict))
    structure_changed = Signal(str)                     # (tpid)

    # border width and corner_radius are set based on a standard MTG card
    def __init__(self, pid, geometry=UnitStrGeometry(width="2.5in", height="3.5in"), parent = None, 
        name=None, registry=None, corner_radius=UnitStr("0.125in"), border=UnitStr("0.125in")):
        super().__init__(parent)
        self._tpid = None
        self.lpid = None
        self._path = None
        # associated layouts if any
        self._layouts = []
        self._pid = pid
        self._name = name
        self._registry = registry
        self._geometry = geometry
        self._dpi = 144
        self._unit = "px"
        self._pixmap = None
        self.items: List['ComponentElement'] = []
        self._background_image: Optional[str] = None
        self._border = border
        self._corner_radius = corner_radius
        self._csv_row = []
        self._csv_path: Path = None 
        self.content = None
        self.registry.object_registered.connect(self.add_item)

    @property
    def tpid(self):
        return self._tpid if self._tpid else None

    @tpid.setter
    def tpid(self, pid):
        if self._tpid != pid:
            self._tpid = pid

    @property
    def registry(self):
        return self._registry

    @property
    def pid(self) -> str:
        return self._pid

    @pid.setter
    def pid(self, value):
        self._pid = value
        self.template_changed.emit()

    @property
    def csv_path(self):
        return self._csv_path

    @csv_path.setter
    def csv_path(self, value):
        if value is None:
            self._csv_path = None
        else:
            path_value = Path(value)
            if path_value != self._csv_path:
                self._csv_path = path_value
                
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
        # print(f"[SETTER] geometry called with {new_geom}")
        if self._geometry == new_geom:
            # print("[SETTER] geometry unchanged")
            return

        self.prepareGeometryChange()
        # print(f"[SETTER] prepareGeometryChange called")
        # print(f"[SETTER] pos set to {self._geometry.px.pos}")
        self._geometry = new_geom
        super().setPos(self._geometry.px.pos)
        if not self.tpid:
            self.template_updated.emit(self.tpid)
        self.update()

    def boundingRect(self) -> QRectF:
        return self._geometry.px.rect

    # This method is for when ONLY the rectangle (size) changes,
    # not the position.
    def setRect(self, new_rect: QRectF):
        # Do not emit signals here. setRect shouldn't be called directly.
        if self._geometry.px.rect == new_rect:
            return
        self.prepareGeometryChange()
        geometry_with_px_rect(self._geometry, new_rect)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        # This is called when the scene moves the item.
        if change == QGraphicsItem.ItemPositionChange and value != self.pos():
            # Block signals to prevent a recursive loop if a connected item
            # also tries to set the position.
            signals_blocked = self.signalsBlocked()
            self.blockSignals(True)
            geometry_with_px_pos(self._geometry, value)
            print(f"[ITEMCHANGE] Called with change={change}, value={value}")
            print(f"[ITEMCHANGE] Geometry.pos updated to: {self._geometry.px.pos}")
            self.blockSignals(signals_blocked)

        # It's crucial to call the base class implementation. This will update geometry.
        # If other signals are emitted or updates called for, it breaks the undo stack.
        return super().itemChange(change, value)

    @property
    def width(self):
        return self._geometry.px.width

    @property
    def height(self):
        return self._geometry.px.height

    @property
    def corner_radius(self):
        return self._corner_radius

    @corner_radius.setter
    def corner_radius(self, value:bool):
        if self._corner_radius != value:
            self._corner_radius = value
            self.template_changed.emit()
            self.update()

    @property
    def border(self):
        return self._border

    def add_item(self, item):
        if item in self.items:
            return
        self.items.append(item)
        max_z = max([e.zValue() for e in self.items], default=0)
        item.setZValue(max_z + 100)
        item.property_changed.connect(self.on_item_property_update)
        self.item_z_order_changed.emit()

    def receive_packet(self, packet: dict):
        action = packet.get("action", "set_property")
        if action == "set_property":
            prop = packet["property"]
            value = packet["new"]
            setattr(self, prop, value)
            # Optionally emit signal for UI/undo
            return True
        elif action == "add_item":
            item = packet["item"]
            self.add_item(item)
            return True
        else:
            print(f"[ComponentTemplate] Unknown action: {action} in packet {packet}")
            return False

    def on_item_property_update(self, prop, new, old):
        sender = self.pid
        target = self.lpid
        packet = {
            "pid": self.pid,
            "property": prop,
            "old": old,
            "new": new,
        }
        self.property_update.emit(sender, target, packet)

    def on_template_property_update(self, prop, new, old):
        self.send_packet_to_layout(prop, new, old)

    def send_packet_to_layout(self, prop, new, old):
        sender = self.pid
        target = self.lpid
        packet = {
            "pid": self.pid,
            "property": prop,
            "old": old,
            "new": new,
        }
        self.property_update.emit(sender, target, packet)

    def remove_item(self, item: 'ComponentElement'):
        if item in self.items:
            self.items.remove(item)
            self.template_changed.emit()
            self.item_z_order_changed.emit()
            if not self.tpid:
                self.template_updated.emit(self.tpid)

    def update_from_template(self, tpid):
        if not self.tpid:
            return
        registry = self._registry
        template = self.global_get(tpid)
        self.geometry = template.geometry
        self.items = [registry.clone(el) for el in template.items]


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
            self.template_updated.emit(self.tpid)

    def _normalize_z_values(self):
        """Ensure all items have unique, ordered z-values"""
        # Sort by current z-value
        sorted_items = sorted(self.items, key=lambda e: e.zValue())
        
        # Assign new values with fixed increments
        for z_value, el in enumerate(sorted_items, start=100):
            el.setZValue(z_value * 100)  # Fixed increment of 100
        
        # Sort internal list to match new order
        self.items.sort(key=lambda e: e.zValue())

    def bring_to_front(self, item: 'ComponentElement'):
        if item not in self.items:
            return
        
        # Set to max + increment
        max_z = max(e.zValue() for e in self.items)
        item.setZValue(max_z + 100)
        self._normalize_z_values()
        self.item_z_order_changed.emit()

    def send_to_back(self, item: 'ComponentElement'):
        if item not in self.items:
            return
        
        # Set to min - increment
        min_z = min(e.zValue() for e in self.items)
        item.setZValue(min_z - 100)
        self._normalize_z_values()
        self.item_z_order_changed.emit()

    @property
    def background_image(self):
        return self._background_image

    @background_image.setter
    def background_image(self, path):
        if not path:
            self._background_image = None
            return

        path = Path(path)  # Only now that we know it's not None
        if path.exists():
            self._background_image = path
            if not self.tpid:
                self.template_updated.emit(self.tpid)
            self.update()
        else:
            self._background_image = None
            print(f"[Warning] Background image not found: {path}")

    def paint(self, painter: QPainter, option, widget=None, unit='px', dpi=144):
        """
        Paints the template's background and border using the specified unit and dpi.

        Parameters:
            painter (QPainter): Painter object used by the scene or exporter.
            option: QStyleOptionGraphicsItem from the scene (unused).
            widget: Optional QWidget; unused.
            unit (str): Unit such as 'px', 'in', or 'mm'.
            dpi (int): Dots-per-inch resolution to use for physical units.
        """
        rect = self.geometry.to(self.unit, dpi=self.dpi).rect
        painter.setRenderHint(QPainter.Antialiasing)

        # ——— Background ———
        painter.save()
        painter.setClipRect(rect)
        painter.setPen(Qt.NoPen)

        if self.background_image:
            img = QImage(self.background_image)
            if not img.isNull():
                # Scales image to fill the rect while preserving aspect if needed
                painter.drawImage(rect, img)
            else:
                painter.fillRect(rect, Qt.white)
        else:
            painter.fillRect(rect, Qt.white)
        painter.restore()

        # ——— Border ———
        if self.border.value > 0:
            painter.save()
            painter.setBrush(Qt.NoBrush)

            # Convert border thickness to unit
            thickness = self.border.to(self.unit, dpi=self.dpi)
            inset = thickness / 2.0

            inner = QRectF(
                rect.x() + inset,
                rect.y() + inset,
                rect.width() - thickness,
                rect.height() - thickness
            )

            # Clamp the radius to avoid exceeding available space
            max_radius = min(inner.width(), inner.height()) / 2.0
            radius = max(0.0, min(self.corner_radius.to(self.unit, dpi=self.dpi) - inset, max_radius))

            # Rounded or regular rect
            path = QPainterPath()
            if radius > 0.0:
                path.addRoundedRect(inner, radius, radius)
            else:
                path.addRect(inner)

            painter.setPen(QPen(Qt.black, thickness))
            painter.drawPath(path)
            painter.restore()


    def to_dict(self) -> Dict[str, Any]:
        print("Is this serializing?")
        self._geometry
        self._border
        data = {
            'pid': self._pid,
            'name': self._name,
            'geometry': self._geometry.to_dict(),
            'background_image': str(self.background_image) if self.background_image else None,
            'items': [e.to_dict() for e in self.items],
            'border': self.border.to_dict(),
            'corner_radius': self.corner_radius.to_dict(),
            'csv_path': str(self._csv_path),
<<<<<<< Updated upstream
            'tpid': self._tpid
=======
            'template_pid': self._template_pid,
>>>>>>> Stashed changes
        }
        print(f"On save, name is {self._name}")
        return data

    @classmethod
    def from_dict(
        cls,
        data: dict,
        registry: "ProtoRegistry",
        is_clone: bool = False
    ) -> "ComponentTemplate":
        # 1) Core properties & PID
        pid = issue_pid("cc") if is_clone else data["pid"]
        geom = UnitStrGeometry.from_dict(data["geometry"])
        inst = cls(
            pid=pid,
            geometry=geom,
            name=(None if is_clone else data.get("name")),
            border=UnitStr.from_dict(data.get("border")),
            corner_radius=UnitStr.from_dict(data.get("corner_radius")),
        )
        inst._tpid = None
        if is_clone:
            inst._tpid = data.get("pid")
        inst.csv_path = data.get("csv_path")
        # 2) Registry registration
        inst._registry = registry
        registry.register(inst)

        # 3) Child elements (images/text)
        inst.items = []
        for e in data.get("items", []):
            prefix = get_prefix(e["pid"])
            if prefix == "ie":
                el = ImageElement.from_dict(e, registry, is_clone=is_clone)
            elif prefix == "te":
                el = TextElement.from_dict(e, registry, is_clone=is_clone)
            else:
                raise ValueError(f"Unknown prefix {prefix}")
            el.setParentItem(inst)
<<<<<<< Updated upstream
            inst.items.append(el)

=======
            inst.add_item(el)
            
>>>>>>> Stashed changes
        return inst
