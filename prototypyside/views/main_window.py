# prototypyside/views/main_window.py

import sys
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (QMainWindow, QDockWidget, QTabWidget, QWidget,
                               QVBoxLayout, QLabel, QFileDialog, QMessageBox,
                               QToolBar, QPushButton, QHBoxLayout) # Added QPushButton, QHBoxLayout for temporary property panel layout
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QIcon, QAction

# Import the new ComponentTab
from prototypyside.views.component_tab import ComponentTab

# Other imports that are still needed for MainDesignerWindow's global concerns
# (e.g., AppSettings if it's truly global, not per-tab)
from prototypyside.services.app_settings import AppSettings
from prototypyside.widgets.page_size_dialog import PageSizeDialog # Used in New Template dialog

class MainDesignerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Professional Game Component Designer")
        self.resize(1400, 900)
        self.setMinimumSize(800, 600)

        # Main application settings, might be shared or passed to tabs
        self.app_settings = AppSettings(unit='px', display_dpi=300, print_dpi=300)

        self.tab_widget: Optional[QTabWidget] = None
        self.palette_dock: Optional[QDockWidget] = None
        self.layers_dock: Optional[QDockWidget] = None
        self.properties_dock: Optional[QDockWidget] = None

        self.cli_mode = False # Still managed by main window

        self.setup_ui()
        self.setup_status_bar()
        self.create_menus()

        # Add initial tab
        self.add_new_component_tab()

    def setup_ui(self):
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        self.setCentralWidget(self.tab_widget)

        self.setup_dock_widgets()

    def setup_dock_widgets(self):
        # Toolbar Dock
        self.toolbar_dock = QDockWidget("", self)
        self.addDockWidget(Qt.TopDockWidgetArea, self.toolbar_dock)
        self.toolbar_dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.toolbar_dock.setTitleBarWidget(QWidget())
        # Component Palette Dock
        self.palette_dock = QDockWidget("Components", self)
        # The actual palette widget will be dynamic based on the active tab
        self.palette_dock.setMinimumWidth(150)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.palette_dock)

        # Properties Dock
        self.properties_dock = QDockWidget("Properties", self)
        # The actual property panel widget will be dynamic based on the active tab
        self.properties_dock.setMinimumWidth(150)
        self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock)

        # Layers Dock
        self.layers_dock = QDockWidget("Layers", self)
        # The actual layers list widget will be dynamic based on the active tab
        self.layers_dock.setMinimumWidth(100)
        self.layers_dock.setMaximumWidth(300)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.layers_dock)

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
        if self.cli_mode: # Use self.cli_mode
            return
        self.status_label.setStyleSheet("color: black;")
        self.status_label.setText("")

    def create_menus(self):
        file_menu = self.menuBar().addMenu("&File")

        new_action = file_menu.addAction("&New Template Tab")
        new_action.triggered.connect(self.add_new_component_tab)

        open_action = file_menu.addAction("&Open Template in New Tab...")
        open_action.triggered.connect(self.open_template_in_new_tab)

        file_menu.addSeparator()

        save_action = file_menu.addAction("&Save Current Tab Template...")
        save_action.triggered.connect(self.save_current_tab_template)

        import_data_action = file_menu.addAction("Import &Data (CSV) for Current Tab...")
        import_data_action.triggered.connect(self.import_csv_for_current_tab)

        file_menu.addSeparator()

        export_png_action = file_menu.addAction("&Export Current Tab as PNG...")
        export_png_action.triggered.connect(self.export_current_tab_png)

        export_pdf_action = file_menu.addAction("Export Current Tab as &PDF...")
        export_pdf_action.triggered.connect(self.export_current_tab_pdf)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("E&xit")
        exit_action.triggered.connect(self.close)

    @Slot()
    def add_new_component_tab(self):
        new_tab = ComponentTab(parent=self)
        # Connect the tab's status message signal to the main window's slot
        new_tab.status_message_signal.connect(self.show_status_message)
        new_tab.tab_title_changed.connect(self.on_tab_title_changed)

        index = self.tab_widget.addTab(new_tab, "New Template")
        self.tab_widget.setCurrentIndex(index)
        self.show_status_message("New template tab created.", "info")
        self.on_tab_changed(index) # Manually trigger update for new tab

    @Slot()
    def open_template_in_new_tab(self):
        options = QFileDialog.Options()
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Template", "", "JSON Files (*.json)", options=options)

        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                new_tab = ComponentTab(parent=self, template_data=data)
                new_tab.status_message_signal.connect(self.show_status_message)
                new_tab.tab_title_changed.connect(self.on_tab_title_changed)

                index = self.tab_widget.addTab(new_tab, new_tab.get_template_name())
                self.tab_widget.setCurrentIndex(index)
                self.show_status_message(f"Template '{Path(path).name}' loaded in new tab.", "success")
                self.on_tab_changed(index)
            except json.JSONDecodeError:
                QMessageBox.critical(self, "Load Error", "Invalid JSON file.")
                self.show_status_message("Load Error: Invalid JSON file.", "error")
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"An error occurred while loading: {e}")
                self.show_status_message(f"Error loading template: {e}", "error")
        else:
            self.show_status_message("Template load cancelled.", "info")

    @Slot(int)
    def close_tab(self, index: int):
        if self.tab_widget.count() < 2:
            reply = QMessageBox.question(self, "Close Last Tab",
                                         "This is the last tab. Are you sure you want to close it? "
                                         "The application will exit.",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.close()
            else:
                self.show_status_message("Closing last tab cancelled.", "info")
            return

        tab_to_close = self.tab_widget.widget(index)
        if tab_to_close:
            # Optionally ask to save before closing
            # if isinstance(tab_to_close, ComponentTab) and tab_to_close.is_dirty: # You'd need a dirty flag in ComponentTab
            #     reply = QMessageBox.question(...)
            self.tab_widget.removeTab(index)
            tab_to_close.deleteLater() # Important to clean up

    @Slot(int)
    def on_tab_changed(self, index: int):
        active_tab = self.tab_widget.widget(index)
        if isinstance(active_tab, ComponentTab):
            # Update dock widgets with the content of the active tab
            self.toolbar_dock.setWidget(active_tab.measure_toolbar)

            self.palette_dock.setWidget(active_tab.palette)
            
            # Create a temporary container for the property panel and remove button
            # This is because a widget can only have one parent, and the property panel
            # needs to be inside the dock, but also needs its remove button.
            prop_panel_container = QWidget()
            prop_panel_layout = QVBoxLayout(prop_panel_container)
            prop_panel_layout.setContentsMargins(0,0,0,0) # Remove extra margins
            prop_panel_layout.addWidget(active_tab.property_panel)
            prop_panel_layout.addWidget(active_tab.remove_element_btn) # Use the tab's remove button
            self.properties_dock.setWidget(prop_panel_container)

            self.layers_dock.setWidget(active_tab.layers_list)
        else:
            # If no tab or invalid tab, clear dock widgets
            self.palette_dock.setWidget(QWidget())
            self.properties_dock.setWidget(QWidget())
            self.layers_dock.setWidget(QWidget())
            self.show_status_message("No active component tab selected.", "info")

    @Slot(str)
    def on_tab_title_changed(self, title: str):
        sender_tab = self.sender()
        if isinstance(sender_tab, ComponentTab):
            index = self.tab_widget.indexOf(sender_tab)
            if index != -1:
                self.tab_widget.setTabText(index, title)


    def get_current_tab(self) -> Optional[ComponentTab]:
        return self.tab_widget.currentWidget() if self.tab_widget else None

    @Slot()
    def save_current_tab_template(self):
        current_tab = self.get_current_tab()
        if not current_tab:
            self.show_status_message("No active tab to save.", "warning")
            return

        options = QFileDialog.Options()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Template", "", "JSON Files (*.json)", options=options)

        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(current_tab.get_template_data(), f, indent=4)
                self.show_status_message(f"Template saved to {path}", "success")
                current_tab.tab_title_changed.emit(Path(path).stem) # Update tab title
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"An error occurred while saving: {e}")
                self.show_status_message(f"Error saving template: {e}", "error")
        else:
            self.show_status_message("Template save cancelled.", "info")

    @Slot()
    def import_csv_for_current_tab(self):
        current_tab = self.get_current_tab()
        if not current_tab:
            self.show_status_message("No active tab to import CSV data into.", "warning")
            return
        current_tab.load_csv_and_merge()

    @Slot()
    def export_current_tab_png(self):
        current_tab = self.get_current_tab()
        if not current_tab:
            self.show_status_message("No active tab to export PNG from.", "warning")
            return
        current_tab.export_png_gui()

    @Slot()
    def export_current_tab_pdf(self):
        current_tab = self.get_current_tab()
        if not current_tab:
            self.show_status_message("No active tab to export PDF from.", "warning")
            return
        current_tab.export_pdf_gui()

    def set_cli_mode(self, mode: bool):
        self.cli_mode = mode
        # You might want to adjust UI visibility based on CLI mode if needed

    # CLI export methods (these would typically be called from a main CLI script,
    # not directly from the GUI)
    def export_png_cli_for_current_tab(self, output_dir: Path):
        current_tab = self.get_current_tab()
        if current_tab:
            current_tab.export_png_cli(output_dir)
        else:
            print("No active tab for CLI PNG export.")

    def export_pdf_cli_for_current_tab(self, output_dir: Path):
        current_tab = self.get_current_tab()
        if current_tab:
            current_tab.export_pdf_cli(output_dir)
        else:
            print("No active tab for CLI PDF export.")

    def load_template_cli(self, filepath: str):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            new_tab = ComponentTab(parent=self, template_data=data)
            new_tab.status_message_signal.connect(self.show_status_message)
            new_tab.tab_title_changed.connect(self.on_tab_title_changed)
            index = self.tab_widget.addTab(new_tab, new_tab.get_template_name())
            self.tab_widget.setCurrentIndex(index)
            print(f"Template '{Path(filepath).name}' loaded via CLI.")
            self.on_tab_changed(index)
        except Exception as e:
            print(f"Error loading template via CLI: {e}")

    def load_csv_and_merge_cli(self, filepath: str):
        current_tab = self.get_current_tab()
        if current_tab:
            current_tab.load_csv_and_merge_from_cli(filepath)
        else:
            print("No active tab for CLI CSV merge.")