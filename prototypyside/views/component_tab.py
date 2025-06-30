# prototypyside/views/component_tab.py
from functools import partial
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QDockWidget,
                               QListWidgetItem, QLabel, QPushButton, QComboBox,
                               QSpinBox, QFileDialog, QMessageBox,
                               QCheckBox, QGraphicsItem, QGraphicsView,
                               QGraphicsScene, QToolBar, QLineEdit)
from PySide6.QtCore import Qt, Signal, Slot, QPointF, QRectF, QSizeF, QObject, QSize, QTimer
from PySide6.QtGui import (QPainter, QColor, QIcon, 
                                QKeySequence, QShortcut, QUndoStack)

from prototypyside.views.graphics_scene import ComponentGraphicsScene
from prototypyside.views.graphics_view import DesignerGraphicsView
from prototypyside.views.panels.property_panel import PropertyPanel
from prototypyside.views.panels.layers_panel import LayersListWidget
from prototypyside.views.palettes.palettes import ComponentListWidget
# Import widgets
from prototypyside.widgets.unit_field import UnitField
# from prototypyside.widgets.font_toolbar import FontToolbar
from prototypyside.widgets.pdf_export_dialog import PDFExportDialog


from prototypyside.models.component_elements import (ComponentElement, TextElement, ImageElement)
from prototypyside.services.app_settings import AppSettings
from prototypyside.services.export_manager import ExportManager
from prototypyside.services.property_setter import PropertySetter
from prototypyside.services.geometry_setter import GeometrySetter
from prototypyside.services.undo_commands import (AddElementCommand, RemoveElementCommand, 
            CloneElementCommand, ResizeTemplateCommand, ResizeAndMoveElementCommand)

class ComponentTab(QWidget):
    status_message_signal = Signal(str, str, int)
    tab_title_changed = Signal(str)

    def __init__(self, parent, registry, template):
        super().__init__(parent)
        self.undo_stack = QUndoStack(self)
        self.registry = registry
        self._template = template

        unit = template.width.unit
        print_dpi = template.dpi
        display_dpi = parent.settings.dpi
        self.settings = AppSettings(unit=unit, print_dpi=print_dpi, display_dpi=display_dpi)

        self.geometry_setter = GeometrySetter(self.undo_stack)
        self.property_setter = PropertySetter(self.undo_stack)

        # Setup scene and view
        scene_rect = QRectF(0, 0, template.width_px, template.height_px)
        self.scene = ComponentGraphicsScene(scene_rect=scene_rect, parent=self, tab=self) # Parent is self (ComponentTab)
        self.view = DesignerGraphicsView(self.scene)
        self.view.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.view.setOptimizationFlag(QGraphicsView.DontSavePainterState)
        self.view.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing)        
        self.selected_element: Optional['ComponentElement'] = None

        self.export_manager = ExportManager()

        self._current_drawing_color = QColor(0, 0, 0) # For drawing tools

        self.setup_ui()
        #self.setup_shortcuts()

        self._refresh_scene()

    @property
    def template(self):
        return self._template

    @property
    def template_pid(self):
        return self._template.pid
    
    
    def focusInEvent(self, event):
        super().focusInEvent(event)
        # Assuming you have a way to get the main window, e.g., self.window()
        main_window = self.window()
        if hasattr(main_window, "undo_group"):
            main_window.undo_group.setActiveStack(self.undo_stack)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create toolbars container for flexible layout (e.g., in a HBox)
        toolbar_container = QHBoxLayout()
        toolbar_container.setContentsMargins(0,0,0,0)

        # self.create_font_toolbar()
        self.create_measure_toolbar()

        # Add toolbars to the container (adjust as per desired layout)
        # toolbar_container.addWidget(self.font_toolbar_widget)
        toolbar_container.addWidget(self.measure_toolbar)
  

        main_layout.addLayout(toolbar_container)

        # The QGraphicsView will be the dominant part of the tab
        main_layout.addWidget(self.view)

        # Connect signals specific to this tab's template and scene
        self.template.template_changed.connect(self.update_component_scene)
        self.template.element_z_order_changed.connect(self.update_layers_panel)
        self.scene.selectionChanged.connect(self.on_selection_changed)
        self.scene.element_dropped.connect(self.add_element_from_drop)
        self.scene.element_cloned.connect(self.clone_element)

        # Initialize the property panel and layers panel (their widgets will be placed in docks in QMainWindow)
        self.setup_property_editor()
        self.setup_component_palette()
        self.setup_layers_panel()

        self.set_element_controls_enabled(False) # Initial state: no element selected

    def setup_shortcuts(self):
        delete_shortcut = QShortcut(QKeySequence.Delete, self)
        delete_shortcut.activated.connect(self.remove_selected_element)

    @Slot()
    def update_component_scene(self):
        """Updates the scene dimensions and view based on the current template."""
        if not self.scene or not self.template:
            return

        new_rect = QRectF(0, 0, self.template.width_px, self.template.height_px)
        self.scene.scene_from_template_dimensions(self.template.width_px, self.template.height_px)

        self.view.setSceneRect(new_rect)

        self.scene.update()

    def get_template_name(self) -> str:
        return self.template.name if self.template.name else "Unnamed Template"

    def show_status_message(self, message: str, message_type: str = "info", timeout_ms: int = 5000):
        self.status_message_signal.emit(message, message_type, timeout_ms)

    def setup_component_palette(self):
        # This will be a widget that the QMainWindow will place in a DockWidget
        self.palette = ComponentListWidget()
        components = [
            ("Text Field", "te", "T"),
            ("Image Container", "ie", "🖼️"),
        ]
        for name, etype, icon in components:
            item = QListWidgetItem(f"{icon} {name}")
            item.setData(Qt.UserRole, etype)
            self.palette.addItem(item)
        self.palette.setDragEnabled(True)
        self.palette.palette_item_clicked.connect(self.clear_scene_selection)

    def setup_property_editor(self):
        # This will be a widget that the QMainWindow will place in a DockWidget
        self.property_panel = PropertyPanel(settings=self.settings, parent=self)
        self.property_panel.property_changed.connect(self.on_property_changed)
        self.property_panel.geometry_changed.connect(self.on_geometry_changed)
        self.remove_element_btn = QPushButton("Remove Selected Element")
        self.remove_element_btn.setMaximumWidth(200)
        self.remove_element_btn.clicked.connect(self.remove_selected_element)
        self.set_element_controls_enabled(False) # Ensure this disables the new button too

    def setup_layers_panel(self):
        # This will be a widget that the QMainWindow will place in a DockWidget
        self.layers_list = LayersListWidget(self)
        self.layers_list.element_selected_in_list.connect(self.on_layers_list_item_clicked)
        self.layers_list.element_z_changed_requested.connect(self.reorder_element_z_from_list_event)
        self.layers_list.itemClicked.connect(self.on_layers_list_item_clicked)
        
    # def create_font_toolbar(self):
    #     self.font_toolbar_widget = FontToolbar(self)
    #     font_toolbar = QToolBar("Font Tools")
    #     font_toolbar.addWidget(self.font_toolbar_widget)
    #     self.font_toolbar_widget.font_changed.connect(self.on_font_toolbar_font_changed)
    #     self.font_toolbar_widget.setEnabled(False)
    #     self.layout().addWidget(font_toolbar)

    def create_measure_toolbar(self):
        self.measure_toolbar = QToolBar("Measurement Toolbar")
        self.measure_toolbar.setObjectName("MeasurementToolbar")

        # Unit Selector
        self.unit_selector = QComboBox()
        self.unit_selector.addItems(["in", "cm", "mm", "pt", "px"])
        self.unit_selector.setCurrentText(self.settings.unit)
        self.unit_selector.currentTextChanged.connect(self.on_unit_change)

        # Snap to Grid
        self.snap_checkbox = QCheckBox("Snap to Grid")
        self.snap_checkbox.setChecked(True)
        self.snap_checkbox.stateChanged.connect(self.on_snap_toggle)
        self.snap_to_grid = True

        # Show Grid
        self.grid_checkbox = QCheckBox("Show Grid")
        self.grid_checkbox.setChecked(True)
        self.grid_checkbox.stateChanged.connect(self.on_grid_toggle)
        self.show_grid = True

        self.template_name_field = QLineEdit()
        self.template_name_field.setPlaceholderText(self.template.name)
        self.template_name_field.editingFinished.connect(self.on_template_name_changed)
        self.template_name_field.setMaximumWidth(150)

        self.template_width_field = UnitField(
            initial=self.template.width,
            unit=self.settings.unit,
            dpi=self.template.dpi
        )
        self.template_width_field.setMaximumWidth(100)
        self.template_width_field.editingFinishedWithValue.connect(partial(self.on_template_dimension_changed, "width_px"))

        self.template_height_field = UnitField(
            initial=self.template.height,
            unit=self.settings.unit,
            dpi=self.template.dpi
        )
        self.template_height_field.editingFinishedWithValue.connect(partial(self.on_template_dimension_changed, "height_px"))
        self.template_height_field.setMaximumWidth(100)

        # DPI SpinBox
        self.component_dpi_spin = QSpinBox()
        self.component_dpi_spin.setRange(36, 1200)
        self.component_dpi_spin.setValue(self.template.dpi)
        self.component_dpi_spin.valueChanged.connect(self.on_template_dpi_changed)

        self.measure_toolbar.addWidget(QLabel("Template:"))
        self.measure_toolbar.addWidget(self.template_name_field)
        self.measure_toolbar.addWidget(QLabel("Width:"))
        self.measure_toolbar.addWidget(self.template_width_field)
        self.measure_toolbar.addWidget(QLabel("Height:"))
        self.measure_toolbar.addWidget(self.template_height_field)
        self.measure_toolbar.addWidget(QLabel("DPI:"))
        self.measure_toolbar.addWidget(self.component_dpi_spin)
        self.measure_toolbar.addSeparator()
        self.measure_toolbar.addWidget(QLabel("Unit:"))
        self.measure_toolbar.addWidget(self.unit_selector)
        self.measure_toolbar.addWidget(self.grid_checkbox)
        self.measure_toolbar.addWidget(self.snap_checkbox)
        self.layout().addWidget(self.measure_toolbar)

    @Slot(str)
    def on_unit_change(self, unit: str):
        self.settings.unit = unit
        self.template_width_field.on_unit_changed(unit)
        self.template_height_field.on_unit_changed(unit)
        self.measure_toolbar.update()
        self.property_panel.refresh() # Refresh property panel to update unit fields
        self.scene.update()  # force grid redraw

    @Slot(int)
    def on_snap_toggle(self, state: int):
        self.snap_to_grid = bool(state)
        self.scene.is_snap_to_grid = self.snap_to_grid

    @Slot(int)
    def on_grid_toggle(self, state):
        self.show_grid = bool(state)
        self.measure_toolbar.update()
        self.scene.update()

    @Slot()
    def on_template_name_changed(self):
        new_name = self.template_name_field.text().strip()
        if new_name:
            self.template.name = new_name
            self.tab_title_changed.emit(new_name)

    @Slot(str, object)  # The value is a UnitStr
    def on_template_dimension_changed(self, dimension, value):
        old_width = self.template.width
        old_height = self.template.height
        new_width = value if dimension == "width_px" else old_width
        new_height = value if dimension == "height_px" else old_height
        command = ResizeTemplateCommand(self.template, new_width, new_height)
        self.undo_stack.push(command)
        self._refresh_scene()

    def update_template_scene_rect(self):
        self.scene.scene_from_template_dimensions(
            self.template.width_px,
            self.template.height_px
        )
        self.scene.update()
        self.view.update()
        self.template.template_changed.emit()
        self.tab_title_changed.emit(self.template.name if self.template.name else "Unnamed Template")

    def _refresh_scene(self):
        # Clear old items (grid/background is drawn in drawBackground, not as items)
        self.scene.clear()

        # Make sure scene rect matches template (in case width/height changed)
        self.scene.setSceneRect(0, 0,
                                self.template.width_px,
                                self.template.height_px)

        # Add every element back into the QGraphicsScene
        for element in self.template.elements:
            self.scene.addItem(element)
            element.hide_handles()


    @Slot()
    def on_template_dpi_changed(self):
        new_dpi = self.component_dpi_spin.value()
        self.settings.dpi = new_dpi
        self.template.dpi = new_dpi

        self.template_width_field.set_dpi(new_dpi)
        self.template_height_field.set_dpi(new_dpi)
        self.template_c
        if self.selected_element:
            self.property_panel.set_target(self.selected_element)
            self.property_panel.refresh()

        self.view.viewport().update()
        self.view.update()
        self.scene.update()

        self.template.template_changed.emit()
        self.show_status_message(f"DPI updated to {new_dpi}.", "info")

    @Slot(tuple, tuple)
    def on_geometry_changed(self, new_values, old_values):
        element = self.selected_element
        command = ResizeAndMoveElementCommand(element, new_values, old_values)
        self.undo_stack.push(command)
      

    @Slot()
    def on_property_changed(self, change):
        element = self.get_selected_element()
        if not element or not change:
            return
            
        
        if isinstance(change, tuple) and len(change) == 2 and element is not None:
            self.property_setter.set_prop(element, change)
            #self.property_panel.update_panel_from_element()
            # self.scene.update()

    def get_selected_element(self) -> Optional['ComponentElement']:
        items = self.scene.selectedItems()
        if items:
            return items[0] if isinstance(items[0], ComponentElement) else None
        return None

    def _handle_new_selection(self, new):
        old = self.selected_element
        if old is new:
            return
        
        # Cleanup previous selection
        if old:
            old.hide_handles()
            try:
                old.element_changed.disconnect(self.on_element_data_changed)
            except TypeError:  # Not connected
                pass
        
        # Setup new selection
        self.selected_element = new
        if new:
            new.show_handles()
            new.element_changed.connect(self.on_element_data_changed)
            self.property_panel.set_target(new)
            self.property_panel.refresh()
            self._update_layers_selection(new)
        else:
            self.property_panel.set_target(None)
            self._clear_layers_selection()
        
        self.set_element_controls_enabled(bool(new))

    @Slot()
    def on_selection_changed(self):
        """Handles selection changes from both scene and layers list"""
        # Get selection source (prioritize scene selection)
        if self.scene.selectedItems():
            selected = self.scene.selectedItems()[0]
        else:
            selected = None
        
        self._handle_new_selection(selected)

    @Slot(QListWidgetItem)
    def on_layers_list_item_clicked(self, item):
        """Handles selection from layers list"""
        element = item.data(Qt.UserRole)
        if element:
            self.scene.blockSignals(True)
            self.scene.clearSelection()
            element.setSelected(True)
            self.scene.blockSignals(False)
            self._handle_new_selection(element)

    def _update_layers_selection(self, element):
        """Sync layers list selection with current element"""
        self.layers_list.blockSignals(True)
        self.layers_list.clearSelection()
        
        for i in range(self.layers_list.count()):
            item = self.layers_list.item(i)
            if item.data(Qt.UserRole) is element:
                item.setSelected(True)
                self.layers_list.scrollToItem(item)
                break
        
        self.layers_list.blockSignals(False)

    def _clear_layers_selection(self):
        self.layers_list.blockSignals(True)
        self.layers_list.clearSelection()
        self.layers_list.blockSignals(False)

    @Slot()
    def update_layers_panel(self):
        self.layers_list.update_list(self.template.elements)

    def _adjust_z_value(self, element, new_z):
        """Helper for z-order operations"""
        element.setZValue(new_z)
        self.template.elements.sort(key=lambda e: e.zValue())
        self.template.element_z_order_changed.emit()

    @Slot(int)
    def adjust_z_order_of_selected(self, direction: int):
        if not (element := self.get_selected_element()):
            return
        
        elements = self.template.elements
        sorted_elements = sorted(elements, key=lambda e: e.zValue())
        idx = sorted_elements.index(element)
        
        if direction > 0 and idx < len(sorted_elements) - 1:  # Move up
            next_z = sorted_elements[idx + 1].zValue()
            self._adjust_z_value(element, next_z + 1)
        elif direction < 0 and idx > 0:  # Move down
            prev_z = sorted_elements[idx - 1].zValue()
            self._adjust_z_value(element, prev_z - 1)

    @Slot()
    def bring_selected_to_front(self):
        if element := self.get_selected_element():
            max_z = max(e.zValue() for e in self.template.elements)
            if element.zValue() < max_z:
                self._adjust_z_value(element, max_z + 1)

    @Slot()
    def send_selected_to_back(self):
        if element := self.get_selected_element():
            min_z = min(e.zValue() for e in self.template.elements)
            if element.zValue() > min_z:
                self._adjust_z_value(element, min_z - 1)

    @Slot(object, int)
    def reorder_element_z_from_list_event(self, element: object, direction: int):
        # Reuse existing logic
        self.adjust_z_order_of_selected(direction)

    @Slot(QGraphicsItem)
    def select_element_from_layers_list(self, element: QGraphicsItem):
        if isinstance(element, ComponentElement):
            self.scene.blockSignals(True)
            self.scene.clearSelection()
            element.setSelected(True)
            self.scene.blockSignals(False)


    @Slot()
    def on_element_data_changed(self):
        element = self.get_selected_element()
        if element and element == self.selected_element:
            #self.property_panel.refresh()
            element.update()
            self.scene.update()
        self.update_layers_panel()

    @Slot()
    def clear_scene_selection(self):
        if self.scene.selectedItems():
            self.scene.clearSelection()

    def add_element_from_drop(self, scene_pos: QPointF, element_type: str):
        self.scene.clearSelection()

        command = AddElementCommand(element_type, scene_pos, self)
        self.undo_stack.push(command)
        self.selected_element = self.registry.get_last()

    @Slot(ComponentElement, QPointF)
    def clone_element(self, original, press_scene_pos):
        """Clone via the registry and immediately begin dragging."""
        # 1) Do the registry‐based clone
        original.hide_handles()
        command = CloneElementCommand(original, self)
        # new = self.registry.clone(original)
        self.undo_stack.push(command)
        new = self.registry.get_last()
        self.scene.addItem(new)

        # 2) Place it exactly on top of the original
        new.setPos(original.pos())
        self.scene.select_exclusive(new)
        
        # 3) Compute and stash the drag offset so mouseMoveEvent will pick it up
        drag_offset = press_scene_pos - new.pos()
        self.scene._dragging_item = new
        self.scene._drag_offset   = drag_offset

    def set_element_controls_enabled(self, enabled: bool):
        self.property_panel.setEnabled(enabled)
        self.remove_element_btn.setEnabled(enabled)

    @Slot()
    def remove_selected_element(self):
        element = self.get_selected_element()
        if element:
            reply = QMessageBox.question(self, "Remove Element",
                                         f"Are you sure you want to remove '{element.name}'?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                self.show_status_message("Element removal cancelled.", "info")
                return
            command = RemoveElementCommand(element, self)
            self.undo_stack.push(command)
            self.on_selection_changed()
            self.show_status_message(f"Element '{element.name}' removed.", "info")
        else:
            self.show_status_message("No element selected to remove.", "warning")

    def update_color_display(self):
        self.current_color_display.setStyleSheet(f"background-color: {self._current_drawing_color.name()}; border: 1px solid black;")

    @Slot()
    def set_component_background_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Background Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)")
        if path:
            if self.template.set_background_image(path):
                self.show_status_message("Game Component background image set successfully.", "success")
            else:
                self.show_status_message("Background Error: Could not set background image. File may be invalid.", "error")
        else:
            self.show_status_message("Background image selection cancelled.", "info")
