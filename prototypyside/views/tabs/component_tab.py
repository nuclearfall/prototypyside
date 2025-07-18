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

from prototypyside.views.graphics_scene import ComponentScene
from prototypyside.views.graphics_view import ComponentView
from prototypyside.views.panels.property_panel import PropertyPanel
from prototypyside.views.panels.layers_panel import LayersListWidget
from prototypyside.views.palettes.palettes import ComponentListWidget
# Import widgets
from prototypyside.widgets.unit_field import UnitField, UnitStrGeometryField
from prototypyside.utils.ustr_helpers import geometry_with_px_pos
from prototypyside.utils.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.incremental_grid import IncrementalGrid
# from prototypyside.widgets.font_toolbar import FontToolbar
from prototypyside.widgets.pdf_export_dialog import PDFExportDialog


from prototypyside.models.component_elements import (ComponentElement, TextElement, ImageElement)
from prototypyside.services.app_settings import AppSettings
from prototypyside.services.property_setter import PropertySetter
from prototypyside.services.undo_commands import (AddElementCommand, RemoveElementCommand, 
            CloneElementCommand, ResizeTemplateCommand, ResizeAndMoveElementCommand, ChangeItemPropertyCommand)

class ComponentTab(QWidget):
    status_message_signal = Signal(str, str, int)
    tab_title_changed = Signal(str)
    grid_visibility_changed = Signal(bool)
    grid_snap_changed = Signal(bool)

    def __init__(self, parent, main_window, template, registry):
        super().__init__(parent)
        self.main_window = main_window
        presets = self.main_window.settings
        self.settings = AppSettings(display_dpi=template.geometry.dpi, display_unit=presets.unit, 
                    print_unit=template.geometry.unit, print_dpi=presets.print_dpi)
        self.registry = registry
        self.settings = AppSettings()
        self._template = template
        self.undo_stack = QUndoStack()
        self.file_path = None

        self._unit = self.settings.display_unit
        self._dpi = self.settings.display_dpi
        self._show_grid   = True
        self._snap_grid   = True

        # self.property_setter = PropertySetter(self.undo_stack)
        self.debug_count = 0
        # Setup scene and view
        # scene_rect = template.geometry.px.rect

        # self.scene = ComponentGraphicsScene(scene_rect=scene_rect, parent=self, tab=self) # Parent is self (ComponentTab)
        # self.view = DesignerGraphicsView(self.scene)
        # self.view.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        # self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        # self.view.setOptimizationFlag(QGraphicsView.DontSavePainterState)
        # self.view.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing)
        # self.scene.addItem(self._template)      
        self.selected_item: Optional['ComponentElement'] = None

        self._current_drawing_color = QColor(0, 0, 0) # For drawing tools

        self.setup_ui()

    @property
    def dpi(self): return self._dpi

    @property
    def unit(self):
        return self._unit
    
    @property
    def template(self):
        return self._template

    @template.setter
    def template(self, new):
        if new != self.template and isinstance(new, ComponentTemplate):
            self._template = new

    @property
    def template_pid(self):
        return self._template.pid
    
    def focusInEvent(self, event):
        super().focusInEvent(event)
        # Assuming you have a way to get the main window, e.g., self.window()
        self.main_window = main_window
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


        self.build_scene()
        main_layout.addWidget(self.view)
        # Initialize the property panel and layers panel (their widgets will be placed in docks in QMainWindow)
        self.setup_property_editor()
        self.setup_component_palette()
        self.setup_layers_panel()

        self.set_item_controls_enabled(False) # Initial state: no item selected

    def build_scene(self):
        # create grid
        self.inc_grid = IncrementalGrid(self.settings, snap_enabled=self._snap_grid, parent=self.template)
        self.scene = ComponentScene(self.settings, grid=self.inc_grid, template=self.template, parent=self)
        self.scene.setSceneRect(self.template.geometry.px.rect)
        self.view  = ComponentView(self.scene, self)
        # self.template.setZValue()

        self.scene.addItem(self.inc_grid)

        # connect visibility / snapping controls
        self.grid_visibility_changed.connect(self.inc_grid.setVisible)
        self.grid_snap_changed.connect(self.inc_grid.setSnapEnabled)

        # initialise from current flags
        self.inc_grid.setVisible(self._show_grid)
        self.scene.addItem(self.template)

        # Connect signals specific to this tab's template and scene
        self.template.template_changed.connect(self.update_component_scene)
        self.template.item_z_order_changed.connect(self.update_layers_panel)
        self.scene.selectionChanged.connect(self.on_selection_changed)
        self.scene.item_dropped.connect(self.add_item_from_drop)
        self.scene.item_cloned.connect(self.clone_item)
        self.scene.item_resized.connect(self.on_property_changed)
        self.view.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.view.setOptimizationFlag(QGraphicsView.DontSavePainterState)
        self.view.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing)
        self.view.setScene(self.scene)
        # self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def setup_shortcuts(self):
        delete_shortcut = QShortcut(QKeySequence.Delete, self)
        delete_shortcut.activated.connect(self.remove_selected_item)

    @Slot()
    def update_component_scene(self):
        """Updates the scene dimensions and view based on the current template."""
        if not self.scene or not self.template:
            return

        self.view.setSceneRect(self._template.geometry.px.rect)

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
        self.property_panel = PropertyPanel(display_unit=self.unit, parent=self)
        self.property_panel.property_changed.connect(self.on_property_changed)
        # self.property_panel.geometry_changed.connect(self.on_geometry_changed)
        self.remove_item_btn = QPushButton("Remove Selected Element")
        self.remove_item_btn.setMaximumWidth(200)
        self.remove_item_btn.clicked.connect(self.remove_selected_item)
        self.set_item_controls_enabled(False) # Ensure this disables the new button too

    def setup_layers_panel(self):
        # This will be a widget that the QMainWindow will place in a DockWidget
        self.layers_list = LayersListWidget(self)
        self.layers_list.item_selected_in_list.connect(self.on_layers_list_item_clicked)
        self.layers_list.item_z_changed_requested.connect(self.reorder_item_z_from_list_event)
        self.layers_list.itemClicked.connect(self.on_layers_list_item_clicked)

    def create_measure_toolbar(self):
        self.measure_toolbar = QToolBar("Measurement Toolbar")
        self.measure_toolbar.setObjectName("MeasurementToolbar")

        # Unit Selector
        self.unit_selector = QComboBox()
        self.unit_selector.addItems(["in", "cm", "mm", "pt", "px"])
        self.unit_selector.setCurrentText(self._unit)
        self.unit_selector.currentTextChanged.connect(self.on_unit_change) 

        # Snap to Grid
        self.snap_checkbox = QCheckBox("Snap to Grid")
        self.snap_checkbox.setChecked(True)
        self.snap_checkbox.stateChanged.connect(self.toggle_snap)
        self.snap_to_grid = True

        # Show Grid
        self.grid_checkbox = QCheckBox("Show Grid")
        self.grid_checkbox.setChecked(True)
        self.grid_checkbox.stateChanged.connect(self.toggle_grid)


        self.template_name_field = QLineEdit()
        self.template_name_field.setPlaceholderText(self.template.name)
        self.template_name_field.editingFinished.connect(self.on_template_name_changed)
        self.template_name_field.setMaximumWidth(150)
        width = self.template.geometry.width # Unit Str value
        height = self.template.geometry.height # Unit Str value
        self.template_width_field = UnitField(self.template, "width", display_unit=self.unit)
        self.template_height_field = UnitField(self.template, "height", display_unit=self.unit)
        for dim in [self.template_width_field, self.template_height_field]:
            dim.setMaximumWidth(100)
            dim.valueChanged.connect(self.on_template_geometry_changed)

        self.border_label = QLabel("Border")
        self.border_width_field = UnitField(self.template, "border", self.unit, self)
        self.border_width_field.valueChanged.connect(self.set_template_border)
        self.border_width_field.setMaximumWidth(80)
        self.corners_label = QLabel("Corner Radius")
        self.corners_field = UnitField(self.template, "corner_radius", self.unit, self)
        self.corners_field.valueChanged.connect(self.on_corner_radius_change)
        self.corners_field.setMaximumWidth(80)

        
        self.measure_toolbar.addWidget(QLabel("Template:"))
        self.measure_toolbar.addWidget(self.template_name_field)
        self.measure_toolbar.addSeparator()
        self.measure_toolbar.addWidget(QLabel("Unit:"))
        self.measure_toolbar.addWidget(self.unit_selector)
        self.measure_toolbar.addWidget(self.grid_checkbox)
        self.measure_toolbar.addWidget(self.template_width_field)
        self.measure_toolbar.addWidget(self.template_height_field)
        self.measure_toolbar.addWidget(self.snap_checkbox)
        self.measure_toolbar.addWidget(self.border_label)
        self.measure_toolbar.addWidget(self.border_width_field)
        self.measure_toolbar.addWidget(self.corners_label)
        self.measure_toolbar.addWidget(self.corners_field)

        self.layout().addWidget(self.measure_toolbar)

    @Slot(str)
    def on_unit_change(self, unit: str):
        self.settings.unit = unit
        self.template_width_field.on_unit_change(unit)
        self.template_height_field.on_unit_change(unit)
        self.measure_toolbar.update()
        self.property_panel.on_unit_change(unit)
        # self.scene.on_unit_change(unit)
        # self.scene.update()  # force grid redraw

    @Slot(int)
    def on_corner_radius_change(self, new_value: int):
        self.template.corner_radius = new_value

    # called from menu/toolbar checkboxes:
    def toggle_grid(self, checked: bool):
        self._show_grid = checked
        self.grid_visibility_changed.emit(checked)

    def toggle_snap(self, checked: bool):
        self._snap_grid = checked
        self.grid_snap_changed.emit(checked)

    @Slot()
    def set_template_border(self, t, p, new, old):
        setattr(t, p, new)

    @Slot()
    def on_template_name_changed(self):
        new_name = self.template_name_field.text().strip()
        if new_name:
            self.template.name = new_name
            self.tab_title_changed.emit(new_name)

    @Slot(object, str, object, object)  # The value is a UnitStr
    def on_template_geometry_changed(self, target, prop, new, old):
        if prop == "width":
            w = new
            h = target.geometry.height
        elif prop == "height":
            h = new
            w = target.geometry.width
        old_geom = self.template.geometry
        new_geom = UnitStrGeometry(width=w, height=h)
        command = ResizeTemplateCommand(target, new_geom, old_geom)
        self.undo_stack.push(command)
        print(f"[GEOMETRY] After resize template dimensions: {target.geometry}")
        self.scene.setSceneRect(target.geometry.px.rect)
        self.view

    def _refresh_scene(self):
        # Clear old items (grid/background is drawn in drawBackground, not as items)
        self.scene.clear()
        self.scene.setSceneRect(self.template.geometry.px.rect)
        # Add every item back into the QGraphicsScene
        if not self.template.scene():
            self.scene.addItem(self.template)
        for item in self.template.items:
            if not item.scene():
                self.scene.addItem(item)
            item.hide_handles()

    @Slot()
    def on_property_changed(self, target, prop, new, old):
        command = ChangeItemPropertyCommand(target, prop, new, old)
        self.undo_stack.push(command)
        print(f"[COMPONENT TAB] Target={target}, prop={prop}, old={old}, new={new}")
        print(f"[UNDO STACK] Pushed: {command}")

    def get_selected_item(self) -> Optional['ComponentElement']:
        items = self.scene.selectedItems()
        if items:
            return items[0] if isinstance(items[0], ComponentElement) else None
        return None

    def _handle_new_selection(self, new):
        old = self.selected_item
        if old is new:
            return

        # Cleanup previous selection
        if old:
            old.hide_handles()
            try:
                old.item_changed.disconnect(self.on_item_data_changed)
            except RuntimeError:
                pass  # Signal wasn't connected

        # Update selection
        self.selected_item = new

        if new:
            new.show_handles()
            try:
                new.item_changed.connect(self.on_item_data_changed)
            except RuntimeError:
                pass  # Already connected, which shouldn't happen due to above logic

            self.property_panel.set_target(new)
            self._update_layers_selection(new)
        else:
            self.property_panel.clear_target()
            self._clear_layers_selection()

        self.set_item_controls_enabled(bool(new))


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
        item = item.data(Qt.UserRole)
        if item:
            self.scene.blockSignals(True)
            self.scene.clearSelection()
            item.setSelected(True)
            self.scene.blockSignals(False)
            self._handle_new_selection(item)

    def _update_layers_selection(self, item):
        """Sync layers list selection with current item"""
        self.layers_list.blockSignals(True)
        self.layers_list.clearSelection()
        
        for i in range(self.layers_list.count()):
            item = self.layers_list.item(i)
            if item.data(Qt.UserRole) is item:
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
        self.layers_list.update_list(self.template.items)

    def _adjust_z_value(self, item, new_z):
        """Helper for z-order operations"""
        item.setZValue(new_z)
        self.template.items.sort(key=lambda e: e.zValue())
        self.template.item_z_order_changed.emit()

    @Slot(int)
    def adjust_z_order_of_selected(self, direction: int):
        if not (item := self.get_selected_item()):
            return
        
        items = self.template.items
        sorted_items = sorted(items, key=lambda e: e.zValue())
        idx = sorted_items.index(item)
        
        if direction > 0 and idx < len(sorted_items) - 1:  # Move up
            next_z = sorted_items[idx + 1].zValue()
            self._adjust_z_value(item, next_z + 1)
        elif direction < 0 and idx > 0:  # Move down
            prev_z = sorted_items[idx - 1].zValue()
            self._adjust_z_value(item, prev_z - 1)

    @Slot()
    def bring_selected_to_front(self):
        if item := self.get_selected_item():
            max_z = max(e.zValue() for e in self.template.items)
            if item.zValue() < max_z:
                self._adjust_z_value(item, max_z + 1)

    @Slot()
    def send_selected_to_back(self):
        if item := self.get_selected_item():
            min_z = min(e.zValue() for e in self.template.items)
            if item.zValue() > min_z:
                self._adjust_z_value(item, min_z - 1)

    @Slot(object, int)
    def reorder_item_z_from_list_event(self, item: object, direction: int):
        # Reuse existing logic
        self.adjust_z_order_of_selected(direction)

    @Slot(QGraphicsItem)
    def select_item_from_layers_list(self, item: QGraphicsItem):
        if isinstance(item, ComponentElement):
            self.scene.blockSignals(True)
            self.scene.clearSelection()
            item.setSelected(True)
            self.scene.blockSignals(False)


    @Slot()
    def on_item_data_changed(self):
        self.selected_item.update()
        pass
        # item = self.get_selected_item()
        # if item and item == self.selected_item:
        #     item.update()
        #     self.scene.update()

    @Slot()
    def clear_scene_selection(self):
        if self.scene.selectedItems():
            self.scene.clearSelection()

    def add_item_from_drop(self, scene_pos: QPointF, item_type: str):
        self.scene.clearSelection()
        rect = UnitStrGeometry(width="0.5in", height="0.25in", dpi=self.template.dpi)
        new_geometry = geometry_with_px_pos(rect, scene_pos)
        command = AddElementCommand(item_type, self, new_geometry)
        self.undo_stack.push(command)
        self.selected_item = self.registry.get_last()
        tz = self.template.zValue()
        gz = self.inc_grid.zValue()
        ezs = [e.zValue() for e in self.template.items]
        print(f"[Z_ORDER] zOrdering after item placement: Template {tz}, Grid {gz}, Elements {ezs}")

    @Slot(ComponentElement, QPointF)
    def clone_item(self, original, press_scene_pos):
        """Clone via the registry and immediately begin dragging."""
        # 1) Do the registry‐based clone
        original.hide_handles()
        command = CloneElementCommand(original, self)
        # new = self.registry.clone(original)
        self.undo_stack.push(command)
        new = self.registry.get_last()
        new.setParentItem(self.template)
        self.scene.addItem(new)

        # 2) Place it exactly on top of the original
        new.setPos(original.pos())
        self.scene.select_exclusive(new)
        
        # 3) Compute and stash the drag offset so mouseMoveEvent will pick it up
        drag_offset = press_scene_pos - new.pos()
        self.scene._dragging_item = new
        self.scene._drag_offset   = drag_offset

    def set_item_controls_enabled(self, enabled: bool):
        self.property_panel.setEnabled(enabled)
        self.remove_item_btn.setEnabled(enabled)

    @Slot()
    def remove_selected_item(self):
        item = self.get_selected_item()
        if item:
            reply = QMessageBox.question(self, "Remove Element",
                                         f"Are you sure you want to remove '{item.name}'?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                self.show_status_message("Element removal cancelled.", "info")
                return
            command = RemoveElementCommand(item, self)
            self.undo_stack.push(command)
            self.on_selection_changed()
            self.show_status_message(f"Element '{item.name}' removed.", "info")
        else:
            self.show_status_message("No item selected to remove.", "warning")

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
