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

    def __init__(self, parent, main_window, template, registry):
        super().__init__(parent)
        self.main_window = main_window
        presets = self.main_window.settings
        self.settings = presets
        self.registry = registry
        self._template = template
        self.file_path = None
        self.undo_stack = QUndoStack()
        # self.page_manager = PageManager(template, registry, merge_mgr)
        
        self._show_grid   = True
        self._snap_grid   = True
        self._selected_item_pid: Optional[str] = None

        # --- 2. Setup the central widget for the tab's main area ---
        self.inc_grid = IncrementalGrid(self.settings, snap_enabled=self._snap_grid, parent=template)
        self.scene = LayoutScene(self.settings, template=template, grid=self.inc_grid)
        self.scene.addItem(self._template)
        self.view = LayoutView(self.scene)
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
        self.update_grid(self.template.rows, self.template.columns)

        # initialise from current flags
        self.inc_grid.setVisible(self._show_grid)

        self._template.setGrid(self.registry, rows=template.rows, columns=template.columns)
   
        self._create_layout_toolbar()
        self._create_layout_palette()
        self._create_property_panel()
        self.remove_item_btn = QPushButton("Remove Assignment")

        # Connect signals to handler methods
        self.scene.component_dropped.connect(self.on_component_dropped)
        self.layout_toolbar.display_flag_changed.connect(self.on_display_flag_changed)
        self.layout_toolbar.number_of_copies.connect(self.on_layout_copy_count_changed)
        # self.layout_palette.palette_selection_changed.connect(self.on_palette_selection_change)
        self.layout_palette.select_template.connect(self.on_confirm_template)
        self.layout_palette.remove_template.connect(self.on_remove_template)
        # --- 3. Set the simple, single layout for the tab itself ---
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.view)

    # --- UI creation stubs --- #

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
        self.layout_toolbar.pagination_policy_changed.connect(self.pagination_policy_changed)

        self.layout_toolbar.apply_template(self.template)

        return self.layout_toolbar

    def _create_layout_palette(self) -> QWidget:
        self.layout_palette = LayoutPalette(self.main_window.registry, parent=self)
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
        self.main_window = main_window
        if hasattr(main_window, "undo_group"):
            main_window.undo_group.setActiveStack(self.undo_stack)

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
    def dpi(self): return self._dpi

    @property
    def unit(self):
        return self._unit
    
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
    def pagination_policy_changed(self, new):
        template = self.template
        old = self.template.pagination_policy
        self.on_property_changed(template, "pagination_policy", new, old)
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
    def on_display_flag_changed(self, qflag):
        self.template.display_flag = qflag
        for row in self.template.items:
            for column in row:
                for item in column:
                    flag = self.template.display_flag
                    item.display_flag = flag

    @Slot(int)
    def on_layout_copy_count_changed(self, value: int):
        self.scene.populate_with_clones(value, self.template, self.registry)
        # self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    @Slot(object, str, list, list)
    def on_whitespace_changed(self, target, prop, new, old):
        command = ChangePropertyCommand(target, prop, new, old)
        self.undo_stack.push(command)
        self.template.updateGrid()

    def _on_policy_change(self, policy_name: str):
        # 1. Store on template (persists to JSON)
        old = self.template.pagination_policy
        new = policy_name
        prop = "pagination_policy"
        self.on_property_changed(self.template, prop, new, old)
        # 2. Invalidate existing PageManager & preview
        self.page_manager = None          # force rebuild next refresh
        self._refresh_scene_preview()

    # --- Selection and Placement Logic ---
    @Slot()
    def on_scene_selection_changed(self):
        selected_items = self.scene.selectedItems()
        if selected_items:
            item = selected_items[0]
            self.property_panel.display_item(item)
        else:
            self.property_panel.clear_values()

    def select_item(self, row: int, col: int):
        item = self.template.items[row][col]
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
