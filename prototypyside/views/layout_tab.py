# layout_tab.py

from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSplitter, QLabel, QGridLayout,
    QGraphicsView)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, Slot, QTimer
from PySide6.QtGui import (QKeySequence, QShortcut, QUndoStack, 
    QUndoGroup, QUndoCommand, QPainter)
from prototypyside.models.layout_template import LayoutTemplate, LayoutSlot
from prototypyside.views.layout_property_panel import LayoutPropertyPanel
from prototypyside.widgets.layout_toolbar import LayoutToolbar
from prototypyside.widgets.layout_palette import LayoutPalette
from prototypyside.widgets.import_panel import ImportPanel
from prototypyside.widgets.unit_field import UnitField
from prototypyside.views.layout_scene import LayoutScene
from prototypyside.views.layout_view import LayoutView
from prototypyside.utils.unit_converter import to_px
from prototypyside.config import PAGE_SIZES
# Import your palette, panel, toolbar widgets as needed

class LayoutTab(QWidget):
    """Tab for editing a LayoutTemplate via grid/slot assignment."""
    new_tab = Signal()
    layout_changed = Signal()
    slot_selected = Signal(str)  # slot_pid
    template_selected = Signal(str)  # tpid
    status_message_signal = Signal(str, str, int) # message, type, timeout_ms
    tab_title_changed = Signal(str) # For updating the tab title if needed
    # layout_tab.py (fixed __init__ section)

    # layout_tab.py (corrected __init__ section)
    def __init__(self, parent, template, registry):
        super().__init__(parent)
        self.registry = registry
        self.template = template
        self.settings = registry.settings
        self.undo_stack = QUndoStack()
        self._current_selected_slot_pid: Optional[str] = None

        # --- 1. Create UI components to be docked by MainWindow ---
        # These are now member properties, not part of this widget's layout
        self._create_layout_toolbar()
        self._create_layout_palette()
        self._create_import_panel()
        self._create_property_panel()
        self.margin_spacing_panel = self._create_margin_spacing_panel()
        self.remove_slot_btn = QPushButton("Remove Assignment")
        self.remove_slot_btn.clicked.connect(self._on_remove_slot)

        # --- 2. Setup the central widget for the tab's main area ---
        self.scene = LayoutScene(scene_rect=self.template.boundingRect(), tab=self)
        self.view = LayoutView(self.scene)
        self.view.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.view.setOptimizationFlag(QGraphicsView.DontSavePainterState)
        self.view.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing)
        print(f"Size of scene rect before add item: {self.scene.sceneRect()}")
        self.scene.addItem(self.template)
        print(f"Size of scene rect after add item: {self.scene.sceneRect()}")
        self.view.setScene(self.scene)
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
        self.view.show()

        # Connect margin/spacing signals to handler methods
        self.template.marginsChanged.connect(self.on_template_margins_changed)
        self.template.spacingChanged.connect(self.on_template_spacing_changed)

        # --- 3. Set the simple, single layout for the tab itself ---
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.view)
        
        # --- 4. Load data and connect signals ---
        #self.load_layout_template(self.template) # Make sure this is called!
        self._connect_signals()
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

    def _connect_signals(self):

        tb = self.layout_toolbar
        # tb.page_size_changed.connect(self.on_page_size_changed)
        tb.orientation_changed.connect(self.on_orientation_changed)
        tb.grid_size_changed.connect(self.on_grid_size_changed)
        tb.margin_changed.connect(self.on_margin_changed)
        tb.spacing_changed.connect(self.on_spacing_changed)
        tb.autofill_checkbox.stateChanged.connect(lambda state: self.on_auto_fill_changed(state == 2))

    # --- Properties ---
    @property
    def layout_template(self) -> LayoutTemplate:
        return self.template

    @property
    def current_selected_slot(self) -> Optional[LayoutSlot]:
        if self._current_selected_slot_pid:
            return self.registry.get(self._current_selected_slot_pid)
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
                lambda val, n=name: self.on_margin_changed(n, val))

        for name, field in [("spacing_x", self.spacing_x),
                            ("spacing_y", self.spacing_y)]:
            field.editingFinishedWithValue.connect(
                lambda val, n=name: self.on_spacing_changed(n, val))           
        # print("MarginPanel sizeHint:", self.margin_panel.sizeHint())
        return self.margin_panel

    def on_template_margins_changed(self):
        # This method is called whenever any margin property changes
        # You might update the view, redraw the layout, or update a property panel
        print("Margins changed, update layout or property panel as needed.")
        # For example:
        # self.refresh_layout_view()
        # self.update_property_panel()

    def on_template_spacing_changed(self):
        # This method is called whenever spacing_x or spacing_y changes
        print("Spacing changed, update layout as needed.")
        self.scene.update()
        # self.refresh_layout_view()
        # self.update_property_panel()

    def _create_layout_toolbar(self) -> QWidget:
        self.layout_toolbar = LayoutToolbar(self.settings, parent=self)
        
        # Connect signals
        # self.layout_toolbar.page_size_changed.connect(self.on_page_size_changed)
        self.layout_toolbar.orientation_changed.connect(self.on_orientation_changed)
        self.layout_toolbar.grid_size_changed.connect(self.on_grid_size_changed)
        self.layout_toolbar.autofill_changed.connect(self.on_auto_fill_changed)
        # print("LayoutToolbar sizeHint:", self.layout_toolbar.sizeHint())
        return self.layout_toolbar

    def _create_layout_palette(self) -> QWidget:
        self.layout_palette = LayoutPalette(registry=self.registry.parent_registry, parent=self)
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

    # def assign_template_to_slot(self, row: int, col: int, tpid: str):
    #     self.layout_template.assign_template_to_slot(row, col, tpid, self.registry)
    #     self.update_grid()
    #     self.push_undo_command(...)  # Implement appropriate QUndoCommand

    # def clear_slot(self, row: int, col: int):
    #     self.layout_template.clear_slot(row, col, self.registry)
    #     self.update_grid()
    #     self.push_undo_command(...)  # Implement appropriate QUndoCommand

    # def auto_fill_templates(self, tpids: List[str]):
    #     self.layout_template.auto_fill_templates(tpids, self.registry)
    #     self.update_grid()
    #     self.push_undo_command(...)  # Implement appropriate QUndoCommand

    # def on_auto_fill_changed(self, checked: bool):
    #     self.layout_template.auto_fill = checked
    #     self.update_grid()

    # --- Selection Logic ---
    def select_slot(self, row: int, col: int):
        slot_pid = self.layout_template.slots[row][col]
        self._current_selected_slot_pid = slot_pid
        self.refresh_panels()

    def deselect_slot(self):
        self._current_selected_slot_pid = None
        self.refresh_panels()

    def on_slot_selected(self, slot_pid: str):
        self._current_selected_slot_pid = slot_pid
        self.refresh_panels()

    def on_palette_template_selected(self, tpid: str):
        self._layout_tpid = tpid
        self.refresh_panels()

    def _on_remove_slot(self):
        """Clear template from selected slot."""
        pass
        # slot = self.current_selected_slot
        # if slot is not None:
        #     for row in range(self.layout_template.rows):
        #         for col in range(self.layout_template.cols):
        #             if self.layout_template.slots[row][col] == slot.pid:
        #                 self.clear_slot(row, col)
        #                 return

    @Slot(str, QPointF)
    def on_component_dropped(self, tpid: str, scene_pos: QPointF):
        """
        Called when the user drops a ComponentTemplate onto the layout scene.
        Delegates to the model to figure out which slot that corresponds to.
        """
        # 2️⃣ Ask the model which slot (if any) lives under that scene_pos
        slot_pid, slot_origin = self.layout_template.get_slot_at_position(scene_pos)

        if slot_pid:
            # registry sets slot component_id.
            comp_inst = self.registry.create_component_instance(tpid=tpid, slot_pid=slot_pid)
            # 🔜 next: create & place your ComponentInstance in that slot.
            #    You’ll probably do something like:
            #    tpl = self.registry.get(tpid)
            #    instance = ComponentInstance(tpl, data_row, QRectF(...))
            #    instance.setPos(slot_origin)
            #    self.scene.addItem(instance)
            pass
        else:
            self.show_status_message(f"No layout‐slot at {scene_pos}", "warning")


    def fit_and_place_instance(self, instance, slot_origin: QPointF):
        """
        1. Delegate resizing to the LayoutTemplate (warn if scaled)
        2. Center‐align the (possibly scaled) instance within the slot
        3. Add to the scene
        """
        # 1️⃣ resize (and get scale factor)
        scale = self.layout_template.resize_component(instance)

        if scale < 1.0:
            QMessageBox.warning(
                self,
                "Component Too Large",
                "This component is larger than its slot; it has been scaled down to fit."
            )

        # 2️⃣ compute centered offset
        slot_w, slot_h = self.layout_template.get_cell_size_px()
        inst_rect = instance.boundingRect()
        inst_w = inst_rect.width() * scale
        inst_h = inst_rect.height() * scale

        offset_x = (slot_w - inst_w) / 2
        offset_y = (slot_h - inst_h) / 2

        instance.setPos(slot_origin + QPointF(offset_x, offset_y))

        # 3️⃣ add to scene
        self.scene.addItem(instance)
    ## Existing files are loaded in main_window.py
    # def load_template(self, template: LayoutTemplate):
    #     # Remove any existing item
    #     if self.template_item:
    #         self.removeItem(self.template_item)
    #         self.template_item = None
    #     # Clear scene for fresh layout
    #     self.clear()
    #     # Create and add the template item
    #     item = LayoutTemplateItem(template)
    #     self.template_item = item
    #     self.addItem(item)
    #     # Set the scene rectangle to match page size
    #     self.setSceneRect(item.boundingRect())

    #     # Connect model signals to update view
    #     item.pageRectChanged.connect(lambda: self._on_template_shape_changed())
    #     item.gridSettingsChanged.connect(lambda: self._on_template_shape_changed())
    #     item.slotsChanged.connect(lambda: self._on_template_shape_changed())

    # --- Toolbar / UI Interactions ---

    def on_orientation_changed(self, landscape: bool):
        self.layout_template.landscape = landscape
        self.update_grid()

    def on_grid_size_changed(self, rows: int, cols: int):
        template = self.layout_template
        pid = template.pid 
        old_array_len = template.rows * template.cols
        template.rows = rows
        template.cols = cols
        new_array_len = rows, cols

        if old_array_len == new_array_len:
            return
        elif old_array_len > new_array_len:
            self.registry.grid_contracted(pid, rows=rows, cols=cols)
        elif old_array_len < new_array_len:
            self.registry.grid_expanded(pid, rows=rows, cols=cols)

        self.update_grid()

    def on_margin_changed(self, margin_type: str, value: str):
        setattr(self.layout_template, margin_type, value)
        self.scene.update()
        self.update_grid()

    def on_spacing_changed(self, spacing_type: str, value: str):
        setattr(self.layout_template, spacing_type, value)
        print(f"Spacing x should be set to {value} currently {self.layout_template.spacing_x}")
        self.update_grid()

    def on_auto_fill_changed(self, checked: bool):
        self.layout_template.auto_fill = checked
        self.update_grid()

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
        if event.key() == Qt.Key_Delete and self._current_selected_slot_pid:
            self._on_remove_slot()
            event.accept()
        else:
            super().keyPressEvent(event)
