# prototypyside/models/game_component_template.py (REVISED to inherit QObject)

from PySide6.QtCore import Qt, QObject, QRectF, QPointF, Signal # Import QObject and Signal
from PySide6.QtGui import QPainter, QPixmap, QColor, QImage
from PySide6.QtWidgets import QGraphicsItem
from typing import List, Dict, Any, Optional, TYPE_CHECKING
import csv
import json
from pathlib import Path
from PySide6.QtWidgets import QMessageBox


from prototypyside.models.game_component_elements import create_element
from prototypyside.utils.qt_helpers import list_to_qrectf
# Use TYPE_CHECKING for type hinting
from prototypyside.models.game_component_elements import GameComponentElement


class GameComponentTemplate(QObject): # NOW INHERITS QObject
    template_changed = Signal() # Re-add signal
    element_z_order_changed = Signal() # Re-add signal

    def __init__(self, width=2.5, height=3.5, dpi=300, parent: QObject = None): # Add parent arg
        super().__init__(parent) # Call QObject's init with parent
        self.width_in = parse_dimension(width) if isinstance(width, str) else float(width)
        self.height_in = parse_dimension(height) if isinstance(height, str) else float(height)
        self.dpi = dpi
        self.elements: List['GameComponentElement'] = []
        self.background_image_path: Optional[str] = None

    @property
    def width_px(self) -> int:
        return int(self.width_in * self.dpi)

    @property
    def height_px(self) -> int:
        return int(self.height_in * self.dpi)

    def set_width_px(self, px: int):
        self.width_in = px / self.dpi

    def set_height_px(self, px: int):
        self.height_in = px / self.dpi

    def add_element(self, element_type: str, name: str, rect: QRectF) -> 'GameComponentElement':
        from prototypyside.models.game_component_elements import GameComponentElement
        # element = GameComponentElement.create(element_type, name, rect, self) # Pass self (QObject) as parent_qobject
        element = create_element(element_type, name, rect, parent_qobject=self)
        max_z = max([e.zValue() for e in self.elements] + [0]) if self.elements else 0
        element.setZValue(max_z + 100)
        self.elements.append(element)
        # Re-connect element_changed for new elements
        # This connection should ideally happen in the MainDesignerWindow when elements are added to scene.
        # However, if template needs to be notified of element changes for its own internal state, keep it.
        # For now, let's connect it in MainDesignerWindow when adding to scene for clarity.
        # element.element_changed.connect(self.template_changed) # REMOVE THIS LINE (connect in MainDesignerWindow)
        self.template_changed.emit() # Re-add signal emission
        self.element_z_order_changed.emit() # Re-add signal emission
        return element

    def remove_element(self, element: 'GameComponentElement'):
        if element in self.elements:
            self.elements.remove(element)
            # Removed disconnect for element_changed as it's now managed by MainDesignerWindow
            self.template_changed.emit() # Re-add signal emission
            self.element_z_order_changed.emit() # Re-add signal emission

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
            'width_in': self.width_in,
            'height_in': self.height_in,
            'dpi': self.dpi,
            'background_image_path': self.background_image_path,
            'elements': [e.to_dict() for e in self.elements]
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any], parent: QObject = None) -> 'GameComponentTemplate':
        template = cls(
            width=data.get('width_in', 2.5),
            height=data.get('height_in', 3.5),
            dpi=data.get('dpi', 300),
            parent=parent
        )
        template.background_image_path = data.get('background_image_path')

        for element_data in data.get('elements', []):
            element_type = element_data.get("type")
            if not element_type:
                continue

            # Dispatch to correct class via base class factory method
            element = GameComponentElement.from_dict(element_data, parent_qobject=template)
            template.elements.append(element)

        template.elements.sort(key=lambda e: e.zValue())
        template.template_changed.emit()
        return template


    def reorder_element_z(self, element: 'GameComponentElement', direction: int):
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