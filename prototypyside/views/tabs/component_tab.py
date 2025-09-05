# prototypyside/views/component_tab.py

from typing import Optional, TYPE_CHECKING
from functools import partial

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QCheckBox,
    QLineEdit, QLabel, QToolBar, QListWidgetItem, QMessageBox, QGraphicsView,
    QWidgetAction, QSizePolicy, QFrame
)
from PySide6.QtCore import Qt, Signal, Slot, QPointF
from PySide6.QtGui import QColor, QKeySequence, QShortcut, QUndoStack, QPainter

from prototypyside.views.component_scene import ComponentScene
from prototypyside.views.component_view import ComponentView
from prototypyside.views.toolbars.font_toolbar import FontToolbar
from prototypyside.views.palettes.element_palette import ElementPalette
from prototypyside.views.panels.property_panel import PropertyPanel
from prototypyside.views.panels.layers_panel import LayersListWidget
from prototypyside.views.palettes.palettes import ComponentListWidget
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.widgets.unit_str_field import UnitStrField
from prototypyside.widgets.unit_str_geometry_field import UnitStrGeometryField
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.units.unit_str_helpers import geometry_with_px_pos
from prototypyside.views.overlays.incremental_grid import IncrementalGrid
from prototypyside.services.proto_class import ProtoClass
from prototypyside.models.component_element import ComponentElement

from prototypyside.services.app_settings import AppSettings

from prototypyside.services.undo_commands import (
    AddElementCommand, RemoveElementCommand, CloneElementCommand,
    ResizeTemplateCommand, ChangePropertyCommand
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QGraphicsItem

def vsep():
    s = QFrame()
    s.setFrameShape(QFrame.VLine)
    s.setFrameShadow(QFrame.Sunken)
    return s

class ComponentTab(QWidget):
    status_message_signal = Signal(str, str, int)
    tab_title_changed = Signal(str)
    grid_visibility_changed = Signal(bool)
    grid_snap_changed = Signal(bool)
    print_line_visibility_changed = Signal(bool)

    def __init__(self, parent, main_window, template, registry):
        super().__init__(parent)
        self.main_window = main_window
        presets = self.main_window.settings
        self.settings = presets
        self._dpi = self.settings.dpi           # <- REQUIRED: no fallback, no None
        self._unit = self.settings.unit         # scene logical unit (e.g., "in")
        self._template = template
        self.undo_stack = QUndoStack()
        self.file_path = None
        self.registry = registry
        self._show_grid   = True
        self._snap_grid   = True
        # self._print_lines = True

        self.selected_item: Optional[object] = None

        self._current_drawing_color = QColor(0, 0, 0) # For drawing tools

        self.setup_ui()
    
    def focusInEvent(self, event):
        super().focusInEvent(event)
        # Assuming you have a way to get the main window, e.g., self.window()
        main_window = self.main_window
        if hasattr(main_window, "undo_group"):
            main_window.undo_group.setActiveStack(self.undo_stack)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create toolbars container for flexible layout (e.g., in a HBox)
        toolbar_container = QHBoxLayout()
        toolbar_container.setContentsMargins(0,0,0,0)

        self.create_toolbar()
        #toolbar_container.addWidget(self.measure_bar)

        main_layout.addLayout(toolbar_container)

        # The QGraphicsView will be the dominant part of the tab


        self.build_scene()
        main_layout.addWidget(self.view)
        # Initialize the property panel and layers panel (their widgets will be placed in docks in QMainWindow)
        self.setup_property_editor()
        self.setup_element_palette()
        self.setup_layers_panel()
        #self._setup_shortcuts()
        self.set_item_controls_enabled(False) # Initial state: no item selected

    def build_scene(self):
        # create grid
        rect = self.template.geometry.to("px", dpi=self._dpi).rect
        self.inc_grid = IncrementalGrid(self.settings, snap_enabled=self._snap_grid, parent=self.template)
        self.scene = ComponentScene(self.settings, template=self.template, grid=self.inc_grid)
        if not self.template.scene():
            self.scene.addItem(self.template)
        for el in self.template.items:
            print(f"el is type: {type(el)}")
            el.setParentItem(self.template)
            if not el.scene():
                self.scene.addItem(el)
        self.scene.setSceneRect(rect)
        # print(f"Scene rect in pixels is {self.template.geometry.to("px", dpi=self.settings.dpi).rect}")
        self.view  = ComponentView(self.scene)
        self.view.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.view.setOptimizationFlag(QGraphicsView.DontSavePainterState)
        self.view.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing)
        self.view.setScene(self.scene)
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
        self.view.show()

        # connect visibility / snapping controls
        self.grid_visibility_changed.connect(self.inc_grid.setVisible)
        self.grid_snap_changed.connect(self.inc_grid.setSnapEnabled)

        # initialise from current flags
        self.inc_grid.setVisible(self._show_grid)

        # Connect signals specific to this tab's template and scene
        self.template.template_changed.connect(self.update_component_scene)
        self.template.item_z_order_changed.connect(self.update_layers_panel)
        self.scene.selectionChanged.connect(self.on_selection_changed)
        self.scene.item_dropped.connect(self.add_item_from_drop)
        self.scene.item_cloned.connect(self.clone_item)
        self.scene.item_resized.connect(self.on_property_changed)

    @Slot()
    def update_component_scene(self):
        if not self.scene or not self.template:
            return
        # keep the checkbox/field in sync with the current model value
        self.bleed_checkbox.blockSignals(True)
        self.bleed_checkbox.setChecked(bool(getattr(self.template, "include_bleed", False)))
        self.bleed_checkbox.blockSignals(False)

        self.bleed_field.setEnabled(self.bleed_checkbox.isChecked())

        self.view.setSceneRect(self._template.geometry.px.rect)
        self.scene.sync_scene_rect()
        self.scene.update()

    def get_template_name(self) -> str:
        return self.template.name if self.template.name else "Unnamed Template"

    def show_status_message(self, message: str, message_type: str = "info", timeout_ms: int = 5000):
        self.status_message_signal.emit(message, message_type, timeout_ms)

    def setup_element_palette(self):
        self.palette = ElementPalette()
        components = [
            ("Text Field", "te", "T"),
            ("Image Container", "ie", "🖼️"),
            ("Vector Graphic", "ve", "⬠"),
        ]
        for name, etype, icon in components:
            self.palette.add_item(name, etype, icon)
        self.palette.on_item_type_selected.connect(self.clear_scene_selection)
        #self.palette.on_item_type_selected.connect(self.add_item_from_drop)
        # User clicks a type in the palette; scene arms creation mode.
        #self.palette.on_item_type_selected.connect(self.scene.arm_element_creation)
        # If scene cancels (mouse move, key, focus, or invalid press), clear the palette highlight.
        self.scene.creation_cancelled.connect(self.palette.clear_active_selection)
        # self.scene.item_dropped.connect(self.add_item_from_drop)
        # --- NEW: Scene -> Tab (Step 6 → 7) ---
        #mself.scene.create_item_with_dims.connect(self.add_item_with_dims)

    def setup_property_editor(self):
        # This will be a widget that the QMainWindow will place in a DockWidget
        self.property_panel = PropertyPanel(None, display_unit=self.unit, parent=self, dpi=self.settings.dpi)
        self.property_panel.property_changed.connect(self.on_property_changed)
        # self.property_panel.geometry_changed.connect(self.on_geometry_changed)
        self.remove_item_btn = QPushButton("Remove Selected Element")
        self.remove_item_btn.setMaximumWidth(200)
        self.remove_item_btn.clicked.connect(self.remove_selected_item)
        self.set_item_controls_enabled(False) # Ensure this disables the new button too

    def setup_layers_panel(self):
        self.layers_list = LayersListWidget(self)
        self.layers_list.item_selected_in_list.connect(self.on_layers_list_item_clicked)
        self.layers_list.item_z_changed_requested.connect(self.reorder_item_z_from_list_event)
        self.layers_list.itemClicked.connect(self.on_layers_list_item_clicked)

    def create_toolbar(self):
        self.toolbar = QToolBar()

        self.measure_bar = QWidget()
        self.measure_bar.setObjectName("MeasurementToolbar")
        measure_layout = QHBoxLayout()

        # Unit Selector
        self.unit_label = QLabel("Unit:")
        self.unit_selector = QComboBox()
        self.unit_selector.addItems(["in", "cm", "mm", "pt", "px"])
        self.unit_selector.setCurrentText(self._unit)
        self.unit_selector.currentTextChanged.connect(self.on_unit_change) 

        # Snap to Grid
        self.snap_checkbox = QCheckBox("Snap to Grid")
        self.snap_checkbox.setChecked(True)
        self.snap_checkbox.stateChanged.connect(self.toggle_snap)

        # Show Grid
        self.grid_checkbox = QCheckBox("Show Grid")
        self.grid_checkbox.setChecked(True)
        self.grid_checkbox.stateChanged.connect(self.toggle_grid)

        self.template_dims_field = UnitStrGeometryField(self.template, "geometry", labels=["Width", "Height"], display_unit=self.settings.display_unit, 
                decimal_places=2, stack_cls=QHBoxLayout, dpi=self._dpi)
        self.template_dims_field.valueChanged.connect(self.on_property_changed)
        self.template_dims_field.setMaximumWidth(250)
 
        self.bleed_label = QLabel("Bleed")
        self.bleed_checkbox = QCheckBox("Add Bleed")
        self.bleed_checkbox.setChecked(bool(getattr(self.template, "include_bleed", False)))
        self.bleed_checkbox.toggled.connect(self.toggle_bleed)
        self.bleed_field = UnitStrField(self.template, "bleed", display_unit=self.unit, dpi=self._dpi)
        self.bleed_field.valueChanged.connect(self.on_property_changed)
        self.bleed_field.setMaximumWidth(60)   
        self.bleed_field.setEnabled(self.bleed_checkbox.isChecked())
        self.border_label = QLabel("Border")
        self.border_width_field = UnitStrField(self.template, "border_width", display_unit=self.unit, dpi=self._dpi)
        self.border_width_field.valueChanged.connect(self.on_property_changed)
        self.border_width_field.setMaximumWidth(60)
        self.corners_label = QLabel("Corner Radius")
        self.corners_field = UnitStrField(self.template, "corner_radius", display_unit=self.unit, dpi=self._dpi)
        self.corners_field.valueChanged.connect(self.on_property_changed)
        self.corners_field.setMaximumWidth(60)


        for widget in [
            self.unit_label,
            self.unit_selector,
            vsep(),
            self.snap_checkbox, 
            self.grid_checkbox,
            vsep(),
            self.template_dims_field,
            self.bleed_label,
            self.bleed_checkbox,
            self.bleed_field,
            self.corners_label,
            self.corners_field,
        ]:
            # widget.setMinimumHeight(30)
            measure_layout.addWidget(widget)

        self.measure_bar.setLayout(measure_layout)
        # self.measure_bar.setMaximumHeight(36)
        self.toolbar.addWidget(self.measure_bar)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)  # or TextBesideIcon, your call
        # self.toolbar.setMinimumHeight(max(self.toolbar.minimumHeight(), 28))
        self.toolbar.setIconSize(self.toolbar.iconSize()) 
        self.toolbar.setIconSize(self.toolbar.iconSize())  # forces a re-layout

        self.layout().addWidget(self.toolbar)

    @property
    def dpi(self):
        self._dpi

    @dpi.setter
    def dpi(self, value):
        self._dpi = value

    @property
    def unit(self):
        return self._unit
    
    @property
    def template(self):
        return self._template

    @template.setter
    def template(self, new):
        if new != self._template and isinstance(new, ProtoClass.CT):
            self._template = new

    @Slot(str)
    def on_unit_change(self, unit: str):
        self.settings.unit = unit
        self.template_dims_field.on_unit_change(unit)
        self.measure_bar.update()
        self.property_panel.on_unit_change(unit)

    # called from menu/toolbar checkboxes:
    def toggle_grid(self, checked: bool):
        self._show_grid = checked
        self.inc_grid.setVisible(self._show_grid)

    def toggle_snap(self, checked: bool):
        self._snap_grid = checked
        self.grid_snap_changed.emit(checked)

    def toggle_bleed(self, checked: bool):
        new = bool(checked)
        old = bool(getattr(self.template, "include_bleed", False))
        if new == old:
            return

        # If boundingRect() depends on include_bleed, this is essential:
        self.template.prepareGeometryChange()
        self.on_property_changed(self.template, "include_bleed", new, old)

        self.bleed_field.setEnabled(new)

        # Recalculate scene rect AFTER the property change
        self.scene.sync_scene_rect()

    @Slot()
    def on_property_changed(self, target, prop, new, old):
        command = ChangePropertyCommand(target, prop, new, old)
        self.undo_stack.push(command)

    def get_selected_item(self) -> Optional[ComponentElement]:
        items = self.scene.selectedItems()
        if items:
            return items[0] if isinstance(items[0], ComponentElement) else None
        return None

    # def clear(self):
    #     self.clear_scene_selection()
    #     i = 0
    #     while i < len(self.template.items):
    #         self.template.remove_item(i)
    #         i += 1
    #     self.scene.selectedItems() = []


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
            target = selected = self.scene.selectedItems()[0]
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

    @Slot("QGraphicsItem")
    def select_item_from_layers_list(self, item: "QGraphicsItem"):
        if isinstance(item, ComponentElement):
            self.scene.blockSignals(True)
            self.scene.clearSelection()
            item.setSelected(True)
            self.scene.blockSignals(False)

    @Slot()
    def on_item_data_changed(self):
        self.selected_item.update()
        pass

    @Slot()
    def clear_scene_selection(self):
        if self.scene.selectedItems():
            self.scene.clearSelection()

    @Slot(ProtoClass)
    def add_item_from_action(self, proto: ProtoClass):
        pass
        # proto = ProtoClass.from_prefix(prefix)
        # if proto:
        #     # set the defaults to reasonable values
        #     default_geom = UnitStrGeometry(width="0.75in", height="0.5in", 
        #         x="0.125in", y="0.125.in", dpi=self.settings.dpi)
        #     command = AddElementCommand(proto, self, default_geom)
        #     self.undo_stack.push(command)
        #     self.selected_item = self.registry.get_last()
        #     self.selected_item.resize_finished.connect(self.scene.on_item_resize_finished)

    @Slot(ProtoClass, object)
    def add_item_with_dims(self, proto: ProtoClass, geom):
        """
        Scene finished a click-drag create. Make it undoable via AddElementCommand.
        Select the created item and wire the resize_finished signal.
        """
        command = AddElementCommand(proto, self, geom)
        self.undo_stack.push(command)

        # Select last-created element
        self.selected_item = self.registry.get_last()

        # When user finishes adjusting handles, let the scene reconcile state
        self.selected_item.resize_finished.connect(self.scene.on_item_resize_finished)

    @Slot(ProtoClass, object)
    def add_item_from_drop(self, proto: ProtoClass, scene_pos: QPointF):
        self.scene.clearSelection()
        # set the defaults to reasonable values
        x = UnitStr(scene_pos.x(), dpi=self.dpi)
        y = UnitStr(scene_pos.y(), dpi=self.dpi)

        geom = UnitStrGeometry(width="0.8125 in", height="0.5in", 
            x=x, y=y, dpi=self.settings.dpi)
        command = AddElementCommand(proto, self, geom)
        self.undo_stack.push(command)
        self.selected_item = self.registry.get_last()
        self.selected_item.resize_finished.connect(self.scene.on_item_resize_finished)

    @Slot(object, object)
    def clone_item(self, original, new_geometry):
        """Clone via the registry and immediately begin dragging."""
        # 1) Do the registry‐based clone
        # original.hide_handles()
        # command = CloneElementCommand(original, self)
        # self.undo_stack.push(command)
        old_geometry = original.geometry
        new = self.registry.clone(original, register=True)
        new.geometry = new_geometry

        # Set the parent in the Qt scene graph for UI behavior.
        new.setParentItem(self.template)
        new.show()
        self.template.update()
        self.scene.update()
        print("From ComponentTab:")
        print(f" - scene rect: {self.scene.sceneRect()}")
        print(f" - clone pid, geometry, pos, and rect:\n - pid: {new.pid}\n   - geometry: {new.geometry.px}\n   - pos: {new.scenePos()}\n   - rect: {new.boundingRect()}")
        print(f"   - original object pid and geometry:\n   - pid: {self.scene.alt_drag_original_item.pid}\n   - geometry: {self.scene.alt_drag_original_item.geometry.px}")
        print(f" - clone has scene: {True if new.scene() else False}")
        print(f" - clone scene is template scene: {True if self.template.scene() == new.scene() else False}")
        print(f" - clone scene is template scene: {True if self.template.scene() == new.scene() else False}")
        print(f" - clone exists in this registry: {True if self.registry.get(new.pid) else False}")
        print(f" - clone exists in tab's scene: {True if self.scene == new.scene() else False}")
        new.update()
        new.show()
        self.update_layers_panel()

        # drag_offset = press_scene_pos - new.pos()
        # self.scene._dragging_item = new
        # self.scene._drag_offset   = drag_offset

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
