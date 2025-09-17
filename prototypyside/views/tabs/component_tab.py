# prototypyside/views/component_tab.py

from typing import Optional, TYPE_CHECKING
from functools import partial

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QCheckBox,
    QLineEdit, QLabel, QToolBar, QListWidgetItem, QMessageBox, QGraphicsView,
    QWidgetAction, QSizePolicy, QFrame, QGraphicsObject
)
from PySide6.QtCore import Qt, Signal, Slot, QPointF, QObject, QEvent 
from PySide6.QtGui import QColor, QKeySequence, QShortcut, QUndoStack, QPainter

from prototypyside.views.component_scene import ComponentScene
from prototypyside.views.component_view import ComponentView
from prototypyside.views.toolbars.font_toolbar import FontToolbar
from prototypyside.views.palettes.element_palette import ElementPalette
from prototypyside.views.panels.property_panel import PropertyPanel
from prototypyside.views.panels.component_property_panel import ComponentPropertyPanel
from prototypyside.views.panels.layers_panel import LayersListWidget
from prototypyside.views.palettes.palettes import ComponentListWidget
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.widgets.unit_str_field import UnitStrField
from prototypyside.widgets.unit_str_geometry_field import UnitStrGeometryField
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.units.unit_str_helpers import geometry_with_px_pos
from prototypyside.services.proto_class import ProtoClass
from prototypyside.models.component_element import ComponentElement

from prototypyside.services.app_settings import AppSettings

from prototypyside.services.undo_commands import (
    AddElementCommand, RemoveElementCommand, CloneElementCommand,
    ResizeTemplateCommand, ChangePropertyCommand, MoveSelectionCommand
)
pc = ProtoClass
elem_types = (pc.CE, pc.TE, pc.IE, pc.VE)

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
        self.settings = AppSettings(
            display_unit=presets.display_unit, 
            print_unit=presets.print_unit
        )
        self._dpi = self.settings.dpi           # <- REQUIRED: no fallback, no None
        self._unit = self.settings.unit         # scene logical unit (e.g., "in")
        self._template = template
        self.undo_stack = QUndoStack()
        self.file_path = None
        self.registry = registry
        self._show_grid   = True
        self._snap_grid   = True

        # state to aggregate a gesture:
        self._gesture_active = False
        self._old_rects = {}   # item -> QRectF
        self._new_rects = {}   # item -> QRectF
        self._old_positions = {}  # item -> QPointF
        self._new_positions = {}
        self._old_by_item = {}  # {item: UnitStrGeometry}
        self._new_by_item = {}  # {item: UnitStrGeometry}
        self._connected_items = []
        # self.selected_item: Optional[object] = None
        for item in self.template.items:
            self._connect_item_signals(item)
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
        # The QGraphicsView will be the dominant part of the tab

        self.build_scene()
        main_layout.addWidget(self.view)
        # Initialize the property panel and layers panel (their widgets will be placed in docks in QMainWindow)
        self.create_right_dock()
        self.setup_element_palette()
        self.setup_layers_panel()
        self.create_left_dock()
        #self._setup_shortcuts()

    def build_scene(self):
        # create grid
        rect = self.template.geometry.to("px", dpi=self._dpi).rect
        self.scene = ComponentScene(self.settings, template=self.template)

        if not self.template.scene():
            self.scene.addItem(self.template)
        self.scene.setSceneRect(rect)
        self.inc_grid = self.scene.inc_grid
        # print(f"Scene rect in pixels is {self.template.geometry.to("px", dpi=self.settings.dpi).rect}")
        self.view = ComponentView(self.scene)
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
        # self.template.item_z_order_changed.connect(self.update_layers_panel)
        self.scene.selectionChanged.connect(self.on_selection_changed)

        # hook scene press/release to bracket gestures
        self.scene.installEventFilter(self)
        self.scene.item_dropped.connect(self.add_item_from_drop)
        self.scene.item_cloned.connect(self.clone_item)
        # self.scene.item_resized.connect(self.on_property_changed)

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
        self.palette.on_item_type_selected.connect(self.scene.arm_element_creation)
        # If scene cancels (mouse move, key, focus, or invalid press), clear the palette highlight.
        self.scene.creation_cancelled.connect(self.palette.clear_active_selection)
        # self.scene.item_dropped.connect(self.add_item_from_drop)
        # --- NEW: Scene -> Tab (Step 6 → 7) ---
        self.scene.create_item_with_dims.connect(self.add_item_with_dims)

    def create_right_dock(self):
        # This will be a widget that the QMainWindow will place in a DockWidget
        self.right_dock = QWidget()
        layout = QVBoxLayout()
        self.property_panel = PropertyPanel(None, display_unit=self.unit, parent=self, dpi=self.settings.dpi)
        self.property_panel.property_changed.connect(self.on_property_changed)
        self.property_panel.batch_property_changed.connect(self.on_batch_property_changed)
        # self.property_panel.geometry_changed.connect(self.on_geometry_changed)
        self.remove_item_btn = QPushButton("Remove Selected Element")
        self.remove_item_btn.setMaximumWidth(200)
        self.remove_item_btn.clicked.connect(self.remove_selected_item)
        self.comp_prop_panel = ComponentPropertyPanel(
            target=self.template, 
            display_unit=self.settings.display_unit,
            dpi=self.settings.dpi)
        self.comp_prop_panel.property_changed.connect(self.on_property_changed)
        self.right_dock.setLayout(layout)
        layout.addWidget(self.comp_prop_panel)
        layout.addWidget(self.remove_item_btn)
        layout.addWidget(self.property_panel)

    def setup_layers_panel(self):
        self.layers_list = LayersListWidget(self)
        self.layers_list.item_selected_in_list.connect(self.on_layers_list_item_clicked)
        self.layers_list.item_z_changed_requested.connect(self.reorder_item_z_from_list_event)
        self.layers_list.itemClicked.connect(self.on_layers_list_item_clicked)

    def create_left_dock(self):
        self.left_dock = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.palette)
        layout.addWidget(self.layers_list)
        self.left_dock.setLayout(layout)      

    def create_toolbar(self):
        self.toolbar = QToolBar()
        self.measure_bar = QWidget()
        self.measure_bar.setObjectName("MeasurementToolbar")
        measure_layout = QHBoxLayout()

        # Unit Selector
        self.unit_label = QLabel("Unit:")
        self.unit_selector = QComboBox()
        self.unit_selector.addItems(["in", "cm", "mm", "pt", "px"])
        self.unit_selector.setCurrentText(self.settings.display_unit)
        self.unit_selector.currentTextChanged.connect(self.on_unit_change)

        # Snap to Grid
        self.snap_checkbox = QCheckBox("Snap to Grid")
        self.snap_checkbox.setChecked(True)
        self.snap_checkbox.stateChanged.connect(self.toggle_snap)

        # Show Grid
        self.grid_checkbox = QCheckBox("Show Grid")
        self.grid_checkbox.setChecked(True)
        self.grid_checkbox.stateChanged.connect(self.toggle_grid)
 
        self.bleed_label = QLabel("Bleed")
        self.bleed_checkbox = QCheckBox("Add Bleed")
        self.bleed_checkbox.setChecked(bool(getattr(self.template, "include_bleed", False)))
        self.bleed_checkbox.toggled.connect(self.toggle_bleed)
        self.bleed_field = UnitStrField(self.template, "bleed", display_unit=self.unit, dpi=self._dpi)
        self.bleed_field.valueChanged.connect(self.on_property_changed)
        self.bleed_field.setMaximumWidth(60)   
        self.bleed_field.setEnabled(self.bleed_checkbox.isChecked())


        for widget in [
            self.unit_label,
            self.unit_selector,
            vsep(),
            self.snap_checkbox, 
            self.grid_checkbox,
            vsep(),
            self.bleed_label,
            self.bleed_checkbox,
            self.bleed_field,
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
        return self._dpi

    @dpi.setter
    def dpi(self, value):
        self._dpi = value

    @property
    def unit(self):
        return self._unit
    
    @property
    def template(self):
        return self._template

    @Slot(str)
    def on_unit_change(self, unit: str):
        self.settings.display_unit = unit
        # self.template_dims_field.on_unit_change(unit)
        self.measure_bar.update()
        # self.corners_field.on_unit_change(unit)
        self.bleed_field.on_unit_change(unit)
        self.property_panel.on_unit_change(unit)
        self.comp_prop_panel.on_unit_change(unit)

    # called from menu/toolbar checkboxes:
    def toggle_grid(self, checked: bool):
        self._show_grid = bool(checked)
        # Make sure you have access to the scene instance from the tab.
        # If the tab stores it as self.scene, do:
        self.scene.set_grid_visible(self._show_grid)

    def toggle_snap(self, checked: bool):
        self.scene.set_snap_enabled(bool(checked))

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

    def _wire_panel_live_updates(self, items: list):
        """Connect selected items' change signals to the panel for read-only refresh."""
        # Disconnect prior
        for it in getattr(self, "_panel_items", []):
            try:
                it.geometryChanged.disconnect(self._panel_on_item_geometry)
            except Exception:
                pass
            try:
                # Optional generic data change signal if your elements expose it
                it.item_changed.disconnect(self._panel_on_item_generic)
            except Exception:
                pass

        self._panel_items = list(items or [])

        # Connect new
        for it in self._panel_items:
            # Live geometry refresh
            it.geometryChanged.connect(self._panel_on_item_geometry)
            # If elements have an item_changed signal for non-geometry props, wire it too
            if hasattr(it, "item_changed"):
                it.item_changed.connect(self._panel_on_item_generic)

    @Slot(object)
    def _panel_on_item_geometry(self, new_geom):
        """Selected item geometry changed; ask panel to refresh without emitting changes."""
        it = self.sender()
        # Call a 'read-only' update on the panel (no undo, no property_changed emit)
        if hasattr(self.property_panel, "on_external_property_changed"):
            self.property_panel.on_external_property_changed(it, "geometry", new_geom)
        else:
            # Fallback: refresh entire panel targets if you don't have a targeted updater
            self.property_panel.refresh()

    @Slot()
    def _panel_on_item_generic(self):
        """Selected item changed some other property; do a light refresh."""
        if hasattr(self.property_panel, "refresh_selected"):
            self.property_panel.refresh_selected()
        else:
            self.property_panel.refresh()

    @Slot(object, str, object, object)
    def on_property_changed(self, target, prop, new, old):
        command = ChangePropertyCommand(target, prop, new, old)
        self.undo_stack.push(command)

    @Slot(list, str, object, list)
    def on_batch_property_changed(self, items, prop, new_value, old_values):
        # push a single undoable command that applies to all items
        # (or loop and push a macro-command with child commands)
        for it, old in zip(items, old_values):
            setattr(it, prop, new_value)
            if hasattr(it, "element_changed"):
                it.element_changed.emit()

    # Assumes: elem_types (tuple/type set for your element classes)
    # and pc.isproto(item, elem_types) filters only your real elements.

    def get_primary_selected_item(self):
        items = self.get_selected_items()
        return items[0] if items else None

    def get_selected_items(self) -> list:
        """Return currently selected ComponentElements in the scene."""
        return [it for it in self.scene.selectedItems() if pc.isproto(it, elem_types)]

    @Slot()
    def on_selection_changed(self):
        """Connected to QGraphicsScene.selectionChanged."""
        print(f"Selected items are: {self.scene.selectedItems()}")
        self._handle_new_selection(self.scene.selectedItems(), source="scene")

    def _handle_new_selection(self, items, *, source: str = "scene"):
        """
        Centralized selection handler.
        - Filters to ComponentElements
        - Updates property panel
        - Mirrors to layers
        - Applies handle policy
        """
        # 0) Normalize to just our elements
        sel = [it for it in items if pc.isproto(it, elem_types)]

        # 1) Idempotence guard: same structural selection?
        current_ids = tuple(sorted(map(id, sel)))
        if getattr(self, "_last_selection_ids", None) == current_ids:
            if sel:
                self.property_panel.refresh()
            else:
                self.property_panel.clear_target()
            self._apply_handle_policy(sel)
            return
        self._last_selection_ids = current_ids

        # 2) Property panel (multi-target)
        if sel:
            self.property_panel.set_targets(sel)
            self.property_panel.set_panel_enabled(True)
            self.remove_item_btn.setEnabled(True)
        else:
            self.property_panel.clear_target()
            self.property_panel.set_panel_enabled(False)
            self.remove_item_btn.setEnabled(False)

        # Wire live updates for current targets (noop if you don’t need it)
        if hasattr(self, "_wire_panel_live_updates"):
            self._wire_panel_live_updates(sel)

        # 3) Mirror into Layers (without loops)
        if hasattr(self, "layers_list"):
            try:
                self.layers_list.blockSignals(True)
                self._update_layers_selection(sel)
            finally:
                self.layers_list.blockSignals(False)

        # 4) Optional status line
        if hasattr(self, "show_status_message"):
            if not sel:
                self.show_status_message("No selection.", "info")
            elif len(sel) == 1:
                name = getattr(sel[0], "name", "Item")
                self.show_status_message(f"Selected: {name}", "info")
            else:
                self.show_status_message(f"{len(sel)} items selected.", "info")

        # 5) Handle visibility policy
        self._apply_handle_policy(sel)

    def _apply_handle_policy(self, selected_items: list):
        """
        - none selected: none show handles
        - exactly one: that one shows handles
        - multiple: all selected show handles
        """
        sel_set = set(selected_items or [])
        for it in self.scene.items():
            if pc.isproto(it, elem_types):
                it.outline.show_handles(it in sel_set)

    def set_selection(self, items):
        """
        Programmatic selection setter.
          - None or []: no selection
          - single item or iterable
        """
        # Normalize
        if items is None:
            items = []
        elif not isinstance(items, (list, tuple, set)):
            items = [items]

        sel = [it for it in items if pc.isproto(it, elem_types)]

        # Mutate scene selection atomically
        self.scene.blockSignals(True)
        try:
            self.scene.clearSelection()
            for it in sel:
                it.setSelected(True)
        finally:
            self.scene.blockSignals(False)

        # Drive the same pipeline as user interaction
        self._handle_new_selection(sel, source="programmatic")

    @Slot(QListWidgetItem)
    def on_layers_list_item_clicked(self, list_item):
        """Single-click selects exactly one item."""
        elem = list_item.data(Qt.UserRole)
        if elem:
            self.set_selection(elem)

    @Slot(list)
    def on_layers_list_selection_changed(self, elements):
        """Mirror layers panel multi-selection into the scene."""
        self.set_selection(elements)

    def _update_layers_selection(self, selected_elements: list):
        """Sync layers list selection with a list of selected scene items."""
        sel_set = set(selected_elements or [])
        self.layers_list.blockSignals(True)
        try:
            self.layers_list.clearSelection()
            first = None
            for i in range(self.layers_list.count()):
                row = self.layers_list.item(i)
                elem = row.data(Qt.UserRole)
                is_sel = elem in sel_set
                row.setSelected(is_sel)
                if is_sel and first is None:
                    first = row
            if first is not None:
                self.layers_list.scrollToItem(first)
        finally:
            self.layers_list.blockSignals(False)

    def _clear_layers_selection(self):
        self.layers_list.blockSignals(True)
        try:
            self.layers_list.clearSelection()
        finally:
            self.layers_list.blockSignals(False)



    # --- Z-order helpers and actions (multi-select aware) ---

    def _adjust_z_value(self, item, new_z):
        """Helper for z-order operations"""
        item.setZValue(new_z)
        # Keep internal list sorted (lowest->highest or however you rely on it)
        self.template.items.sort(key=lambda e: e.zValue())
        self.template.item_z_order_changed.emit()

    @Slot(int)
    def adjust_z_order_of_selected(self, direction: int):
        """
        Move selection up/down one step as a *block*, preserving relative order.
        direction > 0 => up (toward front), direction < 0 => down (toward back)
        """
        sel = self.get_selected_items()
        if not sel:
            return

        items = list(self.template.items)
        # Sort by current Z ascending so index order matches paint order (back->front)
        items.sort(key=lambda e: e.zValue())
        idx_map = {e: i for i, e in enumerate(items)}

        selected_flags = [it in sel for it in items]  # parallel to items

        if direction > 0:  # move up: scan from top toward back so we swap safely
            for i in range(len(items) - 2, -1, -1):  # second-to-last down to 0
                if selected_flags[i] and not selected_flags[i + 1]:
                    # swap i and i+1
                    items[i], items[i + 1] = items[i + 1], items[i]
                    selected_flags[i], selected_flags[i + 1] = selected_flags[i + 1], selected_flags[i]
        elif direction < 0:  # move down: scan from back toward top
            for i in range(1, len(items)):
                if selected_flags[i] and not selected_flags[i - 1]:
                    # swap i and i-1
                    items[i], items[i - 1] = items[i - 1], items[i]
                    selected_flags[i], selected_flags[i - 1] = selected_flags[i - 1], selected_flags[i]

        # Reassign Zs with spacing so we keep clean ordering
        step = 100.0
        base = 0.0
        for i, e in enumerate(items):
            new_z = base + step * (i + 1)
            if e.zValue() != new_z:
                e.setZValue(new_z)

        self.template.items = items
        self.template.item_z_order_changed.emit()
        self.update_layers_panel()

    @Slot()
    def update_layers_panel(self):
        self.layers_list.update_list(self.template.items)

    @Slot()
    def bring_selected_to_front(self):
        sel = self.get_primary_selected_item()
        if not sel:
            return

        # Maintain relative order among the selected when bringing forward
        non_sel = [e for e in self.template.items if e not in sel]
        step = 100.0
        base = 0.0
        # new order: non-selected (back) + selected (front)
        new_order = non_sel + sel
        for i, e in enumerate(sorted(new_order, key=lambda e: (e in sel, e.zValue()))):
            # The sort above ensures stable ordering; we’ll assign final Zs below anyway.
            pass

        # Assign Z strictly by this order (back->front)
        for i, e in enumerate(new_order):
            e.setZValue(base + step * (i + 1))

        self.template.items = new_order
        # self.template.item_z_order_changed.emit()
        self.update_layers_panel()

    @Slot()
    def send_selected_to_back(self):
        sel = self.get_selected_items()
        if not sel:
            return

        non_sel = [e for e in self.template.items if e not in sel]
        step = 100.0
        base = 0.0
        # new order: selected (back) + non-selected (front)
        new_order = sel + non_sel

        for i, e in enumerate(new_order):
            e.setZValue(base + step * (i + 1))

        self.template.items = new_order
        # self.template.item_z_order_changed.emit()
        self.update_layers_panel()

    @Slot(object, int)
    def reorder_item_z_from_list_event(self, item: object, direction: int):
        """
        Layers panel notified us a manual reorder occurred.
        You can either rebuild Zs from layers order or reuse the move-by-one API.
        Here we just refresh layers and scene; Zs are already set by the panel handler.
        """
        self.update_layers_panel()

    @Slot()
    def on_item_data_changed(self):
        self.selected_item.update()
        pass

    @Slot()
    def clear_scene_selection(self):
        if self.scene.selectedItems():
            self.scene.clearSelection()

    @Slot(ProtoClass, object)
    def add_item_with_dims(self, proto: ProtoClass, geom):
        """
        Scene finished a click-drag create. Make it undoable via AddElementCommand.
        Select the created item and wire the resize_finished signal.
        """
        command = AddElementCommand(proto, self, geom)
        self.undo_stack.push(command)
        item = self.registry.get_last()
        # Select last-created element
        item.setSelected(True)
        self.property_panel.set_targets([item])
        self._connect_item_signals(item)

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
        item = self.registry.get_last()
        item.setSelected(True)
        self.property_panel.set_targets([item])
        self._connect_item_signals(item)

    @Slot(object, object)
    def clone_item(self, original, new_geometry):
        """Clone via the registry and immediately begin dragging."""
        # 1) Do the registry‐based clone
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
        self._connect_item_signals(new)
        self.update_layers_panel()

        # drag_offset = press_scene_pos - new.pos()
        # self.scene._dragging_item = new
        # self.scene._drag_offset   = drag_offset

    def set_item_controls_enabled(self, enabled: bool):
        # Do NOT disable the PropertyPanel widget itself.
        # Let the panel control its inner form state.
        self.property_panel._set_panel_enabled(enabled)
        self.remove_item_btn.setEnabled(enabled)

    def _apply_handle_policy(self, selected_items: list):
        """Show handles according to selection policy:
           - exactly one selected: only that one shows handles
           - multiple selected: all selected show handles
           - none selected: none show handles
        """
        selected_set = set(selected_items or [])

        for it in self.scene.items():
            if pc.isproto(it, elem_types):
                if not selected_set:  # none selected
                    handle_state = False
                elif len(selected_set) == 1:
                    handle_state = it in selected_set
                else:  # multiple selected
                    handle_state = it in selected_set

                it.outline.show_handles(handle_state)

    @Slot()
    def remove_selected_item(self):
        item = self.get_selected_item()
        if not item:
            self.show_status_message("No item selected to remove.", "warning")
            return
        
        reply = QMessageBox.question(
            self, "Remove Element",
            f"Are you sure you want to remove '{item.name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No:
            self.show_status_message("Element removal cancelled.", "info")
            return
        
        # 1) Unbind the panel first so no child editors hold the item

        # 2) Clear selection in the scene (prevents selection-changed churn)
        sel_items = list(self.scene.selectedItems())
        for it in sel_items:
            self._disconnect_item_signals(item)
            it.setSelected(False)
        self.property_panel.clear_target()
        # 3) Delete via undo command
        command = RemoveElementCommand(item, self)
        self.undo_stack.push(command)
        
        # 4) Panel stays empty until the user selects something else
        self.on_selection_changed()
        print(f"Confirming the removal method is being called")
        self.show_status_message(f"Element '{item.name}' removed.", "info")

    @Slot(QObject)
    def _on_selected_item_destroyed(self, _=None):
        """
        If the selected item gets destroyed (removed via undo/redo or elsewhere),
        clear the selection / property panel.
        """
        # Only clear if we were actually pointing to the sender
        self._handle_new_selection(None)

    def _connect_item_signals(self, item: QGraphicsObject):
        if not item:
            print(f"Warning {item} is not a valid item type.")
            return
        try:
            item.geometryAboutToChange.connect(self._on_geom_about_to_change)
            item.geometryChanged.connect(self._on_geom_changed)
            item.moveCommitted.connect(self._on_items_moved_commit)
        except (RuntimeError, TypeError):
            pass

    def _disconnect_item_signals(self, item):
        """Safely disconnect per-item signals."""
        if not item:
            print(f"Warning {item} is not a valid item type.")
            return
        try:
            item.item_changed.disconnect(self.on_item_data_changed)
            item.moveCommitted.disconnect(self._on_items_moved_commit)
            item.geometryChanged.disconnect(self._on_geom_changed)
            item.geometryAboutToChange.disconnect(self._on_geom_about_to_change)
        except (RuntimeError, TypeError):
            pass

    def eventFilter(self, obj, ev):
        et = ev.type()
        if et == QEvent.GraphicsSceneMousePress:
            self._begin_gesture()
        elif et in (QEvent.GraphicsSceneMouseRelease, QEvent.GraphicsSceneMouseDoubleClick):
            self._end_gesture()
        return False

    def _begin_gesture(self):
        self._gesture_active = True
        self._old_by_item.clear()
        self._new_by_item.clear()

    def _on_geom_about_to_change(self, old_geom):
        if not self._gesture_active:
            return
        it = self.sender()
        # Snapshot the very first old geometry we see for this item in this gesture
        self._old_by_item.setdefault(it, old_geom)

    def _on_geom_changed(self, new_geom):
        if not self._gesture_active:
            return
        it = self.sender()
        self._new_by_item[it] = new_geom
        self._panel_on_item_geometry(new_geom)

    def _end_gesture(self):
        if not self._gesture_active:
            return
        self._gesture_active = False

        # Filter to items that genuinely changed
        changed_items = []
        for it, new_geom in self._new_by_item.items():
            old_geom = self._old_by_item.get(it)
            if old_geom is None:
                continue
            if new_geom.to("px", dpi=it.dpi).rect != old_geom.to("px", dpi=it.dpi).rect or \
               new_geom.to("px", dpi=it.dpi).pos  != old_geom.to("px", dpi=it.dpi).pos:
                changed_items.append(it)

        if not changed_items:
            self._old_by_item.clear(); self._new_by_item.clear()
            return

        # One undo step, many items: reuse your existing on_property_changed calls
        self.undo_stack.beginMacro("Change geometry")
        try:
            for it in changed_items:
                old_g = self._old_by_item[it]
                new_g = self._new_by_item[it]
                # Route through your pipeline:
                self.on_property_changed(it, "geometry", new_g, old_g)
        finally:
            self.undo_stack.endMacro()

        self._old_by_item.clear()
        self._new_by_item.clear()

    def _on_items_moved_commit(self, items, starts, ends):
        cmd = MoveSelectionCommand(items, starts, ends)
        self.undo_stack.push(cmd)
