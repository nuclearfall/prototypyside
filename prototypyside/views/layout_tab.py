# layout_tab.py

from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSplitter, QLabel, QGridLayout,
    QGraphicsView, QGraphicsScene)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, Slot, QTimer
from PySide6.QtGui import (QKeySequence, QShortcut, QUndoStack, 
    QUndoGroup, QUndoCommand, QPainter, QPageSize, QPixmap, QImage, QPainter)

from prototypyside.models.layout_template import LayoutTemplate, LayoutSlot
from prototypyside.views.panels.layout_property_panel import LayoutPropertyPanel, scene_to_pixmap
from prototypyside.views.toolbars.layout_toolbar import LayoutToolbar
from prototypyside.views.palettes.layout_palette import LayoutPalette
from prototypyside.views.panels.import_panel import ImportPanel
from prototypyside.widgets.unit_field import UnitField
from prototypyside.views.layout_scene import LayoutScene
from prototypyside.views.layout_view import LayoutView
from prototypyside.utils.unit_converter import to_px
from prototypyside.config import PAGE_SIZES
from prototypyside.services.undo_commands import CreateComponentCommand


class LayoutTab(QWidget):
    """Tab for editing a LayoutTemplate via grid/slot assignment."""
    new_tab = Signal()
    layout_changed = Signal()
    slot_selected = Signal(str)  # slot_pid
    template_selected = Signal(str)  # tpid
    status_message_signal = Signal(str, str, int) # message, type, timeout_ms
    tab_title_changed = Signal(str) # For updating the tab title if needed

    def __init__(self, parent, main_window, template, registry):
        super().__init__(parent)
        self.main_window = main_window
        self.registry = registry
        self.template = template
        self.settings = registry.settings
        self.undo_stack = QUndoStack()
        # self.pagination_manager = PaginationManager(template, registry, merge_mgr)
        
        self._selected_slot_pid: Optional[str] = None

        # --- 2. Setup the central widget for the tab's main area ---
        self.scene = LayoutScene(scene_rect=self.template.boundingRect(), tab=self)
        self.view = LayoutView(self.scene)
        # self.template.setGrid()
        self.view.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.view.setOptimizationFlag(QGraphicsView.DontSavePainterState)
        self.view.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing)
        self.view.setScene(self.scene)
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
        self.view.show()

        self.scene.addItem(self.template)
        self.template.setGrid(self.registry)
        self._create_layout_toolbar()
        self._create_layout_palette()
        self._create_import_panel()
        self._create_property_panel()
        self.margin_spacing_panel = self._create_margin_spacing_panel()
        self.remove_slot_btn = QPushButton("Remove Assignment")
        
        #self.remove_slot_btn.clicked.connect(self._on_remove_slot)

        # Connect signals to handler methods
        self.scene.component_dropped.connect(self.on_component_dropped)
        self.layout_toolbar.display_flag_changed.connect(self.on_display_flag_changed)
        self.template.marginsChanged.connect(self.on_template_margin_changed)
        self.template.spacingChanged.connect(self.on_template_spacing_changed)
        self.layout_palette.palette_selection_changed.connect(self.on_palette_selection_change)
        # --- 3. Set the simple, single layout for the tab itself ---
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.view)
        # --- 4. Load data and connect signals ---
        #self.load_template(self.template) # Make sure this is called!
        self.update_grid() # This method currently does nothing in your provided code for LayoutTab
        self.refresh_panels()

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
    def current_selected_slot(self) -> Optional[LayoutSlot]:
        if self._selected_slot_pid:
            return self.registry.get(self._selected_slot_pid)
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
        self.margin_top = UnitField(top, unit=self.template.unit, dpi=self.template.dpi)
        margin_grid.addWidget(QLabel("Top:"), 0, 0)
        margin_grid.addWidget(self.margin_top, 0, 1)
        
        # Bottom margin
        self.margin_bottom = UnitField(bottom, unit=self.template.unit, dpi=self.template.dpi)
        margin_grid.addWidget(QLabel("Bottom:"), 1, 0)
        margin_grid.addWidget(self.margin_bottom, 1, 1)
        
        # Left margin
        self.margin_left = UnitField(left, unit=self.template.unit, dpi=self.template.dpi)
        margin_grid.addWidget(QLabel("Left:"), 2, 0)
        margin_grid.addWidget(self.margin_left, 2, 1)
        
        # Right margin
        self.margin_right = UnitField(right, unit=self.template.unit, dpi=self.template.dpi)
        margin_grid.addWidget(QLabel("Right:"), 3, 0)
        margin_grid.addWidget(self.margin_right, 3, 1)
        
        layout.addLayout(margin_grid)
        
        # Add spacing section
        layout.addWidget(QLabel("<b>Spacing</b>"))
        
        # Create grid for spacing controls
        spacing_grid = QGridLayout()
        spacing_grid.setSpacing(5)
        
        # Horizontal spacing
        self.spacing_x = UnitField(self.template.spacing_x, unit=self.template.unit, dpi=self.template.dpi)
        spacing_grid.addWidget(QLabel("Horizontal:"), 0, 0)
        spacing_grid.addWidget(self.spacing_x, 0, 1)
        
        # Vertical spacing
        self.spacing_y = UnitField(self.template.spacing_y, unit=self.template.unit, dpi=self.template.dpi)
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
            field.editingFinishedWithValue.connect(
                self.on_template_margin_changed)

        for name, field in [("spacing_x", self.spacing_x),
                            ("spacing_y", self.spacing_y)]:
            field.editingFinishedWithValue.connect(
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
        self.layout_palette = LayoutPalette(registry=self.registry.root, parent=self)
        # print("LayoutPalette sizeHint:", self.layout_palette.sizeHint())
        # Return a widget listing all open component templates
        pass

    def _create_import_panel(self) -> QWidget:
        self.import_panel = ImportPanel()
        # print("ImportPanel sizeHint:", self.import_panel.sizeHint())
        # Return a widget showing CSV import/merge status
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
        # Rebuild scene items for each slot; gray out empty slots, assign templates as needed
        pass

    @Slot(str, QPageSize)
    def on_page_size_changed(self, display_string, qpagesize):
        self.template.page_size = display_string
        self.scene.setSceneRect(*self.template.boundingRect().getRect()) # Save the display string!
        # Optionally also save qpagesize for calculations/rendering
        self.template.setGrid(self.registry)

    @Slot(bool)
    def on_orientation_changed(self, landscape: bool):
        self.template.landscape = landscape
        self.update_grid()

    @Slot(int, int)
    def on_grid_size_changed(self, rows: int, cols: int):
        # self.template.setGrid(rows, cols)
        # self.update_grid()
        self.template.setGrid(self.registry, rows, cols)
        self.scene.update()

    @Slot(bool)
    def on_auto_fill_changed(self, autofill: bool):
        self.template.auto_fill = autofill
        self.update_grid()

    @Slot(object)
    def on_display_flag_changed(self, qflag):
        self.template.display_flag = qflag
        for row in self.template.layout_slots:
            for column in row:
                for slot in column:
                    flag = self.template.display_flag
                    slot.display_flag = flag

    def on_template_margin_changed(self):
        # For consistency, use a loop to update all margins
        for attr, field in [
            ("margin_top", self.margin_top),
            ("margin_bottom", self.margin_bottom),
            ("margin_left", self.margin_left),
            ("margin_right", self.margin_right)
        ]:
            setattr(self.template, attr, field.value())  # Or .get_value()
        
        self.template.setGrid(self.registry)

    def on_template_spacing_changed(self):
        # This method is called whenever spacing_x or spacing_y changes
        print("Spacing changed, update layout as needed.")
        # self.scene.clear()
        self.template.spacing_x = self.spacing_x.getValue()
        self.template.spacing_y = self.spacing_y.getValue()

        self.template.setGrid(self.registry)

    def _on_policy_change(self, policy_name: str, params: dict):
        # 1. Store on template (persists to JSON)
        self.template.pagination_policy = policy_name
        self.template.pagination_params = params

        # 2. Invalidate existing PaginationManager & preview
        self.pagination_manager = None          # force rebuild next refresh
        self._refresh_scene_preview()

    # --- Selection and Placement Logic ---

    @Slot(str)
    def on_palette_selection_change(self, pid):

        ct = self.registry.root.find(pid)
        # print(ct.name, ct.pid) # This works
        scene = self.main_window.get_scene_for_template_pid(pid)

        ct_rendered = scene_to_pixmap(scene, ct.width_px, ct.height_px)
        self.property_panel.display_template(ct, ct_rendered)
        self.property_panel.update()
        self.update()

    @Slot()
    def on_scene_selection_changed(self):
        selected_items = self.scene.selectedItems()
        if selected_items:
            item = selected_items[0]
            self.property_panel.display_item(item)
        else:
            self.property_panel.clear_values()

    def select_slot(self, row: int, col: int):
        slot = self.template.layout_slots[row][col]
        self._selected_slot = slot
        self.refresh_panels()

    def deselect_slot(self):
        self._selected_slot_pid = None
        self.refresh_panels()

    def on_slot_selected(self, slot_pid: str):
        if prefix(slot_pid) == "ct":
            self.property_panel.template_
        self._selected_slot_pid = slot_pid
        self.refresh_panels()

    @Slot(str, QPointF)
    def on_component_dropped(self, tpid: str, scene_pos: QPointF):
        """
        Called when the user drops a ComponentTemplate onto the layout scene.
        Delegates to the model to figure out which slot that corresponds to.
        """
        slot, pos = self.template.get_slot_at_position(scene_pos)
        component = self.registry.root.find(tpid)

        if slot is None or component is None:
            print("Drop failed: no valid slot or component found")
            return

        command = CreateComponentCommand(component, self, slot)
        self.undo_stack.push(command)

        clone = self.registry.get_last("ct")
        slot.content = clone
        print(f"Component Template clone {clone.name} being dropped into {slot.pid}")
        print(f"Verifying we're in {slot.name}: {slot.content.name}")


    # --- Export / Print ---
    def export_pdf(self, *args, **kwargs):
        # Implement PDF export logic for the current layout
        pass

    def export_png(self, *args, **kwargs):
        # Implement PNG export logic for the current layout
        pass

    def print_layout(self, *args, **kwargs):
        # Implement printing logic for the current layout
        pass

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
        if event.key() == Qt.Key_Delete and self._selected_slot_pid:
            self._on_remove_slot()
            event.accept()
        else:
            super().keyPressEvent(event)
