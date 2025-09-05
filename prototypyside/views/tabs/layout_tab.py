# layout_tab.py
from functools import partial
from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSplitter, QLabel, QGridLayout,
    QGraphicsView, QGraphicsScene)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, Slot, QTimer
from PySide6.QtGui import (QKeySequence, QShortcut, QUndoStack, 
    QUndoGroup, QUndoCommand, QPainter, QPageSize, QPixmap, QImage, QPainter)

from prototypyside.views.overlays.incremental_grid import IncrementalGrid
from prototypyside.models.layout_template import LayoutTemplate
from prototypyside.models.layout_slot import LayoutSlot
from prototypyside.services.app_settings import AppSettings
from prototypyside.views.panels.layout_property_panel import LayoutPropertyPanel
from prototypyside.views.toolbars.layout_toolbar import LayoutToolbar
from prototypyside.views.palettes.layout_palette import LayoutPalette
from prototypyside.widgets.unit_str_field import UnitStrField
from prototypyside.widgets.unit_strings_field import UnitStringsField
from prototypyside.views.layout_scene import LayoutScene
from prototypyside.views.layout_view import LayoutView
from prototypyside.utils.unit_converter import to_px
from prototypyside.config import PAGE_SIZES
from prototypyside.services.proto_registry import ProtoRegistry
from prototypyside.services.undo_commands import (ChangePropertyCommand, 
        CloneComponentTemplateToSlotCommand, CloneComponentToEmptySlotsCommand)
# # from prototypyside.services.pagination.page_manager import PageManager


class LayoutTab(QWidget):
    """Tab for editing a LayoutTemplate via grid/item assignment."""
    new_tab = Signal()
    layout_changed = Signal()
    item_selected = Signal(str)  # item_pid
    template_selected = Signal(str)  # tpid
    status_message_signal = Signal(str, str, int) # message, type, timeout_ms
    tab_title_changed = Signal(str) # For updating the tab title if needed
    grid_visibility_changed = Signal(bool)
    grid_snap_changed = Signal(bool)

    def __init__(self, main_window, template, registry, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        presets = self.main_window.settings
        self.settings = presets
        self.registry = registry
        self._template = template
        self.file_path = None
        self.undo_stack = QUndoStack()
        self._page_root = None
        self._page_index = 0
        # self._page_manager = PageManager(self.registry, self.settings)

        
        self._show_grid   = True
        self._snap_grid   = True
        self._selected_item_pid: Optional[str] = None

        # --- 2. Setup the central widget for the tab's main area ---
        self.inc_grid = IncrementalGrid(self.settings, snap_enabled=self._snap_grid, parent=template)
        self.scene = LayoutScene(self.settings, template=template, grid=self.inc_grid)
        self.scene.selectionChanged.connect(self.on_scene_selection_changed)
        self.view = LayoutView(self.scene)
        self.view.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.view.setOptimizationFlag(QGraphicsView.DontSavePainterState)
        self.view.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing)
        self.view.setScene(self.scene)

        # First template mount will set the scene rect; then fit:
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
        self.view.show()
        # connect visibility / snapping controls
        self.grid_visibility_changed.connect(self.inc_grid.setVisible)
        self.grid_snap_changed.connect(self.inc_grid.setSnapEnabled)

        # initialise from current flags
        self.inc_grid.setVisible(self._show_grid)
   
        self._create_layout_toolbar()
        self._create_layout_palette()
        self._create_property_panel()
        self.remove_item_btn = QPushButton("Remove Assignment")

        # Connect signals to handler methods
        self.scene.component_dropped.connect(self.on_component_dropped)
        self.layout_toolbar.display_mode_changed.connect(self.on_display_mode_changed)
        #self.layout_toolbar.number_of_copies.connect(self.on_layout_copy_count_changed)
        # self.layout_palette.palette_selection_changed.connect(self.on_palette_selection_change)
        self.layout_palette.select_template.connect(self.on_confirm_template)
        self.layout_palette.remove_template.connect(self.on_remove_template)
        # --- 3. Set the simple, single layout for the tab itself ---
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.view)

    # --- UI creation stubs --- #

    # def set_template(self, tmpl: LayoutTemplate):
    #     # disconnect old
    #     # if self.template:
    #     #     try:
    #     #         self.template.policyChanged.disconnect(self._on_template_policy_changed)
    #     #         self.template.slotsChanged.disconnect(self._on_template_slots_changed)
    #     #     except TypeError:
    #     #         pass

    #     self.template = tmpl

    #     # connect new
    #     tmpl.policyChanged.connect(self._on_template_policy_changed)
    #     tmpl.slotsChanged.connect(self._on_template_slots_changed)

    #     # first show
    #     self._refresh_scene_rect()
    #     self._remount_page()

    # def _prime_grid(self, t):
    #     # Ensure rows/cols/geometry are set from current policy first.
    #     # (If you already apply a default policy elsewhere, this is a no-op.)
    #     # if hasattr(self.layout_toolbar, "current_policy") and self.layout_toolbar.current_policy:
    #     #     # whatever you do today to apply policy to the template:
    #     #     self.apply_policy_to_template(self.layout_toolbar.current_policy, t)

    #     # Ensure the grid actually exists before updateGrid/math
    #     if not t.items or len(t.items) != (t.rows * t.columns):
    #         t.setGrid(t.rows, t.columns)

    #     # It’s now safe to size/position slots
    #     t.updateGrid()

    def _create_property_panel(self) -> QWidget:
        """Create panel with margin and spacing controls"""
        unit = self.settings.unit
        dpi = self.settings.dpi

        self.property_panel = QWidget()
        layout = QVBoxLayout(self.property_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Add section headers
        layout.addWidget(QLabel("Margins and Spacing"))

        
        self.ws_fields = UnitStringsField(
            target_item=self.template,
            property_name="whitespace",
            labels=["Top Margin", "Bottom Margin", "Left Margin", 
                        "Right Margin", "Horizontal Spacing", "Veritical Spacing"],
            display_unit=self.settings.display_unit,
            decimal_places=4)

        self.ws_fields.valueChanged.connect(self.on_property_changed)
        layout.addWidget(self.ws_fields)
        return self.property_panel

    def _create_layout_toolbar(self) -> QWidget:
        self.layout_toolbar = LayoutToolbar(self.settings, parent=self)

        # Connect signals
        self.layout_toolbar.page_size_changed.connect(self.on_page_size_changed)
        self.layout_toolbar.orientation_property_change.connect(self.on_orientation_changed)
        self.layout_toolbar.grid_size_changed.connect(self.on_grid_size_changed)
        self.layout_toolbar.autofill_changed.connect(self.on_auto_fill_changed)
        self.layout_toolbar.pagination_policy_changed.connect(self.on_policy_changed)

        self.layout_toolbar.apply_template(self.template)

        return self.layout_toolbar

    def _create_layout_palette(self) -> QWidget:
        self.layout_palette = LayoutPalette(
            root_registry=self.main_window.registry, 
            layout=self.template, 
            parent=self)
        # print("LayoutPalette sizeHint:", self.layout_palette.sizeHint())
        # Return a widget listing all open component templates
        pass

    # called from menu/toolbar checkboxes:
    def toggle_grid(self, checked: bool):
        self._show_grid = checked
        self.grid_visibility_changed.emit(checked)

    def toggle_snap(self, checked: bool):
        self._snap_grid = checked
        self.grid_snap_changed.emit(checked)


    def focusInEvent(self, event):
        super().focusInEvent(event)
        # Assuming you have a way to get the main window, e.g., self.window()
        # Prefer the injected main_window; fallback to window()
        if not hasattr(self, "main_window") or self.main_window is None:
            self.main_window = self.window()
        if hasattr(self.main_window, "undo_group"):
            self.main_window.undo_group.setActiveStack(self.undo_stack)

    def show_status_message(self, message: str, message_type: str = "info", timeout_ms: int = 5000):
        self.status_message_signal.emit(message, message_type, timeout_ms)

    @Slot()
    def on_template_name_changed(self):
        new_name = self.template_name_field.text().strip()
        if new_name:
            self.tab_title_changed.emit(new_name)

    # --- Properties ---
    @property
    def current_selected_item(self) -> Optional[LayoutSlot]:
        if self._selected_item_pid:
            return self.registry.get(self._selected_item_pid)
        return None

    @property
    def dpi(self):
        return self.settings.dpi

    @dpi.setter
    def dpi(self, value):
        self.settings.dpi = value

    @property
    def unit(self):
        return self.settings.unit

    @unit.setter
    def unit(self, value):
        for each in unit_str_like_fields():
            each.setUnit(value)
    
    @property
    def template(self):
        return self._template

    @template.setter
    def template(self, new):
        if new != self.template and isinstance(new, LayoutTemplate):
            self._template = new

    # --- Grid/Scene Logic ---
    @Slot()
    def on_property_changed(self, target, prop, new, old):
        command = ChangePropertyCommand(target, prop, new, old)
        self.undo_stack.push(command)
        print(f"[LAYOUTTAB] Target={target}, prop={prop}, old={old}, new={new}")
        print(f"[UNDO STACK] Pushed: {command}")
        
    @Slot(str)
    def on_unit_change(self, unit: str):
        self.settings.unit = unit
        self.template_width_field.on_unit_change(unit)
        self.template_height_field.on_unit_change(unit)
        self.layout_toolbar.update()
        self.property_panel.on_unit_change(unit)

    def update_grid(self, rows=None, columns=None):
        """Refresh the scene grid based on template settings."""
        if rows and columns:
            self.template.setGrid(self.registry, rows=rows, columns=columns)
        self.template.updateGrid()
        pass

    @Slot(str)
    def on_page_size_changed(self, key):
        t = self.template
        o = self.template.page_size
        n = key
        p = "page_size"
        command = ChangePropertyCommand(t, p, n, o)
        self.undo_stack.push(command)
        self.scene.setSceneRect(self.template.boundingRect())
        # self._refreshGrid()

    @Slot(str, bool, bool)
    def on_orientation_changed(self, prop, new, old):
        t = self.template
        print(f"BoundingRect before change: {t.boundingRect()}")
        self.on_property_changed(t, prop, new, old)
        print(f"BoundingRect after change: {t.boundingRect()}")
        self.scene.setSceneRect(t.boundingRect())

        t.updateGrid()
        self.scene.sync_scene_rect()

    def cleanup(self):
        self.scene.clear()  # Clears all graphics items
        self.template = None  # Drop reference to ComponentTemplate
        
    @Slot(str)
    def on_confirm_template(self, pid):
        comp = self.registry.global_get(pid)
        command = CloneComponentToEmptySlotsCommand(self.registry, self.template, comp)
        self.undo_stack.push(command)

    @Slot(str)
    def on_remove_template(self, pid):
        print(f"[LAYOUT_TAB] on_remove_template: Received remove request...")
        flat_slots = [c for r in self.template.items for c in r]
        for slot in flat_slots:
            slot.content = None
            slot.update()
        print(f"All slot content has been set to None")
        # command = CloneComponentToSlotsCommand(self.registry, self.template, None)
        # self.undo_stack.push(command)

    @Slot(str)
    def on_policy_changed(self, new):
        template = self.template
        old = self.template.polkey
        self.on_property_changed(template, "polkey", new, old)
        self.template.update()

    @Slot(int, int)
    def on_grid_size_changed(self, rows: int, cols: int):
        template = self.template
        old_grid = template.grid
        print(f"rows and cols received from toolbar are {rows}, {cols}")
        command = ChangePropertyCommand(self.template, "grid", (rows, cols), old_grid)
        self.undo_stack.push(command)
        self.template.setGrid(self.registry, rows=rows, columns=cols)
        print(f"[LAYOUT_TAB] From on_grid_size_changed: Template rows and columns after change are are now {template.rows}, {template.columns}")
        
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    @Slot(bool)
    def on_auto_fill_changed(self, autofill: bool):
        self.template.auto_fill = autofill
        self.template = self.registry.root.get_last()

    @Slot(object)
    def on_display_mode_changed(self, qflag):
        self.template.display_mode = qflag
        for row in self.template.items:
            for column in row:
                for item in column:
                    flag = self.template.display_mode
                    item.display_mode = flag

    # @Slot(int)
    # def on_layout_copy_count_changed(self, value: int):
    #     self.scene.populate_with_clones(value, self.template, self.registry)
    #     # self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    @Slot(object, str, list, list)
    def on_whitespace_changed(self, target, prop, new, old):
        command = ChangePropertyCommand(target, prop, new, old)
        self.undo_stack.push(command)
        self.template.updateGrid()

    @Slot(str)
    def _on_policy_change(self, policy_name: str):
        old = self.template.polkey
        if policy_name == old:
            return
        # push undoable change (must call the template's setter so it emits!)
        self.on_property_changed(self.template, "polkey", policy_name, old)
        # If polkey can change page size, update scene rect now
        self._refresh_scene_rect()

    # --- Selection and Placement Logic ---
    @Slot()
    def on_scene_selection_changed(self):
        # Only care about LayoutSlot selections
        selected_slots = [it for it in self.scene.selectedItems() if isinstance(it, LayoutSlot)]
        if selected_slots:
            slot = selected_slots[-1]  # prefer the last selected if multiple
            self._selected_item_pid = getattr(slot, "pid", None)
            self.property_panel.display_item(slot)
        else:
            self._selected_item_pid = None
            self.property_panel.clear_values()


    def select_item(self, row: int, col: int):
        item = self.template.slots[row][col]
        self._selected_item = item
        self._selected_item.hoverEventEffect()
        self.refresh_panels()

    def deselect_item(self):
        self._selected_item_pid = None
        self._selected_item.hoverLeaveEffect()
        self.refresh_panels()

    def on_item_selected(self, item_pid: str):
        if prefix(item_pid) == "ct":
            self.property_panel.template_
        self._selected_item_pid = item_pid
        self.refresh_panels()

    @Slot(str, QPointF)
    def on_component_dropped(self, tpid: str, scene_pos: QPointF):
        component = self.registry.global_get(tpid)
        
        command = CloneComponentToEmptySlotsCommand(self.registry, self.template, component)

        self.undo_stack.push(command)

    # --- Page Management ---
    # scene rect stays based on the unrotated template geometry
    def _refresh_scene_rect(self):
        rect_px = self.template.geometry.to("px", dpi=self.settings.dpi).rect
        self.scene.setSceneRect(rect_px)

    # def _remount_page(self):
    #     if self._page_root:
    #         self._page_manager.unmount(self.scene, self._page_root)
    #         self._page_root = None
    #     page, root = self._page_manager.mount(self.template, self.scene, self._page_index)
    #     self._page_root = root
        # nothing else needed — your live slots are now children of root

    # Hooks for updates
    def _on_template_policy_changed(self):
        # landscape / duplex / item_rotation toggles
        self._remount_page()

    def _on_template_slots_changed(self):
        # when autofill rebuilds or you add/remove slots
        self._remount_page()

    # def show_page(self, page_index: int = 0):
    #     if self._page_root:
    #         self._page_manager.unmount(self.scene, self._page_root)
    #         self._page_root = None
    #     page, root = self._page_manager.mount(self.template, self.scene, page_index)
    #     self._page_root = root
        # Store page if you need status display, etc.

    # def on_policy_changed(self):
    #     # Called when user toggles landscape / duplex / item_rotation edits, etc.
    #     old = self.template.polkey
    #     new = policy_name
    #     prop = "polkey"
    #     self.on_property_changed(self.template, prop, new, old)
    #     self.show_page(page_index=0)  # or keep same index

    # --- Undo/Redo Integration ---
    def push_undo_command(self, command):
        self.undo_stack.push(command)

    def undo(self):
        self.undo_stack.undo()

    def redo(self):
        self.undo_stack.redo()

    # --- Misc/Utility ---
    def save_state(self):
        # For persistence (e.g., JSON serialization)
        pass

    def load_state(self, data: dict):
        # Restore from saved state
        pass

    def refresh_panels(self):
        # Refresh property panel, palette, import panel, etc.
        pass

    # --- Keyboard shortcut handling for delete ---
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete and self._selected_item_pid:
            self._on_remove_item()
            event.accept()
        else:
            super().keyPressEvent(event)
