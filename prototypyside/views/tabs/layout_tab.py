# layout_tab.py

from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSplitter, QLabel, QGridLayout,
    QGraphicsView, QGraphicsScene)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, Slot, QTimer
from PySide6.QtGui import (QKeySequence, QShortcut, QUndoStack, 
    QUndoGroup, QUndoCommand, QPainter, QPageSize, QPixmap, QImage, QPainter)

from prototypyside.models.layout_template import LayoutTemplate, LayoutSlot
from prototypyside.services.app_settings import AppSettings
from prototypyside.views.panels.layout_property_panel import LayoutPropertyPanel, scene_to_pixmap
from prototypyside.views.toolbars.layout_toolbar import LayoutToolbar
from prototypyside.views.palettes.layout_palette import LayoutPalette
from prototypyside.widgets.unit_field import UnitField
from prototypyside.views.layout_scene import LayoutScene
from prototypyside.views.layout_view import LayoutView
from prototypyside.utils.unit_converter import to_px
from prototypyside.config import PAGE_SIZES
from prototypyside.services.proto_registry import ProtoRegistry
from prototypyside.services.undo_commands import ChangeItemPropertyCommand, CloneComponentTemplateToSlotCommand


class LayoutTab(QWidget):
    """Tab for editing a LayoutTemplate via grid/item assignment."""
    new_tab = Signal()
    layout_changed = Signal()
    item_selected = Signal(str)  # item_pid
    template_selected = Signal(str)  # tpid
    status_message_signal = Signal(str, str, int) # message, type, timeout_ms
    tab_title_changed = Signal(str) # For updating the tab title if needed

    def __init__(self, parent, main_window, template, registry):
        super().__init__(parent)
        self.main_window = main_window
        presets = self.main_window.settings
        self.settings = AppSettings(display_dpi=template.geometry.dpi, display_unit=presets.unit, 
                    print_unit=template.geometry.unit, print_dpi=presets.print_dpi)
        self.registry = registry
        self._template = template
        self.file_path = None
        print(self._template)
        self.undo_stack = QUndoStack()
        # self.pagination_manager = PaginationManager(template, registry, merge_mgr)
        
        self._selected_item_pid: Optional[str] = None

        # --- 2. Setup the central widget for the tab's main area ---
        self.scene = LayoutScene(scene_rect=self.template.boundingRect(), tab=self)
        self.view = LayoutView(self.scene)
        self.view.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.view.setOptimizationFlag(QGraphicsView.DontSavePainterState)
        self.view.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing)
        self.view.setScene(self.scene)
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
        self.view.show()
        self.scene.addItem(self._template)
        print(f"Scene rect is: {self.scene.sceneRect()}")
        print(f"[LAYOUT_TAB] From __init__: Template rows and columns prior to initially setting grid {template.rows}, {template.columns}")
        self._template.setGrid(self.registry, rows=template.rows, columns=template.columns)
        print(f"[LAYOUT_TAB] From __init__: Template rows and columns after initially setting grid {template.rows}, {template.columns}")
        self._create_layout_toolbar()
        self._create_layout_palette()

        self._create_property_panel()
        self.margin_spacing_panel = self._create_margin_spacing_panel()
        self.remove_item_btn = QPushButton("Remove Assignment")
        
        #self.remove_item_btn.clicked.connect(self._on_remove_item)

        # Connect signals to handler methods
        self.scene.component_dropped.connect(self.on_component_dropped)
        self.layout_toolbar.display_flag_changed.connect(self.on_display_flag_changed)
        self.layout_toolbar.number_of_copies.connect(self.on_layout_copy_count_changed)
        # self._template.marginsChanged.connect(self.on_template_margin_changed)
        # self._template.spacingChanged.connect(self.on_template_spacing_changed)
        self.layout_palette.palette_selection_changed.connect(self.on_palette_selection_change)
        # --- 3. Set the simple, single layout for the tab itself ---
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.view)
        # --- 4. Load data and connect signals ---
        #self.load_template(self.template) # Make sure this is called!
        self.update_grid() # This method currently does nothing in your provided code for LayoutTab
        self.refresh_panels()

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
            self.template.name = new_name
            self.tab_title_changed.emit(new_name)

    # --- Properties ---
    @property
    def current_selected_item(self) -> Optional[LayoutSlot]:
        if self._selected_item_pid:
            return self.registry.get(self._selected_item_pid)
        return None

    # --- UI creation stubs (fill in as needed) ---
    # layout_tab.py (new method)

    def _create_margin_spacing_panel(self) -> QWidget:
        """Create panel with margin and spacing controls"""
        unit, dpi = self.settings.unit, self.settings.dpi

        self.margin_panel = QWidget()
        layout = QVBoxLayout(self.margin_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Add section headers
        layout.addWidget(QLabel("<b>Margins</b>"))
        
        # Create grid for margin controls
        margin_grid = QGridLayout()
        margin_grid.setSpacing(5)
        top, bottom, left, right = self.template.get_margins()

        # Top margin
        self.margin_top = UnitField(self.template, "margin_top", display_unit=self.template.geometry.unit, )
        margin_grid.addWidget(QLabel("Top:"), 0, 0)
        margin_grid.addWidget(self.margin_top, 0, 1)
        
        # Bottom margin
        self.margin_bottom = UnitField(self.template, "margin_bottom", display_unit=self.template.geometry.unit, )
        margin_grid.addWidget(QLabel("Bottom:"), 1, 0)
        margin_grid.addWidget(self.margin_bottom, 1, 1)
        
        # Left margin
        self.margin_left = UnitField(self.template, "margin_left", display_unit=self.template.geometry.unit, )
        margin_grid.addWidget(QLabel("Left:"), 2, 0)
        margin_grid.addWidget(self.margin_left, 2, 1)
        
        # Right margin
        self.margin_right = UnitField(self.template, "margin_right", display_unit=self.template.geometry.unit, )
        margin_grid.addWidget(QLabel("Right:"), 3, 0)
        margin_grid.addWidget(self.margin_right, 3, 1)
        
        layout.addLayout(margin_grid)
        
        # Add spacing section
        layout.addWidget(QLabel("<b>Spacing</b>"))
        
        # Create grid for spacing controls
        spacing_grid = QGridLayout()
        spacing_grid.setSpacing(5)
        
        # Horizontal spacing
        self.spacing_x = UnitField(self.template, "spacing_x", display_unit=self.template.geometry.unit, )
        spacing_grid.addWidget(QLabel("Horizontal:"), 0, 0)
        spacing_grid.addWidget(self.spacing_x, 0, 1)
        
        # Vertical spacing
        self.spacing_y = UnitField(self.template, "spacing_y", display_unit=self.template.geometry.unit, )
        spacing_grid.addWidget(QLabel("Vertical:"), 1, 0)
        spacing_grid.addWidget(self.spacing_y, 1, 1)
        spacing_grid.sizeHint()
        layout.addLayout(spacing_grid)
        layout.addStretch(1)
        
        # Connect signals
        for name, field in [
            ("margin_top", self.margin_top),
            ("margin_bottom", self.margin_bottom),
            ("margin_left", self.margin_left),
            ("margin_right", self.margin_right),
        ]:
            field.valueChanged.connect(
                self.on_template_margin_changed)

        for name, field in [("spacing_x", self.spacing_x),
                            ("spacing_y", self.spacing_y)]:
            field.valueChanged.connect(
                self.on_template_spacing_changed)           
        # print("MarginPanel sizeHint:", self.margin_panel.sizeHint())
        return self.margin_panel

    def _create_layout_toolbar(self) -> QWidget:
        self.layout_toolbar = LayoutToolbar(self.settings, parent=self)
        # Connect signals
        self.layout_toolbar.pagination_policy_changed.connect(self._on_policy_change)
        self.layout_toolbar.page_size_changed.connect(self.on_page_size_changed)
        self.layout_toolbar.orientation_changed.connect(self.on_orientation_changed)
        self.layout_toolbar.grid_size_changed.connect(self.on_grid_size_changed)
        self.layout_toolbar.autofill_changed.connect(self.on_auto_fill_changed)
        # Set up initial toolbar state from the template
        self.layout_toolbar.apply_template(self.template)
        # print("LayoutToolbar sizeHint:", self.layout_toolbar.sizeHint())


        return self.layout_toolbar

    def _create_layout_palette(self) -> QWidget:
        self.layout_palette = LayoutPalette(self.main_window.registry, parent=self)
        # print("LayoutPalette sizeHint:", self.layout_palette.sizeHint())
        # Return a widget listing all open component templates
        pass

    def _create_property_panel(self) -> QWidget:
        # Changed to set self.property_panel instead of self.layout_property_panel
        self.property_panel = LayoutPropertyPanel(parent=self)
        # print("PropertyPanel sizeHint:", self.property_panel.sizeHint())
        # Return a property panel reflecting the selected template
        pass

    # --- Grid/Scene Logic ---

    def update_grid(self):
        """Refresh the scene grid based on template settings."""
        # Rebuild scene items for each item; gray out empty items, assign templates as needed
        pass

    @Slot(str)
    def on_page_size_changed(self, key):
        t = self.template
        o = self.template.page_size
        n = key
        p = "page_size"
        command = ChangeItemPropertyCommand(t, p, n, o)
        self.undo_stack.push(command)
        self.scene.setSceneRect(self.template.boundingRect())
        # self._refreshGrid()

    @Slot(bool)
    def on_orientation_changed(self, landscape: bool):
        t = self.template
        old = t.orientation
        new = landscape
        if old == new:
            return  # no change, no-op

        # # 🔁 Swap row/col spinbox values (but keep logical count the same)
        # r = self.layout_toolbar.rows_spin.value()
        # c = self.layout_toolbar.cols_spin.value()
        # self.layout_toolbar.rows_spin.blockSignals(True)
        # self.layout_toolbar.cols_spin.blockSignals(True)
        # self.layout_toolbar.rows_spin.setValue(c)
        # self.layout_toolbar.cols_spin.setValue(r)
        # self.layout_toolbar.rows_spin.blockSignals(False)
        # self.layout_toolbar.cols_spin.blockSignals(False)

        # 🔁 Push undo and orientation change
        command = ChangeItemPropertyCommand(t, "orientation", new, old)
        self.undo_stack.push(command)

        self.scene.setSceneRect(self.template.boundingRect())
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    @Slot(int, int)
    def on_grid_size_changed(self, rows: int, cols: int):
        template = self.template
        old_grid = template.grid
        print(f"rows and cols received from toolbar are {rows}, {cols}")
        command = ChangeItemPropertyCommand(self.template, "grid", (rows, cols), old_grid)
        self.undo_stack.push(command)
        self.template.setGrid(self.registry, rows=rows, columns=cols)
        print(f"[LAYOUT_TAB] From on_grid_size_changed: Template rows and columns after change are are now {template.rows}, {template.columns}")
        
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    @Slot(bool)
    def on_auto_fill_changed(self, autofill: bool):
        self.template.auto_fill = autofill
        self.update_grid()

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

    # def _refreshGrid(self):
    #     tpl = self.template
    #     tpl.setGrid(self.registry, tpl.rows, tpl.columns)
    #     tpl.update()

    def on_template_margin_changed(self, t, p, n, o):
        # For consistency, use a loop to update all margins
        command = ChangeItemPropertyCommand(t, p, n, o)

        self.undo_stack.push(command)
        # self._refreshGrid()

    def on_template_spacing_changed(self, t, p, n, o):
        # This method is called whenever spacing_x or spacing_y changes
        print("Spacing changed, update layout as needed.")
        # self.scene.clear()
        command = ChangeItemPropertyCommand(t, p, n, o)
        self.undo_stack.push(command)
        # self.template.spacing_x = self.spacing_x.valueChanged()
        # self.template.spacing_y = self.spacing_y.valueChanged()
        # self._refreshGrid()

    def _on_policy_change(self, policy_name: str):
        # 1. Store on template (persists to JSON)
        self.template.pagination_policy = policy_name

        # 2. Invalidate existing PaginationManager & preview
        self.pagination_manager = None          # force rebuild next refresh
        self._refresh_scene_preview()

    # --- Selection and Placement Logic ---

    @Slot(str)
    def on_palette_selection_change(self, pid: str):
        """
        When a component template is selected in the layout palette,
        this sets it as the content template used by the layout.
        """
        ct = ProtoRegistry.global_get(pid)
        if ct is None:
            print(f"[WARN] No ComponentTemplate found for PID: {pid}")
            return

        try:
            _ = ct.scene()  # Touch the scene to trigger a RuntimeError if deleted
        except RuntimeError:
            print(f"[ERROR] Qt object for ComponentTemplate {pid} has been deleted.")
            return

        # Set the layout template's content reference
        self.template.content = ct
        print(f"[INFO] Layout content set to ComponentTemplate: {ct.name} ({ct.pid})")

        # Optionally trigger any UI updates
        self.template.invalidateCache()
        self.template.update()


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
        # print(item, scene_pos)

        temp = self.registry.global_get(tpid)
        item = self.template.get_item_at_position(scene_pos)
        print(item.pid)
        # print(template.pid)
        clone = self.template.registry.clone(item)
        item.content = temp


        # command = CloneComponentTemplateToSlotCommand(self.registry, template, slot)
        # self.undo_stack.push(command)

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
