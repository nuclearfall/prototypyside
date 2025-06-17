# prototypyside/models/game_component_template.py (REVISED to inherit QObject)

from PySide6.QtCore import Qt, QObject, QRectF, QPointF, Signal # Import QObject and Signal
from PySide6.QtGui import QPainter, QPixmap, QColor, QImage
from PySide6.QtWidgets import QGraphicsItem
from typing import List, Dict, Any, Optional, TYPE_CHECKING
import csv
import json
from pathlib import Path
from PySide6.QtWidgets import QMessageBox

#from prototypyside.models.game_component_elements import create_element
from prototypyside.utils.qt_helpers import list_to_qrectf
from prototypyside.utils.unit_converter import to_px, format_dimension
# Use TYPE_CHECKING for type hinting
if TYPE_CHECKING:
    from prototypyside.models.component_elements import ComponentElement

class ComponentTemplate(QObject): # NOW INHERITS QObject
    template_changed = Signal() # Re-add signal
    element_z_order_changed = Signal() # Re-add signal

    def __init__(self, pid, width="2.5 in", height="3.5 in", dpi=300, parent: QObject = None, name="Component Template"): # Add parent arg
        super().__init__(parent) # Call QObject's init with parent
        self._pid = pid
        self.name = name
        self.width = width
        self.height = height
        self._width_px = to_px(width, dpi=dpi)
        self._height_px = to_px(height, dpi=dpi)
        self.dpi = dpi
        self.is_template = True
        self.element_pids = []
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
    def width_px(self) -> int:
        return self._width_px

    @width_px.setter
    def width_px(self, px: int):
        self._width_px = px
        self.width = format_dimension(px, dpi=self.dpi)
        self.template_changed.emit()

    @property
    def height_px(self) -> int:
        return self._height_px

    @height_px.setter
    def height_px(self, px: int):
        self._height_px = px
        self.height = format_dimension(px, dpi=self.dpi)
        self.template_changed.emit()

    def add_element(self, element) -> 'ComponentElement':
        # Use consistent z-value increments
        print(f"Element added... {element.pid}:{element.name}")
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
            'width': self.width,
            'height': self.height,
            'dpi': self.dpi,
            'is_template': self.is_template,
            'background_image_path': self.background_image_path,
            'element_pids': [e.pid for e in self.elements]  # 🔄 save only references
        }
  
    @classmethod
    def from_dict(cls, data: Dict[str, Any], parent: QObject = None) -> 'ComponentTemplate':
        template = cls(
            pid=data['pid'],
            width=data.get('width', 2.5),
            height=data.get('height', 3.5),
            dpi=data.get('dpi', 300),
            parent=parent,
            name=data.get('name', "Component Template")
        )

        template.background_image_path = data.get('background_image_path')
        template.element_pids = data.get('element_pids')
        template._pending_element_pids = []
        return template

    def reorder_element_z(self, element: 'ComponentElement', direction: int):
        if element not in self.elements:
            return

        elements_by_z = sorted(self.elements, key=lambda e: e.zValue())

        element_idx = -1
        for i, el in enumerate(elements_by_z):
            if el == element:
                element_idx = i
                break

        if element_idx == -1:
            return

        if direction > 0: # Bring forward
            if element_idx + 1 < len(elements_by_z):
                next_element = elements_by_z[element_idx + 1]
                temp_z = element.zValue()
                element.setZValue(next_element.zValue())
                next_element.setZValue(temp_z)
        elif direction < 0: # Send backward
            if element_idx - 1 >= 0:
                prev_element = elements_by_z[element_idx - 1]
                temp_z = element.zValue()
                element.setZValue(prev_element.zValue())
                prev_element.setZValue(temp_z)

        self.elements.sort(key=lambda e: e.zValue())
        self.element_z_order_changed.emit() # Re-add signal emission