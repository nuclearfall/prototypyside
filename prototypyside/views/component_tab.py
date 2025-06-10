# prototypyside/views/component_tab.py

import json
import csv
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QDockWidget,
                               QListWidgetItem, QLabel, QPushButton, QComboBox,
                               QSpinBox, QColorDialog, QFontDialog, QFileDialog, QMessageBox,
                               QCheckBox, QGraphicsItem, QGraphicsView,
                               QGraphicsScene, QToolBar) # Added QToolBar for font/measure
from PySide6.QtCore import Qt, Signal, Slot, QPointF, QRectF, QSizeF, QObject, QSize, QTimer # Removed QCoreApplication, QEvent, QKeySequence, QShortcut
from PySide6.QtGui import QPainter, QAction, QImage, QPixmap, QFont, QColor, QIcon, QKeySequence, QShortcut # Added QKeySequence, QShortcut here, removed from main_window

# Import views components
from prototypyside.views.palettes import ComponentListWidget
from prototypyside.views.layers_panel import LayersListWidget
from prototypyside.views.graphics_scene import GameComponentGraphicsScene
from prototypyside.views.graphics_view import DesignerGraphicsView

# Import widgets
from prototypyside.widgets.unit_field import UnitField
# from prototypyside.widgets.font_toolbar import FontToolbar
from prototypyside.widgets.page_size_selector import PageSizeSelector # Potentially remove if PageSizeDialog is used
from prototypyside.widgets.pdf_export_dialog import PDFExportDialog
from prototypyside.widgets.property_panel import PropertyPanel

# Import models
from prototypyside.models.game_component_template import GameComponentTemplate
from prototypyside.models.game_component_elements import (GameComponentElement, TextElement, ImageElement)
from prototypyside.services.app_settings import AppSettings
from prototypyside.services.export_manager import ExportManager
from prototypyside.services.property_setter import PropertySetter

class ComponentTab(QWidget):
    # Signals for communication with MainDesignerWindow
    status_message_signal = Signal(str, str, int) # message, type, timeout_ms
    tab_title_changed = Signal(str) # For updating the tab title if needed

    def __init__(self, parent: QWidget = None, template_data: Optional[Dict] = None):
        super().__init__(parent)
        self.settings = AppSettings(unit='px', display_dpi=300, print_dpi=300) # Each tab gets its own settings
        self.current_template = GameComponentTemplate(parent=self) # Each tab gets its own template
        self.merged_templates: List[GameComponentTemplate] = []
        self._current_selected_element: Optional['GameComponentElement'] = None
        self.export_manager = ExportManager()

        self.scene: Optional[GameComponentGraphicsScene] = None
        self.view: Optional[DesignerGraphicsView] = None
        self.property_panel: Optional[PropertyPanel] = None
        self.layers_list: Optional[LayersListWidget] = None
        # self.font_toolbar_widget: Optional[FontToolbar] = None
        self.measure_toolbar: Optional[QToolBar] = None

        self._current_drawing_color = QColor(0, 0, 0) # For drawing tools

        self.setup_ui()
        self.setup_shortcuts()

        if template_data:
            self.load_template_data(template_data)
        else:
            self.update_game_component_scene() # Initialize with default template

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
        # Assuming drawing_toolbar is also a QToolBar, it would be added similarly.
        # For simplicity in this example, drawing_toolbar is implicitly handled if it's a QToolBar instance.
        # If create_drawing_toolbar returns a QToolBar, add it here. Otherwise, it might be a floating one.
        # Let's assume it's created as a floating toolbar for now, as in original.

        main_layout.addLayout(toolbar_container)


        # Setup scene and view
        scene_rect = QRectF(0, 0, self.current_template.width_px, self.current_template.height_px)
        self.scene = GameComponentGraphicsScene(scene_rect, self, self.settings) # Parent is self (ComponentTab)
        self.view = DesignerGraphicsView(self.scene)
        self.view.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.view.setOptimizationFlag(QGraphicsView.DontSavePainterState)
        self.view.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing)

        # Central widget for scene and view should be the main area of the tab
        # We need a way to integrate this with the dock widgets.
        # For now, let's just make the view the primary content.
        # Dock widgets will be added to the MainDesignerWindow, referencing this tab's content.

        # The structure inside a ComponentTab will be:
        # main_layout (QVBoxLayout)
        #   -> toolbar_container (QHBoxLayout)
        #   -> self.view (QGraphicsView) - This will be the central focus
        #   -> (Implicitly, the dock widgets are created and added to the MainDesignerWindow,
        #       but their content is managed by this tab)

        # The QGraphicsView will be the dominant part of the tab
        main_layout.addWidget(self.view)

        # Connect signals specific to this tab's template and scene
        self.current_template.template_changed.connect(self.update_game_component_scene)
        self.current_template.element_z_order_changed.connect(self.update_layers_panel)
        self.scene.selectionChanged.connect(self.on_selection_changed)
        self.scene.element_dropped.connect(self.add_element_from_drop)

        # Initialize the property panel and layers panel (their widgets will be placed in docks in QMainWindow)
        self.setup_property_editor()
        self.setup_component_palette()
        self.setup_layers_panel()

        self.set_element_controls_enabled(False) # Initial state: no element selected

    def setup_shortcuts(self):
        delete_shortcut = QShortcut(QKeySequence.Delete, self)
        delete_shortcut.activated.connect(self.remove_selected_element)

    def load_template_data(self, template_data: Dict):
        # Disconnect previous signals from old template/scene safely
        try:
            self.current_template.element_z_order_changed.disconnect(self.update_layers_panel)
            self.current_template.template_changed.disconnect(self.update_game_component_scene)
            if self.scene: # Check if scene exists before disconnecting
                self.scene.selectionChanged.disconnect(self.on_selection_changed)
                self.scene.element_dropped.disconnect(self.add_element_from_drop)
        except (AttributeError, TypeError, RuntimeError):
            pass # Ignore if signals are not connected or objects don't exist

        # Clear existing scene items
        if self.scene:
            for item in self.scene.items():
                self.scene.removeItem(item)
            self.scene.clear()

        # Create new template from data
        self.current_template = GameComponentTemplate.from_dict(template_data, parent=self)

        # Update scene dimensions and clear existing scene
        self.scene.set_template_dimensions(self.current_template.width_px, self.current_template.height_px)
        self.view.setSceneRect(0, 0, self.current_template.width_px, self.current_template.height_px)

        # Add template elements to scene
        for element in self.current_template.elements:
            self.scene.addItem(element)

        # Connect new signals
        self.current_template.template_changed.connect(self.update_game_component_scene)
        self.current_template.element_z_order_changed.connect(self.update_layers_panel)
        self.scene.selectionChanged.connect(self.on_selection_changed)
        self.scene.element_dropped.connect(self.add_element_from_drop)

        self.tab_title_changed.emit(self.current_template.name if self.current_template.name else "New Template")
        self.update_layers_panel()
        self.on_selection_changed()
        QTimer.singleShot(0, lambda: self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio))
        self.show_status_message(f"Template loaded.", "success")


    @Slot()
    def update_game_component_scene(self):
        """Updates the scene dimensions and view based on the current template."""
        if not self.scene or not self.current_template:
            return

        new_rect = QRectF(0, 0, self.current_template.width_px, self.current_template.height_px)
        self.scene.set_template_dimensions(self.current_template.width_px, self.current_template.height_px)
        self.view.setSceneRect(new_rect)
        self.scene.update()
        QTimer.singleShot(0, lambda: self.view.fitInView(new_rect, Qt.KeepAspectRatio)) # Keep aspect ratio after update

    def get_template_data(self) -> Dict:
        return self.current_template.to_dict()

    def get_template_name(self) -> str:
        return self.current_template.name if self.current_template.name else "Unnamed Template"

    def show_status_message(self, message: str, message_type: str = "info", timeout_ms: int = 5000):
        self.status_message_signal.emit(message, message_type, timeout_ms)

    def setup_component_palette(self):
        # This will be a widget that the QMainWindow will place in a DockWidget
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

    def setup_property_editor(self):
        # This will be a widget that the QMainWindow will place in a DockWidget
        self.property_panel = PropertyPanel(settings=self.settings, parent=self)
        self.property_panel.property_changed.connect(self.on_property_changed)

        self.remove_element_btn = QPushButton("Remove Selected Element")
        self.remove_element_btn.clicked.connect(self.remove_selected_element)
        self.set_element_controls_enabled(False) # Ensure this disables the new button too

    def setup_layers_panel(self):
        # This will be a widget that the QMainWindow will place in a DockWidget
        self.layers_list = LayersListWidget(self)
        self.layers_list.element_selected_in_list.connect(self.select_element_from_layers_list)
        self.layers_list.element_z_changed_requested.connect(self.reorder_element_z_from_list_event)

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
        self.layout().addWidget(self.measure_toolbar)

    @Slot(str)
    def on_unit_change(self, unit: str):
        self.settings.unit = unit
        self.template_width_field.set_unit(unit)
        self.template_height_field.set_unit(unit)
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
        self.tab_title_changed.emit(self.current_template.name if self.current_template.name else "Unnamed Template")

    @Slot()
    def on_template_dpi_changed(self):
        new_dpi = self.game_component_dpi_spin.value()
        self.settings.dpi = new_dpi
        self.current_template.dpi = new_dpi

        self.template_width_field.set_dpi(new_dpi)
        self.template_height_field.set_dpi(new_dpi)

        if self._current_selected_element:
            self.property_panel.set_target(self._current_selected_element)
            self.property_panel.refresh()

        self.view.viewport().update()
        self.view.update()
        self.scene.update()

        self.current_template.template_changed.emit()
        self.show_status_message(f"DPI updated to {new_dpi}.", "info")

    def get_selected_element(self) -> Optional['GameComponentElement']:
        items = self.scene.selectedItems()
        if items:
            return items[0] if isinstance(items[0], GameComponentElement) else None
        return None

    # @Slot(QFont)
    # def on_font_toolbar_font_changed(self, font: QFont):
    #     element = self.get_selected_element()
    #     if element and isinstance(element, TextElement):
    #         element.set_style_property('font', font)

    @Slot()
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
            # self.font_toolbar_widget.setEnabled(isinstance(selected_element, TextElement))
            
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
            #  self.font_toolbar_widget.setEnabled(False)
            self.property_panel.set_target(None)  # Clear the panel
            self.layers_list.blockSignals(True)
            self.layers_list.clearSelection()
            self.layers_list.blockSignals(False)


    @Slot()
    def on_element_data_changed(self):
        element = self.get_selected_element()
        if element and element == self._current_selected_element:
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

        default_width, default_height = 100, 40
        if element_type == "TextElement":
            default_width, default_height = 180, 60
        elif element_type == "ImageElement":
            default_width, default_height = 200, 150

        base_name = f"{element_type.replace('Element', '').lower()}_"
        counter = 1
        existing_names = {el.get_name() for el in self.current_template.elements}
        while f"{base_name}{counter}" in existing_names:
            counter += 1
        new_name = f"{base_name}{counter}"

        new_rect_local = QRectF(0, 0, default_width, default_height)

        new_element = self.current_template.add_element(
            element_type, new_name, new_rect_local
        )

        self.scene.addItem(new_element)

        if self.snap_to_grid:
            scene_pos = self.scene.snap_to_grid(scene_pos)

        visual_offset = new_element.boundingRect().topLeft()
        new_element.setPos(scene_pos - visual_offset)

        new_element.setSelected(True)

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
            self.scene.removeItem(element)
            self.current_template.remove_element(element)
            self.on_selection_changed()
            self.show_status_message(f"Element '{element.name}' removed.", "info")
        else:
            self.show_status_message("No element selected to remove.", "warning")

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
            self.show_status_message("Background image selection cancelled.", "info")

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

    @Slot()
    def export_png_gui(self):
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

    def export_png_cli(self, output_dir: Path):
        templates_to_export = self.merged_templates if self.merged_templates else [self.current_template]
        self.export_manager.export_png(templates_to_export, output_dir=output_dir, is_cli_mode=True)

    def export_pdf_cli(self, output_dir: Path):
        templates_to_export = self.merged_templates if self.merged_templates else [self.current_template]
        pdf_output_name = "merged_output.pdf" if self.merged_templates else "current_template.pdf"
        self.export_manager.export_pdf(templates_to_export, output_file_path=output_dir / pdf_output_name, is_cli_mode=True)

    # These were previously on main_window, but belong to the tab's element management
    # since they manipulate the selected element's properties directly via PropertySetter.
    def change_text_color(self):
        element = self.get_selected_element()
        if element:
            color = QColorDialog.getColor(element._style['color'], self)
            if color.isValid():
                element.set_style_property('color', color)
            else:
                self.show_status_message("Text color selection cancelled.", "info")

    def change_bg_color(self):
        element = self.get_selected_element()
        if element:
            color = QColorDialog.getColor(element._style['bg_color'], self)
            if color.isValid():
                element.set_style_property('bg_color', color)
            else:
                self.show_status_message("Background color selection cancelled.", "info")

    def change_border_color(self):
        element = self.get_selected_element()
        if element:
            color = QColorDialog.getColor(element._style['border_color'], self)
            if color.isValid():
                element.set_style_property('border_color', color)
            else:
                self.show_status_message("Border color selection cancelled.", "info")

    @Slot(int)
    def update_element_border_width(self, px: int):
        if not self._current_selected_element:
            return
        if px != 0:
            self._current_selected_element.set_style_property('border_width', px)
            # self._current_selected_element.element_changed.emit() # PropertySetter should handle this
            self.scene.update()
            self.view.update()

    @Slot(int)
    def update_alignment(self, index: int):
        element = self.get_selected_element()
        if element and isinstance(element, TextElement): # Assuming LabelElement is not used or derived from TextElement
            alignment_map = {
                0: Qt.AlignLeft | Qt.AlignTop, 1: Qt.AlignHCenter | Qt.AlignTop, 2: Qt.AlignRight | Qt.AlignTop,
                3: Qt.AlignLeft | Qt.AlignVCenter, 4: Qt.AlignHCenter | Qt.AlignVCenter, 5: Qt.AlignRight | Qt.AlignVCenter,
                6: Qt.AlignLeft | Qt.AlignBottom, 7: Qt.AlignHCenter | Qt.AlignBottom, 8: Qt.AlignRight | Qt.AlignBottom
            }
            alignment_flag = alignment_map.get(index, Qt.AlignCenter)
            element.set_style_property('alignment', alignment_flag)

    # Simplified geometry update since PropertyPanel handles it more generically
    # @Slot(str, int)
    # def update_element_geometry(self, prop: str, px: int):
    #     if not self._current_selected_element:
    #         return
    #     setter = PropertySetter(self._current_selected_element, self.settings, self.scene)
    #     setter_fn = getattr(setter, f"set_{prop}", None)
    #     if callable(setter_fn):
    #         setter_fn(px)
    #     else:
    #         print(f"No setter for geometry property: {prop}")