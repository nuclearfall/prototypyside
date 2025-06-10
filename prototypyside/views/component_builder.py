# component_builder.py

import sys
import json
import csv
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

from PySide6.QtWidgets import (QGraphicsView, QGraphicsItem, QDockWidget,
                               QListWidgetItem, QWidget, QVBoxLayout, QScrollArea,
                               QLabel, QLineEdit, QPushButton, QComboBox,
                               QSpinBox, QDoubleSpinBox, QFormLayout, QGroupBox,
                               QColorDialog, QFontDialog, QFileDialog, QMessageBox,
                               QHBoxLayout, QDialog, QToolBar, QCheckBox)

from PySide6.QtCore import Qt, Property, Signal, Slot, QPointF, QRectF, QSizeF, QObject, QSize, QTimer, QCoreApplication, QEvent
from PySide6.QtGui import QPainter, QImage, QPixmap, QFont, QColor, QAction, QIcon, QPdfWriter, QTextDocument, QKeySequence, QShortcut, QMouseEvent

# Import views components
from prototypyside.views.graphics_scene import GameComponentGraphicsScene
from prototypyside.views.component_builder_ui import ComponentBuilderUI

from prototypyside.widgets.page_size_dialog import PageSizeDialog
from prototypyside.widgets.page_size_selector import PageSizeSelector
from prototypyside.widgets.pdf_export_dialog import PDFExportDialog
# Import models
from prototypyside.models.game_component_template import GameComponentTemplate
from prototypyside.models.game_component_elements import (GameComponentElement, TextElement,
                                                     ImageElement)
from prototypyside.services.proto_factory import ProtoFactory
from prototypyside.services.proto_registry import ProtoRegistry
from prototypyside.views.graphics_view import DesignerGraphicsView
from prototypyside.services.export_manager import ExportManager
from prototypyside.services.app_settings import AppSettings
from prototypyside.services.property_setter import PropertySetter
from prototypyside.utils.unit_converter import VALID_UNITS



class ComponentBuilder(QWidget):
    status_message_signal = Signal(str, str, int)

    def __init__(self, appwin, app_settings:AppSettings, template=None):
        super().__init__()
        self.appwin = appwin
        self.settings = app_settings
        self.factory = ProtoFactory
        self.registry = ProtoRegistry

        # Automatically updates on AppSettings changes
        self.settings.unit_changed.connect(self.set_unit)
        self.settings.display_dpi_changed.connect(self.set_display_dpi)
        self.settings.print_dpi_changed.connect(self.set_print_dpi)

        self._template = template

        print(f"Template created: {self.current_template.to_dict()}")
        self.scene = None
        self.view = None
        self.element_palette = None
        self.property_panel = None
 
        self.ui = ComponentBuilderUI(self)

        self.setup_shortcuts()
        self._current_selected_element = None  # This must be kept in sync with selection

        self.current_template.template_changed.connect(self.refresh_scene)
        self.current_template.template_changed.connect(self.update_layers_panel)
        self.current_template.element_z_order_changed.connect(self.update_layers_panel)
        self.scene.selectionChanged.connect(self.on_selection_changed)
        self.scene.element_dropped.connect(self.on_element_dropped)

        
    def set_unit(self, unit: str):
        if self.current_template:
            self.current_template.unit = unit
        if self.scene:
            self.scene.unit = unit
        if self.current_template and hasattr(self.current_template, 'elements'):
            for el in self.current_template.elements:
                el.element_changed.emit()

    def set_display_dpi(self, dpi: int):
        if self.current_template:
            self.current_template.display_dpi = dpi
        if self.current_template and hasattr(self.current_template, 'elements'):
            for el in self.current_template.elements:
                el.element_changed.emit()

    def set_print_dpi(self, dpi: int):
        if self.current_template:
            self.current_template.print_dpi = dpi
        if self.current_template and hasattr(self.current_template, 'elements'):
            for el in self.current_template.elements:
                el.element_changed.emit()

    @property
    def current_template(self):
        return self._template


    @Property(object)
    def selected_element(self):
        return self._selected_element

    @selected_element.setter
    def selected_element(self, element):
        self._selected_element = element
        # Optional: trigger selection-based UI refresh here


    @Slot()
    def update_game_component_scene(self):
        """Updates the scene dimensions and view based on the current template."""
        if not self.scene or not self.current_template:
            return

        rect = current_template.rect

        self.scene.set_template_dimensions(rect.width(), rect.height())
        self.view.setSceneRect(new_rect)
        self.view.fitInView(new_rect, Qt.KeepAspectRatio)
        self.scene.update()


    def setup_shortcuts(self):
        delete_shortcut = QShortcut(QKeySequence.Delete, self)
        delete_shortcut.activated.connect(self.remove_selected_element)

    @Slot(str)
    def on_unit_change(self, unit: str):
        unit = unit.lower().strip().replace('"', 'in')
        if unit not in VALID_UNITS:
            print(f"[Unit Change] Unsupported unit: {unit}")
            return

        self.appwin.current_unit = unit
        self.scene.unit = unit

        self.current_template_width_field.set_display_unit(unit)
        self.current_template_height_field.set_display_unit(unit)

        self.measure_toolbar.update()
        self.refresh_element_property_panel()
        self.scene.update()

    @Slot(int)
    def on_snap_toggle(self, state: int):
        self.snap_to_grid = bool(state)
        self.scene.is_snap_to_grid = self.snap_to_grid

    @Slot(int)
    def on_grid_toggle(self, state):
        self.show_grid = bool(state)
        self.measure_toolbar.update()
        self.scene.update()

    @Slot(int)
    def on_template_width_changed(self, new):
        self.current_template.set_width(new)
        self.update_template_scene_rect()

    @Slot(int)
    def on_template_height_changed(self, new):
        self.current_template.set_height(new)
        self.update_template_scene_rect()

    def update_template_scene_rect(self):
        self.scene.set_template_dimensions(
            self.current_template.width,
            self.current_template.height
        )
        self.scene.update()
        self.view.update()
        self.current_template.template_changed.emit()

    @Slot()
    def on_template_dpi_changed(self):
        new_dpi = self.game_component_dpi_spin.value()
        self.settings.display_dpi = new_dpi

        # Update UnitFields to reflect new DPI
        self.current_template_width_field.set_dpi(new_dpi)
        self.current_template_height_field.set_dpi(new_dpi)

        # Also update the current element fields if one is selected
        if self._current_selected_element:
            self.refresh_element_property_panel()

        self.view.viewport().update()
        self.view.update()
        self.scene.update()

        self.current_template.template_changed.emit()
        self.appwin.show_status_message(f"DPI updated to {new_dpi}.", "info")

    def on_property_changed(self, change):
        if self.selected_element is None or self.settings is None or change is None:
            return

        if isinstance(change, tuple) and change[1] is None:
            return  # avoid transmitting None values as changes

        setter = PropertySetter(self.selected_element, self.settings, self.scene)

        if isinstance(change, dict):
            prop = change.get("property")
            value = change.get("value")
        elif isinstance(change, tuple) and len(change) == 2:
            prop, value = change
        else:
            print(f"[ComponentBuilder] Invalid property change payload: {change}")
            return

        setter_fn = getattr(setter, f"set_{prop}", None)
        if callable(setter_fn):
            setter_fn(value)
        else:
            print(f"[ComponentBuilder] No PropertySetter method for: {prop}")

    @Slot()
    def on_selection_changed(self):
        selected_element = self.get_selected_element()

        if self._current_selected_element and self._current_selected_element != selected_element:
            # Disconnect previous
            try:
                self._current_selected_element.element_changed.disconnect(self.on_element_data_changed)
            except TypeError:
                pass

            self._current_selected_element.hide_handles()

        self._current_selected_element = selected_element

        if selected_element:
            
            self._layers_panel.select_element(selected[0])
            selected_element.show_handles()

            self.set_element_controls_enabled(True)
            self.font_toolbar_widget.setEnabled(True)

            self.name_edit.blockSignals(True)
            self.content_edit.blockSignals(True)
            self.alignment_combo.blockSignals(True)

            self.name_edit.setText(selected_element.name)
            self.content_edit.setText(selected_element.get_content() or "")
            self.refresh_element_property_panel()
            current_alignment = selected_element._style.get('alignment', Qt.AlignCenter)
            if current_alignment in self.reverse_alignment_map:
                self.alignment_combo.setCurrentIndex(self.reverse_alignment_map[current_alignment])
            else:
                self.alignment_combo.setCurrentIndex(4)

            if isinstance(selected_element, TextElement):
                current_font = selected_element._style.get('font', QFont("Arial", 12))
                if not isinstance(current_font, QFont):
                    current_font = QFont("Arial", 12)
                self.font_toolbar_widget.set_font(current_font)
                self.font_toolbar_widget.setEnabled(True)
            else:
                self.font_toolbar_widget.setEnabled(False)

            self.name_edit.blockSignals(False)
            self.content_edit.blockSignals(False)
            self.alignment_combo.blockSignals(False)

            selected_element.element_changed.connect(self.on_element_data_changed)

            self.layers_list.blockSignals(True)
            self.layers_list.clearSelection()
            for i in range(self.layers_list.count()):
                item = self.layers_list.item(i)
                if item.data(Qt.UserRole) == selected_element:
                    item.setSelected(True)
                    self.layers_list.scrollToItem(item)
                    break
            self.layers_list.blockSignals(False)
        else:
            self.set_element_controls_enabled(False)
            self.font_toolbar_widget.setEnabled(False)
            self.layers_list.blockSignals(True)
            self.layers_list.clearSelection()
            self.layers_list.blockSignals(False)


    @Slot()
    def on_element_data_changed(self):
        element = self.get_selected_element()
        if element and element == self._current_selected_element:
            self.name_edit.blockSignals(True)
            self.content_edit.blockSignals(True)
            self.alignment_combo.blockSignals(True)

            self.name_edit.setText(element.name)
            self.content_edit.setText(element.get_content() or "")
            current_alignment = element._style.get('alignment', Qt.AlignCenter)
            if current_alignment in self.reverse_alignment_map:
                self.alignment_combo.setCurrentIndex(self.reverse_alignment_map[current_alignment])
            else:
                self.alignment_combo.setCurrentIndex(4)

            if isinstance(element, TextElement):
                current_font = element._style.get('font', QFont("Arial", 12))
                if not isinstance(current_font, QFont):
                     current_font = QFont("Arial", 12)
                self.font_toolbar_widget.set_font(current_font)

            self.name_edit.blockSignals(False)
            self.content_edit.blockSignals(False)
            self.alignment_combo.blockSignals(False)

            element.update()
            self.scene.update()

        self.update_layers_panel()

    @Slot(QGraphicsItem)
    def select_element_from_layers_list(self, element: QGraphicsItem):
        if isinstance(element, GameComponentElement):
            self.scene.blockSignals(True)
            self.scene.clearSelection()
            element.setSelected(True)
            self.scene.blockSignals(False)

    @Slot()
    def update_layers_panel(self):
        if hasattr(self.appwin, "update_layers_panel"):
            self.appwin.update_layers_panel()

    @Slot(int)
    def adjust_z_order_of_selected(self, direction: int):
        element = self.get_selected_element()
        if element:
            self.current_template.reorder_element_z(element, direction)

    @Slot()
    def bring_selected_to_front(self):
        element = self.get_selected_element()
        if element:
            max_z = max([e.zValue() for e in self.current_template.elements] + [0])
            if element.zValue() < max_z:
                element.setZValue(max_z + 1)
                self.current_template.elements.sort(key=lambda e: e.zValue())
                self.current_template.element_z_order_changed.emit()

    @Slot()
    def send_selected_to_back(self):
        element = self.get_selected_element()
        if element:
            min_z = min([e.zValue() for e in self.current_template.elements] + [0])
            if element.zValue() > min_z:
                element.setZValue(min_z - 1)
                self.current_template.elements.sort(key=lambda e: e.zValue())
                self.current_template.element_z_order_changed.emit()

    @Slot(object, int)
    def reorder_element_z_from_list_event(self, element: object, direction: int):
        self.current_template.elements.sort(key=lambda e: e.zValue())
        self.current_template.element_z_order_changed.emit()

    @Slot()
    def clear_scene_selection(self):
        if self.scene.selectedItems():
            self.scene.clearSelection()

    def add_element_from_drop(self, scene_pos: QPointF, prefix: str):
        self.scene.clearSelection()

        # Define default dimensions based on element type
        default_width, default_height = 120, 100

        # Generate a unique name for the new element
        base_name = f"{element_type.replace('Element', '').lower()}_"
        counter = 1
        existing_names = {el.get_name() for el in self.current_template.elements}
        while f"{base_name}{counter}" in existing_names:
            counter += 1
        new_name = f"{base_name}{counter}"
        print(new_name)

        # Always use a rect starting at (0,0) for the internal drawing space
        new_rect = QRectF(0, 0, default_width, default_height)

        # Create the element using the GameComponentTemplate
        pid = issue_pid(prefix)
        new_element = self.registry.create(pid=pid, rect=new_rect, template=current_template, parent=None, dpi=settings.dpi, unit=settings.unit)

        # Add it to the scene
        self.scene.addItem(new_element)

        # Snap top-left corner of visual bounds to grid
        if self.snap_to_grid:
            scene_pos = self.scene.snap_to_grid(scene_pos)

        visual_offset = new_element.boundingRect().topLeft()
        new_element.setPos(scene_pos - visual_offset)

        new_element.setSelected(True)


    @Slot()
    def update_game_component_dimensions(self):
        new_width_in = self.game_component_width.value() # These are not defined in current code
        new_height_in = self.game_component_height.value() # These are not defined in current code
        new_dpi = self.game_component_dpi_spin.value()

        self.current_template.width_in = new_width_in
        self.current_template.height_in = new_height_in
        self.settings.display_dpi = new_dpi

        self.scene.set_template_dimensions(self.current_template.width, self.current_template.height)

        new_scene_rect = QRectF(0, 0, self.current_template.width, self.current_template.height)
        self.scene.setSceneRect(new_scene_rect)
        self.view.setSceneRect(new_scene_rect)

        self.current_template.template_changed.emit()

        self.view.viewport().update()
        self.view.update()
        self.scene.update()

        self.appwin.show_status_message("Game Component dimensions and DPI have been updated.", "info")

    def set_element_controls_enabled(self, enabled: bool):
        self.name_edit.setEnabled(enabled)
        self.content_edit.setEnabled(enabled)
        self.color_btn.setEnabled(enabled)
        self.bg_color_btn.setEnabled(enabled)
        self.border_color_btn.setEnabled(enabled)
        self.alignment_combo.setEnabled(enabled)
        self.remove_element_btn.setEnabled(enabled)


    @Slot()
    def remove_selected_element(self):
        element = self.get_selected_element()
        if element:
            reply = QMessageBox.question(self, "Remove Element",
                                         f"Are you sure you want to remove '{element.name}'?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                self.appwin.show_status_message("Element removal cancelled.", "info")
                return
            self.scene.removeItem(element)
            self.current_template.remove_element(element)
            self.on_selection_changed()
            self.appwin.show_status_message(f"Element '{element.name}' removed.", "info")
        else:
            self.appwin.show_status_message("No element selected to remove.", "warning")

    def refresh_element_property_panel(self):
        element = self._current_selected_element
        dpi = element.template.display_dpi

        if element:
            rect = element.rect

            self.element_x_field.set_dpi(self.settings.dpi)
            self.element_x_field.set_unit(self.settings.unit)
            self.element_x_field.set_value(element.pos().x())

            self.element_y_field.set_dpi(self.settings.dpi)
            self.element_y_field.set_unit(self.settings.unit)
            self.element_y_field.set_value(element.pos().y())

            self.element_width_field.set_dpi(self.settings.dpi)
            self.element_width_field.set_unit(self.settings.unit)
            self.element_width_field.set_value(rect.width())

            self.element_height_field.set_dpi(self.settings.dpi)
            self.element_height_field.set_unit(self.settings.unit)
            self.element_height_field.set_value(rect.height())

            self.border_width_field.set_dpi(self.settings.dpi)
            self.border_width_field.set_unit(self.settings.unit)
            if hasattr(element, "border_width"):
                self.border_width_field.set_value(element.border_width)
            else:
                self.border_width_field.set_value(0)

            self.element_x_field.setEnabled(True)
            self.element_y_field.setEnabled(True)
            self.element_width_field.setEnabled(True)
            self.element_height_field.setEnabled(True)
            self.border_width_field.setEnabled(True)

        else:
            self.element_x_field.set_value(None)
            self.element_y_field.set_value(None)
            self.element_width_field.set_value(None)
            self.element_height_field.set_value(None)
            self.border_width_field.set_value(None)

            self.element_x_field.setEnabled(False)
            self.element_y_field.setEnabled(False)
            self.element_width_field.setEnabled(False)
            self.element_height_field.setEnabled(False)
            self.border_width_field.setEnabled(False)

    def show_status_message(self, message: str, message_type: str = "info", timeout_ms: int = 5000):
        # Emit signal for appwin to display status
        self.appwin.status_message_signal.emit(message, message_type, timeout_ms)

    def on_layer_element_selected(self, element_id: str):
        """
        Slot to handle selection of an element from the layers panel.

        Args:
            element_id (str): The unique ID of the element selected in the layers list.
        """
        # Find the corresponding QGraphicsItem in the scene
        for item in self.scene.items():
            if hasattr(item, "protoid") and item.protoid == element_id:
                self.scene.clearSelection()
                item.setSelected(True)
                self.scene.views()[0].centerOn(item)
                return

        print(f"[LayerSelection] No element found with ID: {element_id}")

    #### Paint Toolbar ####

    @Slot()
    def on_color_picker_clicked(self):
        color = QColorDialog.getColor(self._current_drawing_color, self, "Select Drawing Color")
        if color.isValid():
            self._current_drawing_color = color
            self.update_color_display()
            self.appwin.show_status_message(f"Drawing color set to {color.name()}.", "info")
        else:
            self.appwin.show_status_message("Color picker cancelled.", "info")


    @Slot()
    def on_fill_tool_clicked(self):
        self.appwin.show_status_message("Fill tool selected. Click on an area to fill.", "info")

    @Slot()
    def on_eraser_tool_clicked(self):
        self.appwin.show_status_message("Eraser tool selected. Drag to erase.", "info")

    @Slot()
    def on_brush_tool_clicked(self):
        self.appwin.show_status_message("Brush tool selected. Drag to draw.", "info")

    def on_property_changed(self, payload):
        if not self._current_selected_element:
            return

        setter = PropertySetter(self._current_selected_element, self.settings, self.scene)

        if isinstance(payload, dict):
            prop = payload.get("property")
            value = payload.get("value")
        elif isinstance(payload, tuple) and len(payload) == 2:
            prop, value = payload
        else:
            print(f"Invalid property change payload: {payload}")
            return

        setter_fn = getattr(setter, f"set_{prop}", None)
        if callable(setter_fn):
            setter_fn(value)
        else:
            print(f"No setter defined for property '{prop}'")

    @Slot()
    def set_game_component_background_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Background Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)")
        if path:
            if self.current_template.set_background_image(path):
                self.appwin.show_status_message("Game Component background image set successfully.", "success")
            else:
                self.appwin.show_status_message("Background Error: Could not set background image. File may be invalid.", "error")
        else:
            self.appwin.show_status_message("Background image selection cancelled.", "info")

    def refresh_scene(self):
        self.scene.clear()
        for el in self.current_template.elements:
            self.scene.addItem(el)

    def on_element_type_selected(self, prefix: str):
        self._pending_element_prefix = prefix
        self.status_message_signal.emit(f"Selected element prefix: {prefix}", "info", 3000)

        if hasattr(self.scene, "set_tool_mode"):
            self.scene.set_tool_mode(prefix)

    def on_element_dropped(self, pos: QPointF, prefix: str):
        print(prefix, pos)
        rect = QRectF(pos.x(), pos.y(), 100, 50)
        new_element = self.appwin.registry.create(prefix, rect=rect, template=self.current_template)
        print(new_element.to_dict())
        self.status_message_signal.emit(f"Created new {prefix} at {pos}", "success", 3000)