# prototypyside/views/main_window.py

import sys
import json
import csv
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

from PySide6.QtWidgets import (QMainWindow, QGraphicsView, QGraphicsItem, QDockWidget,
                               QListWidgetItem, QWidget, QVBoxLayout, QScrollArea, # Added QScrollArea for properties panel
                               QLabel, QLineEdit, QPushButton, QComboBox,
                               QSpinBox, QDoubleSpinBox, QFormLayout, QGroupBox,
                               QColorDialog, QFontDialog, QFileDialog, QMessageBox,
                               QHBoxLayout, QDialog, QToolBar, QCheckBox)

from PySide6.QtCore import Qt, Signal, Slot, QPointF, QRectF, QSizeF, QObject, QSize, QTimer, QCoreApplication, QEvent # Added QTimer, QCoreApplication, QEvent
from PySide6.QtGui import QPainter, QImage, QPixmap, QFont, QColor, QAction, QIcon, QPdfWriter, QTextDocument, QKeySequence, QShortcut, QMouseEvent # Added QKeySequence, QShortcut

# Import views components
from prototypyside.views.palettes import ComponentListWidget
from prototypyside.views.layers_panel import LayersListWidget
from prototypyside.views.graphics_scene import GameComponentGraphicsScene

from prototypyside.widgets.page_size_dialog import PageSizeDialog
from prototypyside.widgets.unit_field import UnitField
from prototypyside.widgets.font_toolbar import FontToolbar
from prototypyside.widgets.page_size_selector import PageSizeSelector
from prototypyside.widgets.pdf_export_dialog import PDFExportDialog
# Import models
from prototypyside.models.game_component_template import GameComponentTemplate
from prototypyside.models.game_component_elements import (GameComponentElement, TextElement,
                                                     ImageElement)
from prototypyside.services.app_settings import AppSettings
from prototypyside.views.graphics_view import DesignerGraphicsView
from prototypyside.services.export_manager import ExportManager # NEW: Import ExportManager
from prototypyside.services.property_setter import PropertySetter 
from prototypyside.widgets.property_panel import PropertyPanel


class MainDesignerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.scene = None
        self.settings = AppSettings(unit='px', display_dpi=300, print_dpi=300)
        self.current_template = GameComponentTemplate(parent=self)
        self.merged_templates: List[GameComponentTemplate] = []
        self.setWindowTitle("Professional Game Component Designer")
        self.resize(1400, 900)
        self.setMinimumSize(800, 600)

        self._current_selected_element: Optional['GameComponentElement'] = None
        self.palette_dock: Optional[QDockWidget] = None
        self.layers_dock: Optional[QDockWidget] = None

        self.cli_mode = False

        self.export_manager = ExportManager() # Instantiate ExportManager

        self.setup_ui()
        self.setup_status_bar() # Moved to after setup_ui calls so all elements are ready
        self.setup_shortcuts() # NEW: Setup keyboard shortcuts

    def on_property_changed(self, change):
        element = self.get_selected_element()
        if not element or not change:
            return
            
        setter = PropertySetter(element, self.settings, self.scene)
        
        if isinstance(change, tuple) and len(change) == 2:
            prop, value = change
            setter_fn = getattr(setter, f"set_{prop}", None)
            if callable(setter_fn):
                setter_fn(value)
            else:
                print(f"No setter for: {prop}")

    def update_property_panel(self):
        """Refresh property panel when selection changes"""
        element = self.get_selected_element()
        self.property_panel.set_target(element)
        if element:
            self.property_panel.refresh()

    @Slot()
    def update_game_component_scene(self):
        """Updates the scene dimensions and view based on the current template."""
        if not self.scene or not self.current_template:
            return

        new_rect = QRectF(0, 0, self.current_template.width_px, self.current_template.height_px)
        self.scene.set_template_dimensions(self.current_template.width_px, self.current_template.height_px)
        self.view.setSceneRect(new_rect)
        # self.view.fitInView(new_rect, Qt.KeepAspectRatio)
        self.scene.update()



    def set_cli_mode(self, mode: bool):
        self._cli_mode = mode

    def setup_shortcuts(self):
        delete_shortcut = QShortcut(QKeySequence.Delete, self)
        delete_shortcut.activated.connect(self.remove_selected_element)

    def setup_ui(self):
        self.current_template.template_changed.connect(self.update_game_component_scene)
        self.current_template.element_z_order_changed.connect(self.update_layers_panel)


        scene_rect = QRectF(0, 0, self.current_template.width_px, self.current_template.height_px)
        self.scene = GameComponentGraphicsScene(scene_rect, self, self.settings)

        self.view = DesignerGraphicsView(self.scene)
        self.view.setRenderHints(QPainter.Antialiasing |
                                QPainter.TextAntialiasing |
                                QPainter.SmoothPixmapTransform)

        self.setCentralWidget(self.view)
        self.view.setSceneRect(0, 0,
        self.current_template.width_px,
        self.current_template.height_px
)

        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.view.setOptimizationFlag(QGraphicsView.DontSavePainterState)
        self.view.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing)

        self.setup_component_palette()
        self.setup_property_editor()
        self.setup_layers_panel()
        self.create_font_toolbar()
        self.create_drawing_toolbar()
        self.create_measure_toolbar()

        self.scene.selectionChanged.connect(self.on_selection_changed)
        self.scene.element_dropped.connect(self.add_element_from_drop)

        self.create_menus()

    # NEW METHOD: Setup Keyboard Shortcuts
    def setup_shortcuts(self):
        # Shortcut for removing selected element (Cmd+Delete on Mac, Ctrl+Backspace on others)
        delete_shortcut = QShortcut(QKeySequence.Delete, self) # Use QKeySequence.Delete for platform consistency
        delete_shortcut.activated.connect(self.remove_selected_element)


    def setup_status_bar(self):
        self.statusBar = self.statusBar()
        self.status_label = QLabel("Ready")
        self.statusBar.addWidget(self.status_label)
        self.status_label.setTextFormat(Qt.RichText)

        self.status_message_timer = QTimer(self)
        self.status_message_timer.setSingleShot(True)
        self.status_message_timer.timeout.connect(self.clear_status_message)

    def show_status_message(self, message: str, message_type: str = "info", timeout_ms: int = 5000):
        color = "black"
        if message_type == "info":
            color = "#0000FF"  # Blue
        elif message_type == "success":
            color = "#008000"  # Green
        elif message_type == "warning":
            color = "#FFA500"  # Orange
        elif message_type == "error":
            color = "#FF0000"  # Red

        self.status_label.setStyleSheet(f"color: {color};")
        self.status_label.setText(message)

        self.status_message_timer.start(timeout_ms)

    def clear_status_message(self):
        if self._cli_mode:
            return # No status bar to clear in CLI mode
        self.status_label.setStyleSheet("color: black;")
        self.status_label.setText("")


    def setup_component_palette(self):
        self.palette_dock = QDockWidget("Components", self)
        self.palette = ComponentListWidget()

        components = [
            ("Text Field", "TextElement", "T"),
            ("Image Container", "ImageElement", "🖼️"),
        ]

        for name, etype, icon in components:
            item = QListWidgetItem(f"{icon} {name}")
            item.setData(Qt.UserRole, etype)
            self.palette.addItem(item)

        self.palette.setDragEnabled(True)
        self.palette.palette_item_clicked.connect(self.clear_scene_selection)

        self.palette_dock.setWidget(self.palette)
        self.palette_dock.setMinimumWidth(150)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.palette_dock)

    def setup_property_editor(self):
        property_dock = QDockWidget("Properties", self)
        property_dock_widget = QWidget()
        property_dock_layout = QVBoxLayout(property_dock_widget)
        property_dock_layout.setContentsMargins(0, 0, 0, 0)

        self.property_panel = PropertyPanel(settings=self.settings, parent=self)
        self.property_panel.property_changed.connect(self.on_property_changed)
        property_dock_layout.addWidget(self.property_panel)

        self.remove_element_btn = QPushButton("Remove Selected Element")
        self.remove_element_btn.clicked.connect(self.remove_selected_element)
        property_dock_layout.addWidget(self.remove_element_btn)

        property_dock.setWidget(property_dock_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, property_dock)


        # property_dock = QDockWidget("Properties", self)
        # property_widget = QWidget()
        # main_layout = QVBoxLayout(property_widget) # Use property_widget as the parent for the layout

        # # Add a QScrollArea for the properties to enable OS-specific scrolling
        # scroll_area = QScrollArea(self) # Parent the scroll area to main window or self
        # scroll_area.setWidgetResizable(True) # Allow the widget inside to resize
        # scroll_area.setFrameShape(QScrollArea.NoFrame) # No extra frame around the scrolled content

        # # Create a container widget for all your property groups
        # scroll_content_widget = QWidget()
        # properties_layout = QVBoxLayout(scroll_content_widget) # This layout holds all your groups

        # # Element Properties Group
        # element_group = QGroupBox("Element Properties")
        # element_layout = QFormLayout()

        # self.name_edit = QLineEdit()
        # self.name_edit.textChanged.connect(self.update_selected_name)
        # element_layout.addRow("Name:", self.name_edit)

        # self.content_edit = QLineEdit()
        # self.content_edit.textChanged.connect(self.update_selected_content)
        # element_layout.addRow("Content:", self.content_edit)

        # element_group.setLayout(element_layout)
        # properties_layout.addWidget(element_group) # Add to the scrollable layout

        # # Geometry Group
        # geometry_group = QGroupBox("Geometry")
        # form_layout = QFormLayout()

        # # Geometry Fields (UnitFields)
        # self.element_x_field = UnitField(initial_px=None, unit=self.settings.unit, dpi=self.current_template.dpi)
        # self.element_y_field = UnitField(initial_px=None, unit=self.settings.unit, dpi=self.current_template.dpi)
        # self.element_width_field = UnitField(initial_px=None, unit=self.settings.unit, dpi=self.current_template.dpi)
        # self.element_height_field = UnitField(initial_px=None, unit=self.settings.unit, dpi=self.current_template.dpi)

        # self.element_x_field.editingFinishedWithValue.connect(lambda px: self.update_element_geometry("x", px))
        # self.element_y_field.editingFinishedWithValue.connect(lambda px: self.update_element_geometry("y", px))
        # self.element_width_field.editingFinishedWithValue.connect(lambda px: self.update_element_geometry("width", px))
        # self.element_height_field.editingFinishedWithValue.connect(lambda px: self.update_element_geometry("height", px))

        # form_layout.addRow("X:", self.element_x_field)
        # form_layout.addRow("Y:", self.element_y_field)
        # form_layout.addRow("Width:", self.element_width_field)
        # form_layout.addRow("Height:", self.element_height_field)

        # geometry_group.setLayout(form_layout)
        # properties_layout.addWidget(geometry_group)
        # # Appearance Group
        # appearance_group = QGroupBox("Appearance")
        # appearance_layout = QFormLayout()

        # self.color_btn = QPushButton("Text Color")
        # self.color_btn.clicked.connect(self.change_text_color)
        # appearance_layout.addRow(self.color_btn)

        # self.bg_color_btn = QPushButton("Background Color")
        # self.bg_color_btn.clicked.connect(self.change_bg_color)
        # appearance_layout.addRow(self.bg_color_btn)

        # self.border_color_btn = QPushButton("Border Color")
        # self.border_color_btn.clicked.connect(self.change_border_color)
        # appearance_layout.addRow(self.border_color_btn)

        # # Border Width (UnitField)
        # self.border_width_field = UnitField(None, unit=self.settings.unit, dpi=self.current_template.dpi)
        # self.border_width_field.editingFinishedWithValue.connect(
        #     lambda px: self.update_element_border_width(px)
        # )
        # appearance_layout.addRow("Border Width:", self.border_width_field)

        # self.alignment_combo = QComboBox()
        # self.alignment_map = {
        #     0: Qt.AlignLeft | Qt.AlignTop, 1: Qt.AlignHCenter | Qt.AlignTop, 2: Qt.AlignRight | Qt.AlignTop,
        #     3: Qt.AlignLeft | Qt.AlignVCenter, 4: Qt.AlignHCenter | Qt.AlignVCenter, 5: Qt.AlignRight | Qt.AlignVCenter,
        #     6: Qt.AlignLeft | Qt.AlignBottom, 7: Qt.AlignHCenter | Qt.AlignBottom, 8: Qt.AlignRight | Qt.AlignBottom
        # }
        # self.reverse_alignment_map = {v: k for k, v in self.alignment_map.items()}
        # self.alignment_combo.addItems(["Top Left", "Top Center", "Top Right",
        #                                "Center Left", "Center", "Center Right",
        #                                "Bottom Left", "Bottom Center", "Bottom Right"])
        # self.alignment_combo.currentIndexChanged.connect(self.update_alignment)
        # appearance_layout.addRow("Alignment:", self.alignment_combo)

        # appearance_group.setLayout(appearance_layout)
        # properties_layout.addWidget(appearance_group) # Add to the scrollable layout

        # # Game Component Properties Group
        # game_component_props_group = QGroupBox("Game Component Properties")
        # game_component_props_layout = QFormLayout()

        # self.set_bg_image_btn = QPushButton("Set Background Image")
        # self.set_bg_image_btn.clicked.connect(self.set_game_component_background_image)
        # game_component_props_layout.addRow(self.set_bg_image_btn)

        # game_component_props_group.setLayout(game_component_props_layout)
        # properties_layout.addWidget(game_component_props_group) # Add to the scrollable layout

        # # Actions Group (Now contains only Export buttons)
        # actions_group = QGroupBox("Export Actions") # Renamed for clarity
        # actions_layout = QVBoxLayout()

        # export_btn = QPushButton("Export as PNG")
        # export_btn.clicked.connect(self.export_png_gui)
        # actions_layout.addWidget(export_btn)

        # export_pdf_btn = QPushButton("Export as PDF")
        # export_pdf_btn.clicked.connect(self.export_pdf_gui)
        # actions_layout.addWidget(export_pdf_btn)

        # actions_group.setLayout(actions_layout)
        # properties_layout.addWidget(actions_group) # Add to the scrollable layout

        # # NEW: Element Management Group (for Remove button) - Prominently placed
        # element_management_group = QGroupBox("Element Management")
        # element_management_layout = QVBoxLayout()


        # element_management_layout.addWidget(self.remove_element_btn)

        # element_management_group.setLayout(element_management_layout)
        # properties_layout.addWidget(element_management_group) # Add to the scrollable layout


        # properties_layout.addStretch() # Pushes everything to the top within the scrollable content

        # scroll_area.setWidget(scroll_content_widget) # Set the scrollable content widget

        # # Now add the scroll area to the main_layout of the property_widget
        # main_layout.addWidget(scroll_area)


        # property_dock.setWidget(property_widget)
        # property_dock.setMinimumWidth(250)
        # self.addDockWidget(Qt.RightDockWidgetArea, property_dock)

        self.set_element_controls_enabled(False) # Ensure this disables the new button too

    def setup_layers_panel(self):
        self.layers_dock = QDockWidget("Layers", self)
        layer_widget = QWidget()
        layout = QVBoxLayout()

        self.layers_list = LayersListWidget(self)
        self.layers_list.element_selected_in_list.connect(self.select_element_from_layers_list)
        self.layers_list.element_z_changed_requested.connect(self.reorder_element_z_from_list_event)

        z_order_buttons_layout = QHBoxLayout()
        bring_forward_btn = QPushButton("Bring Forward")
        send_backward_btn = QPushButton("Send Backward")
        bring_to_front_btn = QPushButton("Bring to Front")
        send_to_back_btn = QPushButton("Send to Back")

        button_height = 25
        bring_forward_btn.setFixedHeight(button_height)
        send_backward_btn.setFixedHeight(button_height)
        bring_to_front_btn.setFixedHeight(button_height)
        send_to_back_btn.setFixedHeight(button_height)

        z_order_buttons_layout.addWidget(send_to_back_btn)
        z_order_buttons_layout.addWidget(send_backward_btn)
        z_order_buttons_layout.addWidget(bring_forward_btn)
        z_order_buttons_layout.addWidget(bring_to_front_btn)

        bring_forward_btn.clicked.connect(lambda: self.adjust_z_order_of_selected(1))
        send_backward_btn.clicked.connect(lambda: self.adjust_z_order_of_selected(-1))
        bring_to_front_btn.clicked.connect(self.bring_selected_to_front)
        send_to_back_btn.clicked.connect(self.send_selected_to_back)

        layout.addWidget(self.layers_list)
        layout.addLayout(z_order_buttons_layout)
        layer_widget.setLayout(layout)
        self.layers_dock.setWidget(layer_widget)
        self.layers_dock.setMinimumWidth(100)
        self.layers_dock.setMaximumWidth(300)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.layers_dock)

    def create_drawing_toolbar(self):
        toolbar = self.addToolBar("Drawing Tools")
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.color_picker_action = QAction(QIcon.fromTheme("color-picker"), "Color Picker", self)
        self.color_picker_action.triggered.connect(self.on_color_picker_clicked)
        toolbar.addAction(self.color_picker_action)

        self.fill_action = QAction(QIcon.fromTheme("paint-fill"), "Fill Tool", self)
        self.fill_action.triggered.connect(self.on_fill_tool_clicked)
        toolbar.addAction(self.fill_action)

        self.eraser_action = QAction(QIcon.fromTheme("edit-clear"), "Eraser", self)
        self.eraser_action.triggered.connect(self.on_eraser_tool_clicked)
        toolbar.addAction(self.eraser_action)

        self.brush_action = QAction(QIcon.fromTheme("edit-brush"), "Brush Tool", self)
        self.brush_action.triggered.connect(self.on_brush_tool_clicked)
        toolbar.addAction(self.brush_action)

        toolbar.addSeparator()

        self.current_color_label = QLabel("Current Color:")
        self.current_color_display = QLabel()
        self.current_color_display.setFixedSize(20, 20)
        self.current_color_display.setStyleSheet(f"background-color: {QColor(0, 0, 0).name()}; border: 1px solid black;")
        toolbar.addWidget(self.current_color_label)
        toolbar.addWidget(self.current_color_display)

        self._current_drawing_color = QColor(0, 0, 0)
        self.update_color_display()

    def create_font_toolbar(self):
        self.font_toolbar_widget = FontToolbar(self)
        font_toolbar = self.addToolBar("Font Tools")
        font_toolbar.addWidget(self.font_toolbar_widget)
        self.font_toolbar_widget.font_changed.connect(self.on_font_toolbar_font_changed)
        self.font_toolbar_widget.setEnabled(False)

    def create_measure_toolbar(self):
        self.measure_toolbar = QToolBar("Measurement Toolbar")
        self.measure_toolbar.setObjectName("MeasurementToolbar")
        self.addToolBar(Qt.TopToolBarArea, self.measure_toolbar)

        # Unit Selector
        self.unit_selector = QComboBox()
        self.unit_selector.addItems(["in", "cm", "px"])
        self.unit_selector.setCurrentText(self.settings.unit)
        self.unit_selector.currentTextChanged.connect(self.on_unit_change)
        self.measure_toolbar.addWidget(QLabel("Unit:"))
        self.measure_toolbar.addWidget(self.unit_selector)

        # Snap to Grid
        self.snap_checkbox = QCheckBox("Snap to Grid")
        self.snap_checkbox.setChecked(True)
        self.snap_checkbox.stateChanged.connect(self.on_snap_toggle)
        self.snap_to_grid = True
        self.measure_toolbar.addWidget(self.snap_checkbox)

        # Show Grid
        self.grid_checkbox = QCheckBox("Show Grid")
        self.grid_checkbox.setChecked(True)
        self.grid_checkbox.stateChanged.connect(self.on_grid_toggle)
        self.show_grid = True
        self.measure_toolbar.addWidget(self.grid_checkbox)

        # Template Dimensions
        self.measure_toolbar.addSeparator()
        self.measure_toolbar.addWidget(QLabel("Template:"))

        self.template_width_field = UnitField(
            initial_px=self.current_template.width_px,
            unit=self.settings.unit,
            dpi=self.current_template.dpi
        )
        self.template_width_field.editingFinishedWithValue.connect(self.on_template_width_changed)

        self.template_height_field = UnitField(
            initial_px=self.current_template.height_px,
            unit=self.settings.unit,
            dpi=self.current_template.dpi
        )
        self.template_height_field.editingFinishedWithValue.connect(self.on_template_height_changed)

        self.measure_toolbar.addWidget(QLabel("Width:"))
        self.measure_toolbar.addWidget(self.template_width_field)
        self.measure_toolbar.addWidget(QLabel("Height:"))
        self.measure_toolbar.addWidget(self.template_height_field)

        # DPI SpinBox
        self.game_component_dpi_spin = QSpinBox()
        self.game_component_dpi_spin.setRange(36, 1200)
        self.game_component_dpi_spin.setValue(self.current_template.dpi)
        self.game_component_dpi_spin.valueChanged.connect(self.on_template_dpi_changed)
        self.measure_toolbar.addWidget(QLabel("DPI:"))
        self.measure_toolbar.addWidget(self.game_component_dpi_spin)


    def create_menus(self):
        file_menu = self.menuBar().addMenu("&File")

        new_action = file_menu.addAction("&New Template")
        new_action.triggered.connect(self.new_template)

        save_action = file_menu.addAction("&Save Template...")
        save_action.triggered.connect(self.save_template)

        load_action = file_menu.addAction("&Load Template...")
        load_action.triggered.connect(self.load_template)

        file_menu.addSeparator()

        import_data_action = file_menu.addAction("Import &Data (CSV)...")
        import_data_action.triggered.connect(self.load_csv_and_merge)

        file_menu.addSeparator()

        export_action = file_menu.addAction("&Export as PNG...")
        export_action.triggered.connect(self.export_png_gui)

        export_pdf_action = file_menu.addAction("Export as &PDF...")
        export_pdf_action.triggered.connect(self.export_pdf_gui)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("E&xit")
        exit_action.triggered.connect(self.close)

    @Slot()
    def new_template(self):
        # Disconnect previous signals safely
        try:
            self.current_template.element_z_order_changed.disconnect(self.update_layers_panel)
            self.current_template.template_changed.disconnect(self.update_game_component_scene)
            if self.scene:
                self.scene.selectionChanged.disconnect(self.on_selection_changed)
                self.scene.element_dropped.disconnect(self.add_element_from_drop)
        except (AttributeError, TypeError, RuntimeError):
            pass

        # Clean up old scene and view
        if hasattr(self, 'scene') and self.scene:
            for item in self.scene.items():
                self.scene.removeItem(item)
            self.scene.clear()
            self.scene.deleteLater()
            self.scene = None

        if hasattr(self, 'view') and self.view:
            self.view.setParent(None)
            self.view.deleteLater()
            self.view = None

        # Create new template and reset merged templates
        self.current_template = GameComponentTemplate(parent=self)
        self.merged_templates = []

        # Create scene rect based on current template size
        scene_rect = QRectF(0, 0, self.current_template.width_px, self.current_template.height_px)
        self.scene = GameComponentGraphicsScene(scene_rect, self, self.settings)

        # Create and configure the view
        self.view = DesignerGraphicsView(self.scene)
        self.view.setRenderHints(
            QPainter.Antialiasing |
            QPainter.TextAntialiasing |
            QPainter.SmoothPixmapTransform
        )
        self.view.setDragMode(QGraphicsView.NoDrag)
        self.view.setAcceptDrops(True)
        self.view.viewport().setAcceptDrops(True)
        self.view.setSceneRect(scene_rect)
        self.setCentralWidget(self.view)

        # Connect updated signals
        self.current_template.template_changed.connect(self.update_game_component_scene)
        self.current_template.element_z_order_changed.connect(self.update_layers_panel)
        self.scene.selectionChanged.connect(self.on_selection_changed)
        self.scene.element_dropped.connect(self.add_element_from_drop)

        # Update view and UI
        self.on_selection_changed()

        self.scene.update()

        self.show_status_message("New template created.", "info")
        QTimer.singleShot(0, lambda: self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio))


    @Slot()
    def save_template(self):
        options = QFileDialog.Options()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Template", "", "JSON Files (*.json)", options=options)

        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(self.current_template.to_dict(), f, indent=4)
                self.show_status_message(f"Template saved to {path}", "success")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"An error occurred while saving: {e}")
                self.show_status_message(f"Error saving template: {e}", "error")

    @Slot()
    def load_template(self):
        options = QFileDialog.Options()
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Template", "", "JSON Files (*.json)", options=options)

        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                new_template = GameComponentTemplate.from_dict(data, parent=self)
                self.load_template_instance(new_template)
                self.merged_templates = []

                self.show_status_message(f"Template loaded from {path}", "success")
  
            except json.JSONDecodeError:
                QMessageBox.critical(self, "Load Error", "Invalid JSON file.")
                self.show_status_message("Load Error: Invalid JSON file.", "error")
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"An error occurred while loading: {e}")
                self.show_status_message(f"Error loading template: {e}", "error")

    def load_template_instance(self, new_template: GameComponentTemplate):
        # Clean up old scene and view
        if hasattr(self, 'scene') and self.scene:
            for item in self.scene.items():
                self.scene.removeItem(item)
            del self.scene

        if hasattr(self, 'view') and self.view:
            self.view.close()
            self.view.deleteLater()
            del self.view

        # Disconnect old template signals
        try:
            self.current_template.element_z_order_changed.disconnect(self.update_layers_panel)
            self.current_template.template_changed.disconnect(self.update_game_component_scene)
        except (TypeError, RuntimeError):
            pass

        # Disconnect old scene signals if it exists
        try:
            self.scene.selectionChanged.disconnect(self.on_selection_changed)
            self.scene.element_dropped.disconnect(self.add_element_from_drop)
        except (AttributeError, TypeError, RuntimeError):
            pass

        # Replace current template
        self.current_template = new_template

        # Create new scene and view
        self.scene = GameComponentGraphicsScene(
            QRectF(0, 0, self.current_template.width_px, self.current_template.height_px),
            parent=self, settings=self.settings
        )
        self.view = DesignerGraphicsView(self.scene)

        # Configure view
        self.view.setRenderHints(
            QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform
        )
        self.view.setDragMode(QGraphicsView.NoDrag)
        self.view.setAcceptDrops(True)
        self.view.viewport().setAcceptDrops(True)
        self.setCentralWidget(self.view)

        # Connect new signals
        self.current_template.template_changed.connect(self.update_game_component_scene)
        self.current_template.element_z_order_changed.connect(self.update_layers_panel)
        self.scene.selectionChanged.connect(self.on_selection_changed)
        self.scene.element_dropped.connect(self.add_element_from_drop)

        # Add template elements to scene
        for element in self.current_template.elements:
            self.scene.addItem(element)

        # Set scene rect and refresh selection panel
        self.view.setSceneRect(0, 0, self.current_template.width_px, self.current_template.height_px)
        # Update UI panels
        self.update_layers_panel()
        self.on_selection_changed()
        QTimer.singleShot(0, lambda: self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio))


    def get_selected_element(self) -> Optional['GameComponentElement']:
        items = self.scene.selectedItems()
        if items:
            return items[0] if isinstance(items[0], GameComponentElement) else None
        return None

    @Slot(str)
    def update_selected_name(self, name: str):
        element = self.get_selected_element()
        if element and element.name != name:
            element.name = name
            element.element_changed.emit()

    @Slot(str)
    def update_selected_content(self, content: str):
        element = self.get_selected_element()
        if element:
            element.set_content(content)

    @Slot(QFont)
    def on_font_toolbar_font_changed(self, font: QFont):
        element = self.get_selected_element()
        if element and isinstance(element, TextElement):
            element.set_style_property('font', font)

    @Slot()
    def change_text_color(self):
        element = self.get_selected_element()
        if element:
            color = QColorDialog.getColor(element._style['color'], self)
            if color.isValid():
                element.set_style_property('color', color)
            else:
                self.show_status_message("Text color selection cancelled.", "info") # Status bar message for cancellation

    @Slot(str)
    def on_unit_change(self, unit: str):
        self.settings.unit = unit
        #self.scene.unit = unit

        # Update the unit display in the UnitFields
        self.template_width_field.set_unit(unit)
        self.template_height_field.set_unit(unit)

        self.measure_toolbar.update()
        self.refresh_element_property_panel()
        self.scene.update()  # force grid redraw

    @Slot(int)
    def on_snap_toggle(self, state: int):
        self.snap_to_grid = bool(state)
        self.scene.is_snap_to_grid = self.snap_to_grid  # Pass it to scene

    @Slot(int)
    def on_grid_toggle(self, state):
        self.show_grid = bool(state)
        self.measure_toolbar.update()
        self.scene.update()  # Redraw scene

    @Slot(int)
    def on_template_width_changed(self, new_px):
        self.current_template.set_width_px(new_px)
        self.update_template_scene_rect()

    @Slot(int)
    def on_template_height_changed(self, new_px):
        self.current_template.set_height_px(new_px)
        self.update_template_scene_rect()

    def update_template_scene_rect(self):
        self.scene.set_template_dimensions(
            self.current_template.width_px,
            self.current_template.height_px
        )

        self.scene.update()
        self.view.update()
        self.current_template.template_changed.emit()

    @Slot()
    def on_template_dpi_changed(self):
        new_dpi = self.game_component_dpi_spin.value()
        self.settings.dpi = new_dpi
        self.current_template.dpi = new_dpi

        # Update UnitFields to reflect new DPI
        self.template_width_field.set_dpi(new_dpi)
        self.template_height_field.set_dpi(new_dpi)

        # Also update the current element fields if one is selected
        if self._current_selected_element:
            self.refresh_element_property_panel()

        self.view.viewport().update()
        self.view.update()
        self.scene.update()

        self.current_template.template_changed.emit()
        self.show_status_message(f"DPI updated to {new_dpi}.", "info")

    @Slot()
    def change_bg_color(self):
        element = self.get_selected_element()
        if element:
            color = QColorDialog.getColor(element._style['bg_color'], self)
            if color.isValid():
                element.set_style_property('bg_color', color)
            else:
                self.show_status_message("Background color selection cancelled.", "info") # Status bar message for cancellation

    @Slot()
    def change_border_color(self):
        element = self.get_selected_element()
        if element:
            color = QColorDialog.getColor(element._style['border_color'], self)
            if color.isValid():
                element.set_style_property('border_color', color)
            else:
                self.show_status_message("Border color selection cancelled.", "info") # Status bar message for cancellation

    @Slot(int)
    def update_border_width(self, width: int):
        element = self.get_selected_element()
        if element:
            element.set_style_property('border_width', width)

    @Slot(int)
    def update_alignment(self, index: int):
        element = self.get_selected_element()
        if element and isinstance(element, (TextElement, LabelElement)):
            alignment_flag = self.alignment_map.get(index, Qt.AlignCenter)
            element.set_style_property('alignment', alignment_flag)

    @Slot()
    def on_selection_changed(self):
        selected_element = self.get_selected_element()

        if self._current_selected_element and self._current_selected_element != selected_element:
            try:
                self._current_selected_element.element_changed.disconnect(self.on_element_data_changed)
            except TypeError:
                pass

        self._current_selected_element = selected_element

        if selected_element:
            self.set_element_controls_enabled(True)
            self.font_toolbar_widget.setEnabled(isinstance(selected_element, TextElement))
            
            # Update property panel with selected element
            self.property_panel.set_target(selected_element)
            self.property_panel.refresh()
            
            selected_element.element_changed.connect(self.on_element_data_changed)

            # Update layers list selection
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
            self.property_panel.set_target(None)  # Clear the panel
            self.layers_list.blockSignals(True)
            self.layers_list.clearSelection()
            self.layers_list.blockSignals(False)

    @Slot()
    def on_element_data_changed(self):
        element = self.get_selected_element()
        if element and element == self._current_selected_element:
            # self.name_edit.blockSignals(True)
            # self.content_edit.blockSignals(True)
            # self.alignment_combo.blockSignals(True)

            # self.name_edit.setText(element.name)
            # self.content_edit.setText(element.get_content() or "")
            # current_alignment = element._style.get('alignment', Qt.AlignCenter)
            # if current_alignment in self.reverse_alignment_map:
            #     self.alignment_combo.setCurrentIndex(self.reverse_alignment_map[current_alignment])
            # else:
            #     self.alignment_combo.setCurrentIndex(4)

            # if isinstance(element, TextElement):
            #     current_font = element._style.get('font', QFont("Arial", 12))
            #     if not isinstance(current_font, QFont):
            #          current_font = QFont("Arial", 12)
            #     self.font_toolbar_widget.set_font(current_font)

            # self.name_edit.blockSignals(False)
            # self.content_edit.blockSignals(False)
            # self.alignment_combo.blockSignals(False)
            self.property_panel.refresh()
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
        self.layers_list.update_list(self.current_template.elements)

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

    def add_element_from_drop(self, scene_pos: QPointF, element_type: str):
        self.scene.clearSelection()

        # Define default dimensions based on element type
        default_width, default_height = 100, 40
        if element_type == "TextElement":
            default_width, default_height = 180, 60
        elif element_type == "ImageElement":
            default_width, default_height = 200, 150

        # Generate a unique name for the new element
        base_name = f"{element_type.replace('Element', '').lower()}_"
        counter = 1
        existing_names = {el.get_name() for el in self.current_template.elements}
        while f"{base_name}{counter}" in existing_names:
            counter += 1
        new_name = f"{base_name}{counter}"

        # Always use a rect starting at (0,0) for the internal drawing space
        new_rect_local = QRectF(0, 0, default_width, default_height)

        # Create the element using the GameComponentTemplate
        new_element = self.current_template.add_element(
            element_type, new_name, new_rect_local
        )

        # Add it to the scene
        self.scene.addItem(new_element)

        # Snap top-left corner of visual bounds to grid
        if self.snap_to_grid:
            scene_pos = self.scene.snap_to_grid(scene_pos)

        visual_offset = new_element.boundingRect().topLeft()
        new_element.setPos(scene_pos - visual_offset)

        new_element.setSelected(True)

    # @Slot(QPointF, str)
    # def add_element_from_drop(self, scene_pos: QPointF, element_type: str):
    #     self.scene.clearSelection()

    #     # Define default dimensions based on element type
    #     default_width, default_height = 100, 40
    #     if element_type == "TextElement":
    #         default_width, default_height = 180, 60
    #     elif element_type == "ImageElement":
    #         default_width, default_height = 200, 150

    #     # Generate a unique name for the new element
    #     base_name = f"{element_type.replace('Element', '').lower()}_"
    #     counter = 1
    #     existing_names = {el.get_name() for el in self.current_template.elements}
    #     while f"{base_name}{counter}" in existing_names:
    #         counter += 1
    #     new_name = f"{base_name}{counter}"

    #     # Always use a rect starting at (0,0) for the internal drawing space
    #     new_rect_local = QRectF(0, 0, default_width, default_height)

    #     # Create the element using the GameComponentTemplate
    #     new_element = self.current_template.add_element(
    #         element_type, new_name, new_rect_local
    #     )

    #     # Add it to the scene
    #     self.scene.addItem(new_element)

    #     # Center it at the drop position by offsetting by half the dimensions
    #     center_offset = QPointF(default_width / 2, default_height / 2)
    #     new_element.setPos(scene_pos - center_offset)

    #     new_element.setSelected(True)


    @Slot()
    def update_game_component_dimensions(self):
        new_width_in = self.game_component_width.value()
        new_height_in = self.game_component_height.value()
        new_dpi = self.game_component_dpi_spin.value()

        self.current_template.width_in = new_width_in
        self.current_template.height_in = new_height_in
        self.current_template.dpi = new_dpi

        self.scene.set_template_dimensions(self.current_template.width_px, self.current_template.height_px)

        new_scene_rect = QRectF(0, 0, self.current_template.width_px, self.current_template.height_px)
        self.scene.setSceneRect(new_scene_rect)
        self.view.setSceneRect(new_scene_rect)

        # self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

        self.current_template.template_changed.emit()

        self.view.viewport().update()
        self.view.update()
        self.scene.update()

        self.show_status_message("Game Component dimensions and DPI have been updated.", "info")

    def set_element_controls_enabled(self, enabled: bool):
        # self.name_edit.setEnabled(enabled)
        # self.content_edit.setEnabled(enabled)
        # self.color_btn.setEnabled(enabled)
        # self.bg_color_btn.setEnabled(enabled)
        # self.border_color_btn.setEnabled(enabled)
        # self.alignment_combo.setEnabled(enabled)
        # self.remove_element_btn.setEnabled(enabled)
        self.property_panel.setEnabled(enabled)
        self.remove_element_btn.setEnabled(enabled)

    @Slot()
    def remove_selected_element(self):
        element = self.get_selected_element()
        if element:
            # QMessageBox for confirmation retained as it's a destructive action
            reply = QMessageBox.question(self, "Remove Element",
                                         f"Are you sure you want to remove '{element.name}'?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                self.show_status_message("Element removal cancelled.", "info")
                return
            self.scene.removeItem(element)
            self.current_template.remove_element(element)
            self.on_selection_changed()
            self.show_status_message(f"Element '{element.name}' removed.", "info")
        else:
            self.show_status_message("No element selected to remove.", "warning")

    def refresh_element_property_panel(self):
        element = self._current_selected_element
        dpi = self.current_template.dpi

        if element:
            rect = element.rect
            self.property_panel.set_target(element)
            self.property_panel.refresh()
        #     self.element_x_field.set_dpi(dpi)
        #     self.element_x_field.set_unit(self.settings.unit)
        #     self.element_x_field.set_px_value(element.pos().x())

        #     self.element_y_field.set_dpi(dpi)
        #     self.element_y_field.set_unit(self.settings.unit)
        #     self.element_y_field.set_px_value(element.pos().y())

        #     self.element_width_field.set_dpi(dpi)
        #     self.element_width_field.set_unit(self.settings.unit)
        #     self.element_width_field.set_px_value(rect.width())

        #     self.element_height_field.set_dpi(dpi)
        #     self.element_height_field.set_unit(self.settings.unit)
        #     self.element_height_field.set_px_value(rect.height())

        #     self.border_width_field.set_dpi(dpi)
        #     self.border_width_field.set_unit(self.settings.unit)
        #     if hasattr(element, "border_width"):
        #         self.border_width_field.set_px_value(element.border_width)
        #     else:
        #         self.border_width_field.set_px_value(0)

        #     # Enable fields
        #     self.element_x_field.setEnabled(True)
        #     self.element_y_field.setEnabled(True)
        #     self.element_width_field.setEnabled(True)
        #     self.element_height_field.setEnabled(True)
        #     self.border_width_field.setEnabled(True)

        # else:
        #     # Disable and clear all fields
        #     self.element_x_field.set_px_value(None)
        #     self.element_y_field.set_px_value(None)
        #     self.element_width_field.set_px_value(None)
        #     self.element_height_field.set_px_value(None)
        #     self.border_width_field.set_px_value(None)

        #     self.element_x_field.setEnabled(False)
        #     self.element_y_field.setEnabled(False)
        #     self.element_width_field.setEnabled(False)
        #     self.element_height_field.setEnabled(False)
        #     self.border_width_field.setEnabled(False)

            
    #### Paint Toolbar ####

    @Slot()
    def on_color_picker_clicked(self):
        color = QColorDialog.getColor(self._current_drawing_color, self, "Select Drawing Color")
        if color.isValid():
            self._current_drawing_color = color
            self.update_color_display()
            self.show_status_message(f"Drawing color set to {color.name()}.", "info")
        else:
            self.show_status_message("Color picker cancelled.", "info")


    @Slot()
    def on_fill_tool_clicked(self):
        self.show_status_message("Fill tool selected. Click on an area to fill.", "info")

    @Slot()
    def on_eraser_tool_clicked(self):
        self.show_status_message("Eraser tool selected. Drag to erase.", "info")

    @Slot()
    def on_brush_tool_clicked(self):
        self.show_status_message("Brush tool selected. Drag to draw.", "info")


    @Slot()
    def on_element_dimension_changed(self, element, attr, px):
        setattr(element, attr, px)
        self.property_panel.refresh()
        self.scene.update()
        self.view.update()

    @Slot(str, int)
    def update_element_geometry(self, prop: str, px: int):
        if not self._current_selected_element:
            return

        element = self._current_selected_element
        rect = element.rect
        pos = element.pos()

        if prop == "x":
            element.setPos(QPointF(px, pos.y()))
        elif prop == "y":
            element.setPos(QPointF(pos.x(), px))
        elif prop == "width":
            element.setRect(QRectF(rect.x(), rect.y(), px, rect.height()))
        elif prop == "height":
            element.setRect(QRectF(rect.x(), rect.y(), rect.width(), px))

        element.update()
        self.scene.update()
        self.view.viewport().update()




    def update_color_display(self):
        self.current_color_display.setStyleSheet(f"background-color: {self._current_drawing_color.name()}; border: 1px solid black;")
    @Slot()
    def set_game_component_background_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Background Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)")
        if path:
            if self.current_template.set_background_image(path):
                self.show_status_message("Game Component background image set successfully.", "success")
            else:
                self.show_status_message("Background Error: Could not set background image. File may be invalid.", "error")
        else:
            self.show_status_message("Background image selection cancelled.", "info") # Status bar message for cancellation

    @Slot()
    def load_csv_and_merge(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open CSV Data for Merge", "", "CSV Files (*.csv)")
        if path:
            self.perform_csv_merge(path)
        else:
            self.show_status_message("CSV import cancelled.", "info")


    def load_csv_and_merge_from_cli(self, path: str):
        self.perform_csv_merge(path, cli_mode=True)

    def perform_csv_merge(self, filepath: str, cli_mode: bool = False):
        try:
            with open(filepath, newline='', encoding='utf-8') as csvfile:
                header_line = csvfile.readline().strip()
                raw_headers = [h.strip() for h in header_line.split(',')]
                cleaned_headers = [h for h in raw_headers if h]

                csvfile.seek(0)
                if header_line:
                    csvfile.readline()

                reader = csv.reader(csvfile)
                data_rows_raw = list(reader)

                data_rows = []
                for row_list in data_rows_raw:
                    if not row_list or len(row_list) < len(cleaned_headers):
                        print(f"Warning: Skipping empty or malformed row with too few columns: {row_list}")
                        self.show_status_message(f"Warning: Skipping malformed row with too few columns.", "warning")
                        continue
                    # Ensure row_list has enough elements for all headers
                    if len(row_list) >= len(cleaned_headers):
                        row_data = {cleaned_headers[j]: row_list[j].strip() for j in range(len(cleaned_headers))}
                        data_rows.append(row_data)
                    else:
                        print(f"Warning: Skipping malformed row with too few columns: {row_list}")
                        self.show_status_message(f"Warning: Skipping malformed row with too few columns in row {len(data_rows)+1}.", "warning")


                if not data_rows:
                    self.show_status_message("CSV Merge Error: The CSV file is empty or has no data rows after processing headers.", "error")
                    return

            self.merged_templates = []
            # output_dir = Path("./merged_templates") # No longer needed here as export methods handle dir selection

            for i, row_data in enumerate(data_rows):
                merged_template = GameComponentTemplate.from_dict(self.current_template.to_dict(), parent=None)
                merged_template.background_image_path = self.current_template.background_image_path

                for element in merged_template.elements:
                    if element.name.startswith('@'):
                        field_name_in_template = element.name # Remove '@' for lookup
                        if field_name_in_template in row_data:
                            content = row_data[field_name_in_template]
                            if isinstance(element, ImageElement):
                                if content and Path(content).is_file():
                                    element.set_content(content)
                                else:
                                    print(f"Warning: Image file not found for {element.name} (row {i+1}): {content}")
                                    self.show_status_message(f"Warning: Image not found for field '{element.name}' in row {i+1}.", "warning")
                                    element.set_content("")
                            else:
                                element.set_content(content)
                        else:
                            print(f"Warning: Merge field '{element.name}' not found in CSV row {i+1}.")
                            self.show_status_message(f"Warning: Field '{element.name}' not found in CSV row {i+1}.", "warning")
                            element.set_content(f"<{element.name} Not Found>")
                self.merged_templates.append(merged_template)

            if not cli_mode:
                self.show_status_message(f"Successfully created {len(self.merged_templates)} merged template instances. You can now export them as PNGs or PDF.", "success")
            else:
                print(f"Successfully created {len(self.merged_templates)} merged template instances.")

        except FileNotFoundError:
            if not cli_mode:
                QMessageBox.critical(self, "CSV Merge Error", f"File not found: {filepath}")
                self.show_status_message(f"CSV Merge Error: File not found: {filepath}", "error")
            else:
                print(f"Error: File not found: {filepath}")
        except Exception as e:
            if not cli_mode:
                QMessageBox.critical(self, "CSV Merge Error", f"An error occurred during merge: {str(e)}")
                self.show_status_message(f"An error occurred during merge: {str(e)}", "error")
            else:
                print(f"Error during CSV merge: {str(e)}")

    def _render_template_to_image(self, template: GameComponentTemplate) -> Optional[QImage]:
        image = QImage(template.width_px, template.height_px, QImage.Format_ARGB32)
        image.fill(Qt.transparent)

        painter = QPainter(image)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)

        if template.background_image_path:
            bg_pixmap = QPixmap(template.background_image_path)
            if not bg_pixmap.isNull():
                scaled_bg = bg_pixmap.scaled(
                    QSize(template.width_px, template.height_px),
                    Qt.IgnoreAspectRatio,
                    Qt.SmoothTransformation
                )
                painter.drawPixmap(0, 0, scaled_bg)

        temp_scene = GameComponentGraphicsScene(QRectF(0, 0, template.width_px, template.height_px), None, settings=self.settings)
        for element in template.elements:
            temp_scene.addItem(element)

        temp_scene.render(painter,
                          QRectF(0, 0, template.width_px, template.height_px),
                          temp_scene.sceneRect())
        painter.end()

        for item in temp_scene.items():
            temp_scene.removeItem(item)
        del temp_scene

        return image

    @Slot()
    def export_png_gui(self): # Renamed for clarity
        templates_to_export = self.merged_templates if self.merged_templates else [self.current_template]

        if not templates_to_export:
            self.show_status_message("PNG Export Failed: No templates to export.", "error")
            return

        output_dir_str = QFileDialog.getExistingDirectory(self, "Select Output Directory for PNGs")
        if not output_dir_str:
            self.show_status_message("PNG Export cancelled.", "info")
            return

        output_dir = Path(output_dir_str)
        
        if self.export_manager.export_png(templates_to_export, output_dir=output_dir, is_cli_mode=False):
            self.show_status_message(f"Successfully exported PNG(s) to {output_dir.resolve()}", "success")
        else:
            self.show_status_message("PNG Export Failed.", "error")



    @Slot()
    def export_pdf_gui(self):
        templates_to_export = self.merged_templates if self.merged_templates else [self.current_template]

        if not templates_to_export:
            self.show_status_message("PDF Export Failed: No templates to export.", "error")
            return

        dialog = PDFExportDialog(self)
        if not dialog.exec():
            self.show_status_message("PDF Export cancelled.", "info")
            return

        filenames = dialog.selectedFiles()
        if not filenames:
            self.show_status_message("PDF Export cancelled.", "info")
            return

        output_file_path = Path(filenames[0])
        page_size = dialog.get_page_size()

        if self.export_manager.export_pdf(
            templates_to_export,
            output_file_path=output_file_path,
            page_size=page_size,
            is_cli_mode=False
        ):
            self.show_status_message(f"Successfully exported PDF to {output_file_path.resolve()}", "success")
        else:
            QMessageBox.critical(self, "PDF Export Error", "An error occurred during PDF export.")
            self.show_status_message("PDF Export Failed.", "error")


    # --- CLI Export Methods (public for main.py to call) ---

    def export_png_cli(self, output_dir: Path): # NEW: CLI-specific PNG export
        templates_to_export = self.merged_templates if self.merged_templates else [self.current_template]
        self.export_manager.export_png(templates_to_export, output_dir=output_dir, is_cli_mode=True)


    @Slot(int)
    def update_element_border_width(self, px: int):
        style =  self._current_selected_element.get_style()
        if not self._current_selected_element:
            return
        if px != 0:
            self._current_selected_element.set_border_width(px)
            self._current_selected_element.element_changed.emit()
            self.scene.update()
            self.view.update()


    def export_pdf_cli(self, output_dir: Path): # NEW: CLI-specific PDF export
        templates_to_export = self.merged_templates if self.merged_templates else [self.current_template]
        # For PDF, the ExportManager expects a full file path, not just a directory.
        # We'll default to 'merged_output.pdf' or 'current_template.pdf' within the output_dir.
        pdf_output_name = "merged_output.pdf" if self.merged_templates else "current_template.pdf"
        self.export_manager.export_pdf(templates_to_export, output_file_path=output_dir / pdf_output_name, is_cli_mode=True)



