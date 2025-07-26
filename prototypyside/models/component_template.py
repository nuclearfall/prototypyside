# component_template.py

from PySide6.QtCore import Qt, QObject, QRectF, QPointF, Signal # Import QObject and Signal
from PySide6.QtGui import QPainter, QPixmap, QColor, QImage, QBrush, QPen, QPainterPath
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject
from typing import List, Dict, Any, Optional, TYPE_CHECKING
import csv
import json
from pathlib import Path
from PySide6.QtWidgets import QMessageBox
import weakref
import gc
import traceback

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

    # border_width width and corner_radius are set based on a standard MTG card
    def __init__(self, pid, geometry=UnitStrGeometry(width="2.5in", height="3.5in", dpi=300), parent = None, 
        name=None, registry=None, corner_radius=UnitStr("0.125in", dpi=300), border_width=UnitStr("0.125in", dpi=300)):
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
        self._dpi = 300
        self._unit = "px"
        self._corner_radius = corner_radius
        self._bleed = UnitStr("0.125in", unit="in", dpi=300)
        self._pixmap = None
        self.items: List['ComponentElement'] = []
        self._background_image: Optional[str] = None
        self._border_width = border_width
        self._corner_radius = corner_radius
        self._csv_row = []
        self._csv_path: Path = None 
        self.content = None
        weakref.finalize(self, self._on_finalize)

    def _on_finalize(self):
        print(f"\n[DEBUG] ComponentTemplate {getattr(self, 'pid', 'unknown')} finalized")
        print(">>> Remaining references (may include stack frames):")
        for ref in gc.get_referrers(self):
            try:
                print(f" - {type(ref)}: {repr(ref)[:120]}")
            except RuntimeError as e:
                print(f" - {type(ref)}: <unavailable: {e}>")

        print(">>> Object was constructed at:")
        import traceback
        traceback.print_stack(limit=4)  # shows where template was created

    @property
    def name(self):
        return self._name
    @name.setter
    def name(self, value):
        if self._name != value:
            self._name = value
    
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
        if value != self._csv_path:
            try:
                path = Path(value)
                self._csv_path = path
            except Exception:
                self._csv_path = None
                
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
            self.template_changed.emit()
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
            print(f"[ITEMCHANGE] Geometry.pos updated to: {self._geometry.px.pos}")
            self.blockSignals(signals_blocked)

        # It's crucial to call the base class implementation. This will update geometry.
        # If other signals are emitted or updates called for, it breaks the undo stack.
        return super().itemChange(change, value)

    @property
    def bleed(self):
        return self._bleed

    @bleed.setter
    def bleed(self, new):
        self._bleed = new if self._bleed != new else self,_bleed
        self.update()
    
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
    def border_width(self):
        return self._border_width

    @border_width.setter
    def border_width(self, value):
        if self._border_width != value:
            self._border_width = value
            self.template_changed.emit()

    def add_item(self, item):
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
                self.template_changed.emit()
            self.update()
        else:
            self._background_image = None
            print(f"[Warning] Background image not found: {path}")

    def apply_row_data(self, row_data):
        for item in [i for i in items if i.name.startswith("@")]:
            setattr(i, "content", row_data.get(i.name))

    def paint(self, painter: QPainter, option, widget=None):
        """
        Paints the template's background and border_width using the specified unit and dpi.

        Parameters:
            painter (QPainter): Painter object used by the scene or exporter.
            option: QStyleOptionGraphicsItem from the scene (unused).
            widget: Optional QWidget; unused.
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
        if self.border_width.value > 0:
            painter.save()
            painter.setBrush(Qt.NoBrush)

            # Convert border_width thickness to unit
            thickness = self.border_width.to(self.unit, dpi=self.dpi)
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
        self._geometry
        self._border_width
        

        data = {
            'pid': self._pid,
            'name': self._name,
            'geometry': self._geometry.to_dict(),
            'background_image': str(self.background_image) if self.background_image else None,
            'items': [e.to_dict() for e in self.items],
            'border_width': self.border_width.to_dict(),
            'corner_radius': self.corner_radius.to_dict(),
            'csv_path': str(self.csv_path) if self.csv_path and Path(self.csv_path).exists else None,
            'tpid': self._tpid
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
        inst = cls(
            pid=pid,
            geometry=geom,
            name=data.get("name"),
            border_width=UnitStr.from_dict(data.get("border_width")),
            corner_radius=UnitStr.from_dict(data.get("corner_radius")),
        )

        inst._tpid = data.get("pid") if is_clone else None
        # CSV Data loads properly on open now.
        csv_path = data.get("csv_path")
        inst._csv_path = Path(csv_path) if csv_path else None
        inst._registry = registry
        registry.register(inst)
        inst._name = registry.generate_name(inst)
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
