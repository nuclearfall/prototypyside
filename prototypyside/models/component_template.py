# component_template.py

from PySide6.QtCore import Qt, QObject, QRectF, QPointF, Signal # Import QObject and Signal
from PySide6.QtGui import QPainter, QPixmap, QColor, QImage, QBrush, QPen, QPainterPath
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject
from typing import List, Dict, Any, Optional, TYPE_CHECKING
import csv
import json
from pathlib import Path
from PySide6.QtWidgets import QMessageBox

from prototypyside.models.component_elements import ImageElement, TextElement
from prototypyside.utils.unit_str import UnitStr
from prototypyside.utils.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.ustr_helpers import with_pos, with_rect
from prototypyside.utils.proto_helpers import get_prefix, issue_pid
# Use TYPE_CHECKING for type hinting
if TYPE_CHECKING:
    from prototypyside.models.component_elements import ComponentElement


class ComponentTemplate(QGraphicsObject):
    template_changed = Signal()
    item_z_order_changed = Signal()
    # border width and corner_radius are set based on a standard MTG card
    def __init__(self, pid, geometry=UnitStrGeometry(width="2.5in", height="3.5in"), parent = None, 
        name=None, registry=None, corner_radius=UnitStr("0in"), border=UnitStr("0in")):
        super().__init__(parent)
        self._pid = pid
        self._name = name
        self._registry = registry
        self._geometry = geometry
        self._dpi = geometry.dpi
        self._pixmap = None
        self.items: List['ComponentElement'] = []
        self._background_image: Optional[str] = None
        self._border = border
        self._corner_radius = corner_radius

    @property
    def pid(self) -> str:
        return self._pid

    @pid.setter
    def pid(self, value):
        self._pid = value
        self.template_changed.emit()

    @property
    def dpi(self):
        return self._dpi

    @property
    def geometry(self):
        return self._geometry

    @geometry.setter
    def geometry(self, new_geom: UnitStrGeometry):
        print(f"[SETTER] geometry called with {new_geom}")
        if self._geometry == new_geom:
            print("[SETTER] geometry unchanged")
            return

        self.prepareGeometryChange()
        print(f"[SETTER] prepareGeometryChange called")
        print(f"[SETTER] pos set to {self._geometry.px.pos}")
        self._geometry = new_geom
        super().setPos(self._geometry.px.pos)
        # self.item_changed.emit()
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
        with_rect(self._geometry, new_rect)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        # This is called when the scene moves the item.
        if change == QGraphicsItem.ItemPositionChange and value != self.pos():
            # Block signals to prevent a recursive loop if a connected item
            # also tries to set the position.
            signals_blocked = self.signalsBlocked()
            self.blockSignals(True)
            with_pos(self._geometry, value)
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
    
    def add_item(self, item) -> "ComponentElement":
        if item in self.items:
            return
        self.items.append(item)
        max_z = max([e.zValue() for e in self.items], default=0)
        item.setZValue(max_z + 100)
        # item.item_changed.connect(self._on_item_changed)
        self.template_changed.emit()
        self.item_z_order_changed.emit()

    def remove_item(self, item: 'ComponentElement'):
        if item in self.items:
            self.items.remove(item)
            self.template_changed.emit()
            self.item_z_order_changed.emit()

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
            self.update()
        else:
            self._background_image = None
            print(f"[Warning] Background image not found: {path}")

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.boundingRect()
        painter.setRenderHint(QPainter.Antialiasing)

        # ——— Background ———
        painter.save()
        painter.setClipRect(rect)
        painter.setPen(Qt.NoPen)
        if self.background_image:
            img = QImage(self.background_image)
            if not img.isNull():
                # drawImage(targetRect, image) will scale it to fill rect
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

            thickness_px = self.border.px
            inset = thickness_px / 2.0
            inner = QRectF(
                rect.x() + inset,
                rect.y() + inset,
                rect.width() - thickness_px,
                rect.height() - thickness_px
            )

            # clamp corner radius
            radius_px = max(0.0, min(self.corner_radius.px - inset,
                                     min(inner.width(), inner.height()) / 2.0))

            path = QPainterPath()
            if radius_px > 0.0:
                path.addRoundedRect(inner, radius_px, radius_px)
            else:
                path.addRect(inner)

            painter.setPen(QPen(Qt.black, thickness_px))
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
            'corner_radius': self.corner_radius.to_dict()
        }
        return data

    @classmethod
    def from_dict(cls, data: dict, registry, is_clone=False):
        geom = UnitStrGeometry.from_dict(data["geometry"])
        pid = data.get("pid")
        prefix = get_prefix(pid)
        background_image = data.get("background_image")

        if is_clone:
            pid = issue_pid("cc") # ComponentClone pid for is_clone
        inst = cls(
                    pid=pid, 
                    geometry=geom, 
                    name=data.get("name") if is_clone is False else None,
                    border=UnitStr.from_dict(data.get("border")),
                    corner_radius=data.get("corner_radius"),
        )
        inst.background_image = Path(background_image) if background_image else None
        registry.register(inst)

        inst.items = []
        for e in data.get("items", []):
            item_pid = e.get("pid")
            prefix = get_prefix(item_pid)
            if prefix == 'ie':
                item = ImageElement.from_dict(e, registry, is_clone=is_clone)
            elif prefix == 'te':
                item = TextElement.from_dict(e, registry, is_clone=is_clone)
            else:
                raise ValueError(f"Unknown item prefix {prefix!r}")

            item.setParentItem(inst)
            inst.items.append(item)

        return inst