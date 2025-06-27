# prototypyside/models/game_component_template.py (REVISED to inherit QObject)

from PySide6.QtCore import Qt, QObject, QRectF, QPointF, Signal # Import QObject and Signal
from PySide6.QtGui import QPainter, QPixmap, QColor, QImage
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject
from typing import List, Dict, Any, Optional, TYPE_CHECKING
import csv
import json
from pathlib import Path
from PySide6.QtWidgets import QMessageBox

#from prototypyside.models.game_component_elements import create_element
from prototypyside.utils.qt_helpers import list_to_qrectf
from prototypyside.utils.unit_converter import to_px, format_dimension
from prototypyside.utils.unit_str import UnitStr
from prototypyside.services.undo_commands import AddElementCommand
# Use TYPE_CHECKING for type hinting
if TYPE_CHECKING:
    from prototypyside.models.component_elements import ComponentElement

class ComponentTemplate(QGraphicsObject):
    template_changed = Signal()
    element_z_order_changed = Signal()

    def __init__(self, pid, registry, dpi=300, width="2.5 in", height="3.5 in", parent: QObject = None, name="Component Template"):
        super().__init__(parent)
        self._pid = pid
        self.name = name
        self._width = UnitStr(width, dpi=dpi)
        self._height = UnitStr(height, dpi=dpi)
        self._unit = self._width.unit
        self._dpi = dpi
        self.is_template = True
        self.elements: List['ComponentElement'] = []
        self.background_image_path: Optional[str] = None

    @property
    def pid(self) -> str:
        return self._pid

    @pid.setter
    def pid(self, value):
        self._pid = value
        self.template_changed.emit()

    @property
    def width_px(self) -> float:
        return self.width.to("px", dpi=self._dpi)

    @property
    def height_px(self) -> float:
        return self.height.to("px", dpi=self._dpi)

    @property
    def width(self) -> UnitStr:
        return self._width

    @width.setter
    def width(self, value):
        if isinstance(value, UnitStr):
            self._width = value
        else:
            self._width = UnitStr(value, dpi=self._dpi)
        self.template_changed.emit()

    @property
    def height(self) -> UnitStr:
        return self._height

    @height.setter
    def height(self, value):
        if isinstance(value, UnitStr):
            self._height = value
        else:
            self._height = UnitStr(value, dpi=self._dpi)
        self.template_changed.emit()

    @property
    def unit(self):
        return self._unit
        
    @property 
    def dpi(self):
        return self._dpi

    def add_element(self, element) -> "ComponentElement":
        self.elements.append(element)
        max_z = max([e.zValue() for e in self.elements], default=0)
        element.setZValue(max_z + 100)
        self.elements.append(element)
        element.template_pid = self.pid
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

    def load_csv(self, filepath: str):
        try:
            with open(filepath, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                data_rows = list(reader)
                if not data_rows:
                    QMessageBox.warning(None, "CSV Load Error", "The CSV file is empty or has no data rows.")
                    return

                data_row = data_rows[0]
                for element in self.elements:
                    if element.name in data_row:
                        element.set_content(data_row[element.name])
            self.template_changed.emit() # Re-add signal emission
        except FileNotFoundError:
            QMessageBox.warning(None, "CSV Load Error", f"File not found: {filepath}")
        except Exception as e:
            QMessageBox.critical(None, "CSV Load Error", f"An error occurred: {str(e)}")
            print(f"CSV Load Error: {str(e)}")

    def set_background_image(self, path: str):
        if Path(path).exists():
            self.background_image_path = path
            self.template_changed.emit() # Re-add signal emission
            print(f"path from gc_template {path}")
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'pid': self.pid,
            'name': self.name,
            'width': self._width.format(),
            'height': self._height.format(),
            'dpi': self._dpi,
            'background_image_path': self.background_image_path,
            'elements': [e.to_dict() for e in self.elements]  # 🔄 save only references
        }
  
    @classmethod
    def from_dict(cls, data: Dict[str, Any], parent: QObject = None) -> 'ComponentTemplate':
        template = cls(
            pid=data['pid'],
            width=data.get('width', "2.5 in"),
            height=data.get('height', "3.5 in"),
            dpi=data.get('dpi', 300),
            unit = 300,
            parent=parent,
            name=data.get('name', "Component Template")
        )
        elements = data.get("elements")
        self.elments = [e.from_dict() for e in elements]
        template.background_image_path = data.get('background_image_path')
        return template