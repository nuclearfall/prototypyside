# prototypyside/views/main_window.py

import sys
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
import gc
from PySide6.QtWidgets import (QMainWindow, QDockWidget, QTabWidget, QWidget,
                               QVBoxLayout, QLabel, QFileDialog, QMessageBox,
                               QToolBar, QPushButton, QHBoxLayout, QSizePolicy, QCheckBox) # Added QPushButton, QHBoxLayout for temporary property panel layout
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QStandardPaths, QSaveFile
from PySide6.QtGui import QIcon, QAction, QKeySequence, QShortcut, QUndoStack, QUndoGroup, QUndoCommand, QPainter

# Import the new ComponentTab
from prototypyside.views.tabs.component_tab import ComponentTab
from prototypyside.views.tabs.layout_tab import LayoutTab

from prototypyside.services.app_settings import AppSettings
from prototypyside.services.proto_registry import ProtoRegistry, RootRegistry
from prototypyside.views.tabs.editable_tab_bar import EditableTabBar
from prototypyside.utils.proto_helpers import get_prefix
from prototypyside.services.merge_manager import MergeManager
from prototypyside.views.panels.import_panel import ImportPanel
from prototypyside.services.export_manager import ExportManager
# from prototypyside.services.mail_room import MailRoom

def MetaKeySequence(key: str) -> QKeySequence:
    """
    Returns a QKeySequence using ⌘ on macOS and Ctrl elsewhere.

    :param key: a non‐empty string representing the key (e.g. "S", "Shift+P")
    :raises ValueError: if key is empty or the resulting sequence is invalid
    """
    if not isinstance(key, str) or not key.strip():
        raise ValueError("MetaKeySequence: `key` must be a non-empty string")

    is_mac = sys.platform.startswith("darwin")
    prefix = "Meta" if is_mac else "Ctrl"
    seq_str = f"{prefix}+{key}"

    # 3. Try to construct it, then verify it parsed to something non-empty
    seq = QKeySequence(seq_str)
    if seq.isEmpty():
        raise ValueError(f"MetaKeySequence: invalid shortcut '{seq_str}'")

    return seq


class MainDesignerWindow(QMainWindow):
    logical_disp_change = Signal()
    def __init__(self):
        super().__init__()
        screen = self.screen()
        ldpi = float(screen.logicalDotsPerInchY()) or 144.0
        # Main application settings
        # Validation temporarily disabled pending schema updates
        self.settings = AppSettings()
        self.settings.dpi_changed.connect(self.on_dpi_changed)
        self.registry = RootRegistry(ldpi=ldpi)
        self.export_registry = ProtoRegistry(parent=self.registry, root=self.registry)
        self.registry.add_child(self.export_registry)
        # self.mail_room = MailRoom(registry=self.registry)
        # self.registry.set_mail_room(self.mail_room)
        self.undo_group = QUndoGroup(self)
        self.setWindowTitle("ProtoTypySide")
        self.resize(1400, 900)
        self.setMinimumSize(800, 600)

        self.tab_widget: Optional[QTabWidget] = None
        self.palette_dock: Optional[QDockWidget] = None
        self.layers_dock: Optional[QDockWidget] = None
        self.properties_dock: Optional[QDockWidget] = None

        self.merge_manager = MergeManager()

        self.cli_mode = False # Still managed by main window

        # Autosave every 5 minutes (300 000 ms):
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(5 * 60 * 1000)
        self._autosave_timer.timeout.connect(self._auto_save_current_tab)
        self._autosave_timer.start()

        self.setup_ui()
        self.setup_status_bar()
        self.setup_actions_and_menus()

        # Add initial tabs
        self.add_new_tab(LayoutTab, "lt")
        self.add_new_tab(ComponentTab, "ct")


    ### --- GUI Setup --- ###
    def setup_ui(self):
        tabs = QTabWidget()
        editable_bar = EditableTabBar()

        # connect to update your model (e.g. ComponentTemplate.name) too:
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabBar(editable_bar)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        editable_bar.nameChanged.connect(self.on_tab_title_changed)

        self.setCentralWidget(self.tab_widget)
        self._create_import_panel()
        self.setup_dock_widgets()

    def _create_import_panel(self) -> QWidget:
        self.import_panel = ImportPanel(self.merge_manager)

    def setup_dock_widgets(self):
        # Create dock widgets
        self.toolbar_dock = QDockWidget("Toolbar", self)
        self.palette_dock = QDockWidget("Palette", self)
        self.properties_dock = QDockWidget("Properties", self)
        self.layers_dock = QDockWidget("Layers", self)

        # List of all dock widgets
        all_docks = [
            ("toolbar", self.toolbar_dock),
            ("palette", self.palette_dock),
            ("properties", self.properties_dock),
            ("layers", self.layers_dock),
        ]

        # Assign a safe fallback widget to each dock
        for name, dock in all_docks:
            fallback = QWidget()
            fallback.setObjectName(f"{name}_fallback")
            layout = QVBoxLayout(fallback)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addStretch(1)
            fallback.setLayout(layout)
            fallback.setMinimumSize(1, 1)
            dock.setWidget(fallback)

        # Add docks to the main window
        self.addDockWidget(Qt.TopDockWidgetArea, self.toolbar_dock)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.palette_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock)

        # Optional: only add layers dock if actively used
        self.addDockWidget(Qt.LeftDockWidgetArea, self.layers_dock) 
        # Optional dock features setup
        self.toolbar_dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.toolbar_dock.setTitleBarWidget(QWidget())  # hide title bar


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

    def setup_actions_and_menus(self):
        # 1. File Menu
        file_menu = self.menuBar().addMenu("&File")

        new_ctab_action = file_menu.addAction("&New Component Tab")
        new_ctab_action.triggered.connect(lambda: self.add_new_tab(ComponentTab, "ct"))

        new_ltab_action = file_menu.addAction("New &Layout Tab")
        new_ltab_action.triggered.connect(lambda: self.add_new_tab(LayoutTab, "lt"))

        open_act = file_menu.addAction("&Open")
        open_act.setShortcut(QKeySequence.Open)
        open_act.triggered.connect(self.open_template)

        file_menu.addSeparator()

        save_act = file_menu.addAction("&Save")
        save_act.setShortcut(QKeySequence.Save)
        save_act.triggered.connect(self.save_template)

        save_as_act = file_menu.addAction("Save &As…")
        save_as_act.setShortcut(QKeySequence.SaveAs)
        save_as_act.triggered.connect(self.save_as_template)


        import_menu = self.menuBar().addMenu("&Import")

        self.import_data_action = file_menu.addAction("Import &Data (CSV)")
        self.import_data_action.triggered.connect(self.import_csv_to_merge_manager)

        self.export_png_action = file_menu.addAction("&Export Current Tab as PNG...")
        self.export_png_action.triggered.connect(self.export_to_png)

        self.export_pdf_action = file_menu.addAction("Export Current Tab as PDF...")
        self.export_pdf_action.triggered.connect(self.export_to_pdf)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("E&xit")
        exit_action.triggered.connect(self.close)

        # ————— Edit Menu —————
        edit_menu = self.menuBar().addMenu("&Edit")

        # 1) Undo / Redo
        undo_act = self.undo_group.createUndoAction(self, "&Undo")
        undo_act.setShortcut(QKeySequence.Undo)
        redo_act = self.undo_group.createRedoAction(self, "&Redo")
        redo_act.setShortcut(QKeySequence.Redo)

        edit_menu.addActions([undo_act, redo_act])
        edit_menu.addSeparator()

        # 2) Copy / Cut / Paste
        copy_act = QAction("&Copy", self)
        copy_act.setShortcut(QKeySequence.Copy)
        copy_act.triggered.connect(self.on_copy)

        cut_act = QAction("Cu&t", self)
        cut_act.setShortcut(QKeySequence.Cut)
        cut_act.triggered.connect(self.on_cut)

        paste_act = QAction("&Paste", self)
        paste_act.setShortcut(QKeySequence.Paste)
        paste_act.triggered.connect(self.on_paste)

        edit_menu.addActions([copy_act, cut_act, paste_act])

        # 3) Shortcuts should fire even when menu isn’t open
        for act in (copy_act, cut_act, paste_act,
                    undo_act, redo_act):
            act.setShortcutContext(Qt.ApplicationShortcut)
            self.addAction(act)

        # ———— Project Menu ———— #
        proj_menu = self.menuBar().addMenu("Pro&ject")

        save_proj_act = QAction("Save Project...", self)
        save_proj_act.setShortcut(MetaKeySequence("Shift+S"))
        save_proj_act.triggered.connect(self.on_save_project)
        proj_menu.addAction(save_proj_act)

        open_proj_act = QAction("Open Project...", self)
        open_proj_act.setShortcut(MetaKeySequence("Shift+O"))
        open_proj_act.triggered.connect(self.on_open_project)
        proj_menu.addAction(open_proj_act)

        close_proj_act = QAction("&Close Project", self)
        close_proj_act.triggered.connect(self.on_close_project)
        proj_menu.addAction(close_proj_act)

    def update_menu_states(self, index):
        current_tab = self.tab_widget.widget(index)
        self.import_data_action.setEnabled(isinstance(current_tab, ComponentTab))
        self.export_png_action.setEnabled(isinstance(current_tab, ComponentTab))
        self.export_pdf_action.setEnabled(isinstance(current_tab, LayoutTab))



    # ———— Tab Handling ———— #
    def _auto_save_current_tab(self):
        pass
        # tab = self.get_current_tab()
        # if tab is None:
        #     return

        # # Figure out a safe temp directory
        # tmp_dir = QStandardPaths.writableLocation(QStandardPaths.TempLocation)
        # # Name it by PID so each template has its own autosave
        # filename = f"autosave-{tab.template.pid}.json"
        # tmp_path = Path(tmp_dir) / filename

        # try:
        #     # Fetch a dict just for this template
        #     data = self.registry.to_dict(root_pid=tab.template.pid)
        #     # Write atomically via QSaveFile
        #     saver = QSaveFile(str(tmp_path), self)
        #     if not saver.open(QSaveFile.WriteOnly | QSaveFile.Text):
        #         raise IOError(f"Cannot open {tmp_path}")
        #     saver.write(json.dumps(data, indent=2).encode("utf-8"))
        #     if not saver.commit():
        #         raise IOError(f"Failed to commit autosave for {tmp_path}")
        #     # Optionally, you could status‐bar a timestamp here
        # except Exception as e:
        #     # Don’t crash—just log or show a brief warning
        #     print(f"Autosave failed: {e}")


    @Slot(int)
    def on_tab_changed(self, index: int):
        # first thing: persist whatever was open before
        # self._auto_save_current_tab()

        active_tab = self.tab_widget.widget(index)
        self.update_menu_states(index)
        self.import_panel.update_for_template(active_tab.template)
        # Set the active undo stack for the selected tab
        self.undo_group.setActiveStack(active_tab.undo_stack)
        # Return early if there is no active tab
        if not active_tab:
            # Hide or clear all docks if no tab is selected
            self.toolbar_dock.hide()
            self.palette_dock.hide()
            self.properties_dock.hide()
            self.layers_dock.hide()
            return

        if isinstance(active_tab, ComponentTab):
            # Show all docks used by ComponentTab
            self.toolbar_dock.show()
            self.palette_dock.show()
            self.properties_dock.show()
            self.layers_dock.show()
            # Place ComponentTab's widgets into the main window docks
            self.toolbar_dock.setWidget(active_tab.measure_toolbar) #
            self.palette_dock.setWidget(active_tab.palette) #
            palette_container = QWidget()
            palette_layout = QVBoxLayout(palette_container)
            palette_layout.addWidget(active_tab.palette)
            palette_layout.addWidget(self.import_panel)
            palette_layout.addStretch(1)
            self.palette_dock.setWidget(palette_container)
            self.layers_dock.setWidget(active_tab.layers_list)
            self.layers_dock.show()
            # The property panel needs a container to include the "Remove" button
            prop_container = QWidget()

            prop_layout = QVBoxLayout(prop_container)
            prop_layout.setContentsMargins(0, 0, 0, 0)
            prop_layout.addWidget(active_tab.property_panel)
            prop_layout.addWidget(active_tab.remove_item_btn, alignment=Qt.AlignCenter) #
            prop_layout.addStretch(1)
            self.properties_dock.setWidget(prop_container)

        elif isinstance(active_tab, LayoutTab):
            # Show all docks used by LayoutTab (note: no layers dock)
            self.toolbar_dock.show()
            self.palette_dock.show()
            self.properties_dock.show()
            self.layers_dock.hide() # LayoutTab does not use the layers list

            # Place LayoutTab's widgets into the main window docks
            self.toolbar_dock.setWidget(active_tab.layout_toolbar)

            palette_container = QWidget()
            palette_layout = QVBoxLayout(palette_container)
            palette_layout.setContentsMargins(0, 0, 0, 0)
            palette_layout.addWidget(active_tab.layout_palette)
            palette_layout.addWidget(self.import_panel)
            palette_layout.addStretch(1)
            self.palette_dock.setWidget(palette_container)

            # The property panel for LayoutTab has its own unique combination of widgets
            prop_container = QWidget()
            prop_layout = QVBoxLayout(prop_container)
            prop_layout.setContentsMargins(0, 0, 0, 0)
            prop_layout.addWidget(active_tab.property_panel)
            prop_layout.addWidget(active_tab.margin_spacing_panel)
            prop_layout.addWidget(active_tab.remove_item_btn, alignment=Qt.AlignCenter)
            prop_layout.addStretch(1)
            self.properties_dock.setWidget(prop_container)
            active_tab.layout_palette.refresh()



    @property
    def tab_list(self):
        return [self.tab_widget.widget(i) for i in range(self.tab_widget.count())]

    @Slot(int)
    def on_dpi_changed(self, new_dpi):
        print(f"[MAINWINDOW] DPI received from settings. DPI should be set to {new_dpi}")
        for tab in self.tab_list:
            # tab.dpi = new_dpi
            tab.template.dpi = new_dpi
            tab.scene.dpi = new_dpi

    @Slot(int, str)
    def on_tab_title_changed(self, index, new_name: str):
        sender_tab = self.get_tab_at_index(index)
        template = sender_tab.template
        old_name = template.name
        sender_tab.on_property_changed(template, "name", new_name, old_name)

    def get_current_tab(self) -> Optional[ComponentTab]:
        tw = getattr(self, "tab_widget")
        return tw.currentWidget() if isinstance(tw, QTabWidget) else None

    def get_tab_at_index(self, index):
        tab_widget = getattr(self, "tab_widget")
        return self.tab_widget.widget(index) if isinstance(tab_widget, QTabWidget) else None

    @Slot()
    def add_new_tab(self, tab, prefix):
        registry = ProtoRegistry(parent=self.registry, root=self.registry)
        self.registry.add_child(registry)
        print("registry created")
        template = registry.create(prefix, registry=registry)

        new_tab = tab(parent=self, main_window=self, template=template, registry=registry)
        self.undo_group.addStack(new_tab.undo_stack)
        # Connect the tab's status message signal to the main window's item
        new_tab.status_message_signal.connect(self.show_status_message)
        new_tab.tab_title_changed.connect(self.on_tab_title_changed)
        index = self.tab_widget.addTab(new_tab, template.name)
        self.tab_widget.setCurrentIndex(index)
        self.show_status_message("New template tab created.", "info")
        # self.on_tab_changed(index) # Manually trigger update for new tab

    # @Slot()
    # def add_new_component_tab(self):
    #     new_registry = ProtoRegistry()
    #     self.registries.append(new_registry)
    #     new_template = new_registry.create("ct")
    #     new_tab = ComponentTab(parent=self, main_window=self, template=new_template, registry=new_registry)
    #     self.undo_group.addStack(new_tab.undo_stack)
    #     # Connect the tab's status message signal to the main window's item
    #     new_tab.status_message_signal.connect(self.show_status_message)
    #     new_tab.tab_title_changed.connect(self.on_tab_title_changed)
    #     index = self.tab_widget.addTab(new_tab, new_template.name)
    #     self._tab_map[new_template.pid] = index
    #     self.tab_widget.setCurrentIndex(index)
    #     self.show_status_message("New template tab created.", "info")
    #     self.on_tab_changed(index) # Manually trigger update for new tab

    # ————— Template File ———— #
    @Slot()
    def on_save_template(self):
        tab = self.get_current_tab()
        template = tab.template
        if not tab:
            return

        # Remember: each tab stores its ProtoRegistry as `tab.registry`
        path, _ = QFileDialog.getSaveFileName(self, "Save Template…", "", "JSON Files (*.json)")
        if not path:
            return

        Path(path).write_text(json.dumps(tab.registry.to_dict(tab.template)), encoding="utf-8")

        self.show_status_message(f"Template saved to {path}", "success")
        # update tab title if you like:
        self.tab_widget.setTabText(self.tab_widget.currentIndex(), Path(path).stem)

    @Slot()
    def open_template(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Template…", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

                # Validation temporarily disabled

            registry = ProtoRegistry(parent=self.registry, root=self.registry)
            self.registry.add_child(registry)
            obj = ProtoRegistry.from_dict(data, registry=registry)
            prefix = get_prefix(obj.pid)
            if prefix == 'ct':
                new_tab = ComponentTab(parent=self,
                                       main_window=self,
                                       registry=registry,
                                       template=obj)
            elif prefix == "lt":
                 new_tab = LayoutTab(parent=self,
                                       main_window=self,
                                       registry=registry,
                                       template=obj)
            if hasattr(obj, "csv_path") and getattr(obj, "csv_path") is not None:
                self.merge_manager.load_csv(obj.csv_path, template=obj)
                print(f"Template {obj.name} successfully loaded csv at path: {obj.csv_path}")      
            idx = self.tab_widget.addTab(new_tab, Path(path).stem)
            new_tab.file_path = path
            self.tab_widget.setCurrentIndex(idx)
        except Exception as e:
            QMessageBox.critical(self, "Error Opening File", str(e))
            self.show_status_message(f"Error: {e}", "error")

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
        registry = tab_to_close.template.registry
        self.registry.remove_child(registry)

        if tab_to_close:
            template_pid = tab_to_close.template.pid
            # self.merge_manager.deregister(template_pid)  # If you store merged rows by pid
            self.remove_template_from_all_tabs(template_pid)
            tab_to_close.cleanup()
            template = tab_to_close.template
            scene = tab_to_close.scene
            if template in scene.items():  # or however your scene stores items
                scene.removeItem(template)
            tab_to_close.undo_stack.clear()
            tab_to_close.deleteLater()
            gc.collect()

    def remove_template_from_all_tabs(self, template_pid: str):
        """
        Scan all tabs and remove the template from the palette
        if it's present in any open tab.
        """
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            template = getattr(tab, "template", None)
            if not template:
                continue

            # if getattr(template, "pid", None) == template_pid:
            #     tab.palette.remove_template_by_tpid(template_pid)
            #     break  # Once found, stop (unless you expect duplicates)

    @Slot()
    def save_template(self):
        tab = self.get_current_tab()
        if not tab:
            return
        path = tab.file_path
        if not path:
            self.save_as_template()
            return
            
        self.write_template_to_path(tab.template, tab.registry, tab.file_path)
        self.show_status_message(f"Saved to {tab.file_path}", "success")
        # update the tab title if needed
        idx = self.tab_widget.indexOf(tab)
        self.tab_widget.setTabText(idx, Path(tab.file_path).stem)

    @Slot()
    def save_as_template(self):
        tab = self.get_current_tab()
        if not tab:
            return

        path, _ = QFileDialog.getSaveFileName(self, "Save Template As", "", "JSON Files (*.json)")
        if not path:
            self.show_status_message("Save cancelled", "info")
            return

        self.write_template_to_path(tab.template, tab.registry, path)
        tab.file_path = path
        self.show_status_message(f"Saved to {path}", "success")
        idx = self.tab_widget.indexOf(tab)
        self.tab_widget.setTabText(idx, Path(path).stem)

    def write_template_to_path(self, template, registry, path: str):
        try:
            data = registry.to_dict(template)
            
            # Validation temporarily disabled

            saver = QSaveFile(path, self)
            if not saver.open(QSaveFile.WriteOnly | QSaveFile.Text):
                raise IOError(f"Cannot open {path} for writing")

            saver.write(json.dumps(data, indent=2).encode("utf-8"))
            if not saver.commit():
                raise IOError(f"Could not commit save to {path}")
                
            self.show_status_message(f"Saved to {path}", "success")
            
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))
            self.show_status_message(f"Error saving: {e}", "error")

    @Slot()
    def save_current_tab_template(self):
        current_tab = self.get_current_tab()
        current_template = current_tab.template
        print(f"Preparing to Save. Current template PID is {current_template.pid}")
        if not current_tab:
            self.show_status_message("No active tab to save.", "warning")
            return

        options = QFileDialog.Options()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Template", "", "JSON Files (*.json)", options=options)

        if path:
            try:
                root_pid = current_template.pid
                print(f"Saving template with root pid: {root_pid}")
                
                current_tab.save_to_file(root_pid, path)
                self.show_status_message(f"Template saved to {path}", "success")
                current_tab.tab_title_changed.emit(Path(path).stem) # Update tab title
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"An error occurred while saving: {e}")
                self.show_status_message(f"Error saving template: {e}", "error")
        else:
            self.show_status_message("Template save cancelled.", "info")




    # ———— Project Handling ———— #

    @Slot()
    def on_save_project(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "", "JSON Files (*.json)"
        )
        pass 
        # if not path:
        #     return

        # try:
        #     data = self.registry.to_dict()
        #     saver = QSaveFile(path, self)
        #     if not saver.open(QSaveFile.WriteOnly | QSaveFile.Text):
        #         raise IOError(f"Cannot open {path}")
        #     saver.write(json.dumps(data, indent=2).encode("utf-8"))
        #     if not saver.commit():
        #         raise IOError(f"Failed to commit save to {path}")
        #     self.show_status_message(f"Project saved to {path}", "success")
        # except Exception as e:
        #     QMessageBox.critical(self, "Save Project Error", str(e))
        #     self.show_status_message(f"Error saving project: {e}", "error")

    @Slot()
    def on_open_project(self):
        pass
        # path, _ = QFileDialog.getOpenFileName(
        #     self, "Open Project", "", "JSON Files (*.json)"
        # )
        # if not path:
        #     return

        # try:
        #     with open(path, "r", encoding="utf-8") as f:
        #         data = json.load(f)
        #     # 1) Rebuild the entire global registry + all children

        #     # 2) Clear out UI tabs & undo stacks
        #     self.tab_widget.clear()
        #     self.undo_group.clear()

        #     # 3) Re-create one tab per child registry
        #         # wire up undo & signals
        #         self.undo_group.addStack(tab.undo_stack)
        #         tab.status_message_signal.connect(self.show_status_message)
        #         tab.tab_title_changed.connect(self.on_tab_title_changed)

        #         # add to UI
        #         idx = self.tab_widget.addTab(tab, tab.template.name)
        #         # you might call self.on_tab_changed(idx) here if you want it to become active

        #     self.show_status_message(f"Project loaded from {path}", "success")

        # except Exception as e:
        #     QMessageBox.critical(self, "Open Project Error", str(e))
        #     self.show_status_message(f"Error loading project: {e}", "error")

    @Slot()
    def on_close_project(self):
        reply = QMessageBox.question(
            self, "Close Project",
            "Are you sure you want to close the current project? Unsaved changes will be lost.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        # 1) Clear registry (drops all children & global objects)
        self.registry.from_dict({"global": {}, "children": []})

        # 2) Clear the UI and undo stacks
        self.tab_widget.clear()
        self.undo_group.clear()

        # 3) Optionally create a fresh blank tab:
        self.add_new_tab(ComponentTab, "ct")
        self.show_status_message("Project closed; new blank template created.", "info")

    ### Copy/Pase methods

    def on_copy(self):
        """
        Copy the currently selected object (if any) into the registry+clipboard.
        """
        sel = self.scene.selectedItems()
        if sel:
            obj = sel[0]                      # assume your QGraphicsItem has a .pid
            mime = self.registry.make_mime_data_for(obj.pid)
            QGuiApplication.clipboard().setMimeData(mime)

    def on_cut(self):
        sel = self.scene.selectedItems()
        if sel:
            obj = sel[0]
            # Copy first…
            mime = self.registry.make_mime_data_for(obj.pid)
            QGuiApplication.clipboard().setMimeData(mime)
            # …then remove from registry & scene
            self.registry.deregister(obj.pid)
            self.scene.removeItem(obj)

    def on_paste(self):
        cb   = QGuiApplication.clipboard()
        md   = cb.mimeData()
        # 1) custom python-object clone
        clone = self.registry.paste_from_mime_data(md)
        if clone:
            self.scene.addItem(clone)
            return

        # 2) image data
        if md.hasImage():
            img = md.imageData()  # a QImage
            pix = QPixmap.fromImage(img)
            # if an ImageElement is already selected, update it…
            sel = self.scene.selectedItems()
            if sel and hasattr(sel[0], "setPixmap"):
                sel[0].setPixmap(pix)
            else:
                # otherwise, create a brand-new ImageElement via registry
                new_img_elem = self.registry.create("ie", pixmap=pix)
                self.scene.addItem(new_img_elem)
            return

        # 3) plain text
        if md.hasText():
            txt = md.text()
            # if the focus is in a QLineEdit, let it paste normally
            fw = QApplication.focusWidget()
            if isinstance(fw, QLineEdit):
                fw.insert(txt)
            else:
                # or inject into a selected TextElement
                sel = self.scene.selectedItems()
                if sel and hasattr(sel[0], "setText"):
                    sel[0].setText(txt)
                else:
                    # or build a new TextElement
                    new_te = self.registry.create("te", text=txt)
                    self.scene.addItem(new_te)
            return

        # 4) fallback: do nothing or show “nothing to paste”
        self.statusBar().showMessage("Nothing to paste", 2000)

    @Slot()
    def import_csv_to_merge_manager(self):
        active_tab = self.tab_widget.currentWidget()
        if not active_tab or not hasattr(active_tab, 'template'):
            QMessageBox.warning(self, "No Template", "No active template found")
            return

        # Create file dialog
        dialog = QFileDialog(self, "Import CSV for Template", "", "CSV Files (*.csv);;All Files (*)")
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)

        # Execute dialog
        if dialog.exec() != QFileDialog.Accepted:
            return

        csv_path = dialog.selectedFiles()[0]
        tmpl = active_tab.template
        data = self.merge_manager.get_csv_data_for_template(tmpl)
        # print("TEMPLATE @-names:", [el.name for el in tmpl.items if getattr(el, "name", "").startswith("@")])
        # if data:
        #     print("CSV headers:     ", data.headers)
        #     print("Validation:      ", data.validate_headers(tmpl))
        # else:
        #     print("No CSVData found (check template.csv_path and file exists).")
        data = self.merge_manager.load_csv(csv_path, active_tab.template)
        self.import_panel.set_template(active_tab.template)

        # safe debug
        if data:
            print(data.validate_headers(active_tab.template))
            self.import_panel.update_for_template(active_tab.template)
        else:
            print("[IMPORT] No CSVData returned")
     

    @Slot()
    def export_to_png(self):
        active_tab = self.tab_widget.currentWidget()
        
        if not isinstance(active_tab, ComponentTab):
            print("[EXPORT ERROR] Active tab is not a ComponentTab.")
            return

        folder = QFileDialog.getExistingDirectory(self, "Select Export Directory", str(Path.home()))

        if not folder:
            print("[EXPORT CANCELLED] No directory selected.")
            return

        export_manager = ExportManager(self.settings, active_tab.registry, self.merge_manager)
        export_manager.export_component_to_png(active_tab.template, folder, dpi=300)

        print(f"[EXPORT COMPLETED] Components exported to {folder}")

    @Slot()
    def export_to_pdf(self):
        """Export the current ComponentTemplate to a multi-page PDF using ExportManager."""
        active_tab = self.tab_widget.currentWidget()

        if not hasattr(active_tab, "template"):
            QMessageBox.warning(self, "Export Error", "No active template to export.")
            return

        template = active_tab.template

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export to PDF",
            "",
            "PDF Files (*.pdf);;All Files (*)"
        )

        if not output_path:
            return  # User canceled

        if not output_path.lower().endswith(".pdf"):
            output_path += ".pdf"

        try:

            export_manager = ExportManager(settings=self.settings, registry=self.export_registry, merge_manager=self.merge_manager, dpi=600)
            export_manager.export_with_vector_text_to_pdf(template, output_path)
            QMessageBox.information(self, "Export Complete", f"PDF successfully saved:\n{output_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"An error occurred during export:\n{e}")

    # If a layout has an older copy of the ComponentTemplate, ask if they want to update the registered ComponentTemplate
    def show_update_prompt(layout_template, original_template):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("Update Layout Template")
        msg.setText(
            f"The layout “{layout_template.name}” uses a copy of the component “{original_template.name}”.\n"
            "You’ve just reloaded the original template.\n\n"
            "Would you like to update the layout to use this new version?"
        )
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.Yes)

        result = msg.exec()

        if result == QMessageBox.Yes:
            apply_template_update_to_layout(layout_template, original_template)

    ########################
    # Command Line methods #
    ########################

    def set_cli_mode(self, mode: bool):
        self.cli_mode = mode

    def load_template_cli(self, filepath: str):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            new_tab = ComponentTab(parent=self, template_data=data)
            self.undo_group.addStack(component_tab.undo_stack)
            
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

