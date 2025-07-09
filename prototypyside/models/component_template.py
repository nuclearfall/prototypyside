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
from prototypyside.utils.proto_helpers import get_prefix
# Use TYPE_CHECKING for type hinting
if TYPE_CHECKING:
    from prototypyside.models.component_elements import ComponentElement

class ComponentTemplate(QGraphicsObject):
    template_changed = Signal()
    element_z_order_changed = Signal()
    # border width and corner_radius are set based on a standard MTG card
    def __init__(self, pid, geometry=UnitStrGeometry(width="2.5in", height="3.5in", dpi=144), parent = None, 
        name=None, rounded_corners=True, corner_radius="0in", border_width="0in", template_pid=None):
        super().__init__(parent)
        self._pid = pid
        self._name = name
        self._geometry = geometry
        self._dpi = geometry.dpi
        self._pixmap = None
        self.template_pid = template_pid
        self.elements: List['ComponentElement'] = []
        self.element_pids: List[str] = []
        self.background_image_path: Optional[str] = None
        self._rounded_corners = rounded_corners
        self.border = UnitStr(border_width, dpi=self._dpi)
        self.corner_radius = UnitStr(corner_radius, dpi=self._dpi)

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
        # self.element_changed.emit()
        self.update()

    def boundingRect(self) -> QRectF:
        return self._geometry.px.rect

    # This method is for when ONLY the rectangle (size) changes,
    # not the position.
    def setRect(self, new_rect: QRectF):
        if self._geometry.px.rect == new_rect:
            return
        self.prepareGeometryChange()
        with_rect(self._geometry, new_rect)
        # self.element_changed.emit()
        # self.update()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        # This is called when the scene moves the item.
        if change == QGraphicsItem.ItemPositionChange and value != self.pos():
            # Block signals to prevent a recursive loop if a connected slot
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
    def rounded_corners(self):
        return self._rounded_corners

    @rounded_corners.setter
    def rounded_corners(self, value:bool):
        if self._rounded_corners != value:
            self._rounded_corners = value
            self.template_changed.emit()
            self.update()

    def add_element(self, element) -> "ComponentElement":
        if element in self.elements:
            return
        self.elements.append(element)

        self.element_pids.append(element.pid)
        max_z = max([e.zValue() for e in self.elements], default=0)
        element.setZValue(max_z + 100)
        # element.element_changed.connect(self._on_element_changed)
        self.template_changed.emit()
        self.element_z_order_changed.emit()

    def remove_element(self, element: 'ComponentElement'):
        if element in self.elements:
            self.elements.remove(element)
            self.template_changed.emit()
            self.element_z_order_changed.emit()

    def reorder_element_z(self, element: 'ComponentElement', direction: int):
        if element not in self.elements:
            return

        # Create a stable ordering using indices as secondary key
        sorted_elements = sorted(
            enumerate(self.elements),
            key=lambda x: (x[1].zValue(), x[0])
        )
        
        # Find current position
        current_idx = next((i for i, (idx, e) in enumerate(sorted_elements) if e is element), -1)
        if current_idx == -1:
            return

        # Calculate new position
        new_idx = current_idx + direction
        
        # Validate move boundaries
        if new_idx < 0 or new_idx >= len(sorted_elements):
            return

        # Get adjacent element
        adj_element = sorted_elements[new_idx][1]
        
        # Swap z-values using robust method
        current_z = element.zValue()
        adj_z = adj_element.zValue()
        
        # Handle z-value collisions
        if direction > 0:
            new_z = adj_z + 1
        else:
            new_z = adj_z - 1
        
        # Apply new z-values
        element.setZValue(new_z)
        adj_element.setZValue(current_z)
        
        # Maintain unique z-values by resetting the entire stack
        self._normalize_z_values()
        self.element_z_order_changed.emit()

    def _normalize_z_values(self):
        """Ensure all elements have unique, ordered z-values"""
        # Sort by current z-value
        sorted_elements = sorted(self.elements, key=lambda e: e.zValue())
        
        # Assign new values with fixed increments
        for z_value, el in enumerate(sorted_elements, start=100):
            el.setZValue(z_value * 100)  # Fixed increment of 100
        
        # Sort internal list to match new order
        self.elements.sort(key=lambda e: e.zValue())

    def bring_to_front(self, element: 'ComponentElement'):
        if element not in self.elements:
            return
        
        # Set to max + increment
        max_z = max(e.zValue() for e in self.elements)
        element.setZValue(max_z + 100)
        self._normalize_z_values()
        self.element_z_order_changed.emit()

    def send_to_back(self, element: 'ComponentElement'):
        if element not in self.elements:
            return
        
        # Set to min - increment
        min_z = min(e.zValue() for e in self.elements)
        element.setZValue(min_z - 100)
        self._normalize_z_values()
        self.element_z_order_changed.emit()

    def set_background_image(self, path: str):
        if Path(path).exists():
            self.background_image_path = path
            self.template_changed.emit() # Re-add signal emission
            print(f"path from gc_template {path}")
            return True
        return False

    # def _on_element_changed(self):
    #     # Trigger redraw of entire template and notify any listeners
    #     self.template_changed.emit()
    #     self.update()
    def paint(self, painter: QPainter, option, widget=None):
        rect = self.boundingRect()
        painter.setRenderHint(QPainter.Antialiasing)

        # ——— Background ———
        painter.save()
        painter.setClipRect(rect)
        painter.setPen(Qt.NoPen)
        if self.background_image_path:
            img = QImage(self.background_image_path)
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
    # def paint(self, painter: QPainter, option, widget=None):
    #     rect = self.boundingRect()
    #     painter.setRenderHint(QPainter.Antialiasing)
    #     painter.setClipRect(rect)
    #     # Draw background
    #     if self.background_image_path:
    #         bg_image = QImage(self.background_image_path)
    #         if not bg_image.isNull():
    #             painter.drawImage(rect, bg_image)
    #         else:
    #             painter.fillRect(rect, Qt.white)
    #     else:
    #         painter.fillRect(rect, Qt.white)

    #     # Draw border if defined
    #     if self.border.value > 0:
    #         thickness_px = self.border.px          
    #         radius_px = self.corner_radius.px

    #         inset = thickness_px / 2
    #         inner_rect = QRectF(
    #             rect.x() + inset,
    #             rect.y() + inset,
    #             rect.width() - thickness_px,
    #             rect.height() - thickness_px
    #         )

    #         # Clamp radius to avoid drawing errors
    #         max_radius = min(inner_rect.width(), inner_rect.height()) / 2
    #         radius_px = max(0, min(radius_px - inset, max_radius))

    #         path = QPainterPath()
    #         if radius_px > 0:
    #             path.addRoundedRect(inner_rect, radius_px, radius_px)
    #         else:
    #             path.addRect(inner_rect)

    #         painter.setPen(QPen(Qt.black, thickness_px))
    #         painter.setBrush(Qt.NoBrush)
    #         painter.drawPath(path)

    def to_dict(self) -> Dict[str, Any]:
        data = {
            'pid': self._pid,
            'name': self._name,
            'geometry': self._geometry.dict(),
            'background_image_path': self.background_image_path,
            'elements': [e.to_dict() for e in self.elements]
        }
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ComponentTemplate':
        geometry = UnitStrGeometry.from_dict(data.get("geometry"))
        template = cls(
            pid=data['pid'],
            geometry=geometry,
            name=data.get('name', None),
        )
        template.background_image_path = data.get('background_image_path')
        template._elements = data.get('elements')
        return template
        