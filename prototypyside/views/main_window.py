# prototypyside/views/main_window.py

import sys
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
import gc
from PySide6.QtWidgets import (QMainWindow, QDockWidget, QTabWidget, QWidget,
                               QVBoxLayout, QLabel, QFileDialog, QMessageBox,
                               QToolBar, QPushButton, QHBoxLayout, QSizePolicy, QCheckBox, QTabBar) # Added QPushButton, QHBoxLayout for temporary property panel layout
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QStandardPaths, QSaveFile, QIODevice
from PySide6.QtGui import QIcon, QAction, QKeySequence, QShortcut, QUndoStack, QUndoGroup, QUndoCommand, QPainter



from prototypyside.services.app_settings import AppSettings
from prototypyside.services.proto_registry import ProtoRegistry, RootRegistry
from prototypyside.utils.pkey_sequence import PKeySequence, Key
 
from prototypyside.services.merge_manager import MergeManager
from prototypyside.views.panels.import_panel import ImportPanel
from prototypyside.services.export_manager import ExportManager

from prototypyside.utils.qt_helpers import find_unit_str_like_fields
from prototypyside.services.proto_class import ProtoClass
from prototypyside.models.component_template import ComponentTemplate
from prototypyside.models.layout_template import LayoutTemplate
from prototypyside.views.tabs.component_tab import ComponentTab
from prototypyside.views.tabs.layout_tab import LayoutTab



class MainDesignerWindow(QMainWindow):
    logical_disp_change = Signal()
    send_unit_changed = Signal(str)

    def __init__(self, init_tabs=None, is_headless=False):
        super().__init__()
        screen = self.screen()
        # Validation temporarily disabled pending schema updates
        self.settings = AppSettings()
        self.settings.dpi_changed.connect(self.on_dpi_changed)
        self.settings.unit_changed.connect(self.on_unit_changed)
        self.registry = RootRegistry(root=None, settings=self.settings)
        self.export_registry = ProtoRegistry(root=self.registry, settings=self.settings, parent=self.registry)
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

        self._is_headless = is_headless

        # Autosave every 5 minutes (300 000 ms):
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(5 * 60 * 1000)
        self._autosave_timer.timeout.connect(self._auto_save_current_tab)
        self._autosave_timer.start()

        self.setup_ui()
        self.setup_status_bar()
        self.setup_actions_and_menus()

        self.on_unit_changed(self.settings.unit)
        if not init_tabs:
            # Initialize with new tabs
            self.add_new_tab(ProtoClass.LT)
            self.add_new_tab(ProtoClass.CT)

        if init_tabs:
            self.open_template_batch(init_tabs)


    ### --- GUI Setup --- ###
    def setup_ui(self):
        tabs = QTabWidget()
        tab_bar = QTabBar()

        # connect to update your model (e.g. ComponentTemplate.name) too:
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabBar(tab_bar)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        self.setCentralWidget(self.tab_widget)
        self._create_import_panel()
        self.setup_dock_widgets()

    def _create_import_panel(self) -> QWidget:
        self.import_panel = ImportPanel(self.merge_manager)

    def setup_dock_widgets(self):
        # Creation methods are in their respective tab class
        # switching tabs switches which defs are used.

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
        self.addDockWidget(Qt.LeftDockWidgetArea, self.layers_dock)

        # Pretend the toolbar dock is a simple toolbar at the window level.
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
        if self.is_headless: # Use self.cli_mode
            return
        self.status_label.setStyleSheet("color: black;")
        self.status_label.setText("")

    def setup_actions_and_menus(self):
        # 1. File Menu
        file_menu = self.menuBar().addMenu("&File")

        new_ctab_action = file_menu.addAction("&New Component Tab")
        new_ctab_action.triggered.connect(lambda: self.add_new_tab(ProtoClass.CT))

        new_ltab_action = file_menu.addAction("New &Layout Tab")
        new_ltab_action.triggered.connect(lambda: self.add_new_tab(ProtoClass.LT))

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
        self.export_png_action.triggered.connect(self.export_from_type)

        self.export_pdf_action = file_menu.addAction("&Export Current Tab as PDF...")
        self.export_pdf_action.triggered.connect(self.export_from_type)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("E&xit")
        exit_action.triggered.connect(self.close)

        # --- Edit Menu ---
        edit_menu = self.menuBar().addMenu("&Edit")

        # 1) Undo/Redo
        # QAction already has standard shortcuts for these,
        # you just need to create them and connect the slots.
        undo_act = QAction("&Undo", self)
        undo_act.setShortcuts(QKeySequence.StandardKey.Undo)
        undo_act.triggered.connect(self.undo_group.undo)

        redo_act = QAction("&Redo", self)
        redo_act.setShortcuts(QKeySequence.StandardKey.Redo)
        redo_act.triggered.connect(self.undo_group.redo)

        # Key and PKeySequences offer Platform dependent QKeySequence aliasing
        # eg. PKeySequence(mac=Key.Cmd|Key.Delete, other=Key.Meta|Key.Backspace)
        add_item_act = QAction("Add Item", self)
        add_item_act.setShortcut(PKeySequence.AddItem)
        add_item_act.triggered.connect(self.add_item_to_current)

        remove_item_act = QAction("Delete Item", self)
        remove_item_act.setShortcuts(PKeySequence.RemoveItem)
        remove_item_act.triggered.connect(self.remove_item_from_current)

        # # 2) Copy/Cut/Paste using QAction.StandardShortcut
        # copy_act = QAction(QKeySequence.StandardKey.Copy, self)
        # copy_act.triggered.connect(self.on_copy)

        # cut_act = QAction(QKeySequence.StandardKey.Cut, self)
        # cut_act.triggered.connect(self.on_cut)

        # paste_act = QAction(QKeySequence.StandardKey.Paste, self)
        # paste_act.triggered.connect(self.on_paste)

        # Add actions to the Edit Menu
        edit_menu.addActions([undo_act, redo_act])
        edit_menu.addSeparator()
        # edit_menu.addActions([copy_act, cut_act, paste_act])
        # edit_menu.addSeparator()
        edit_menu.addActions([add_item_act, remove_item_act])

        # All actions added to the menu bar are automatically
        # assigned a shortcut context of Qt.WindowShortcut by default.
        # It's a good practice to explicitly set the context to Qt.ApplicationShortcut
        # for global actions that should always fire.
        actions = [
            undo_act, redo_act,
            # copy_act, cut_act, paste_act,
            add_item_act, remove_item_act
        ]
        self.addActions(actions)
        for act in actions:
            act.setShortcutContext(Qt.ApplicationShortcut)

    @property
    def tabs(self):
        all_tabs = []
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            all_tabs.append(widget)

        return all_tabs

    def update_menu_states(self, index):
        current_tab = self.tab_widget.widget(index)
        self.import_data_action.setEnabled(isinstance(current_tab, ComponentTemplate))

    # ––—— Current Tab  ———— #
    @Slot()
    def add_item_to_current(self):
        pass
        self.current_tab.add_item_from_action()

    @Slot()
    def remove_item_from_current(self):
        self.current_tab.remove_selected_item()

    # ———— Tab Handling ———— #
    def _auto_save_current_tab(self):
        pass
        # tab = self.current_tab
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
        CTAB = ComponentTab
        LTAB = LayoutTab
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

        if isinstance(active_tab, CTAB):
            # Show all docks used by ProtoClass.CTAB
            self.toolbar_dock.show()
            self.palette_dock.show()
            self.properties_dock.show()
            self.layers_dock.show()
            # Place ProtoClass.CTAB's widgets into the main window docks
            self.toolbar_dock.setWidget(active_tab.toolbar) #
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

        elif isinstance(active_tab, LTAB):
            # Show all docks used by ProtoClass.LTAB (note: no layers dock)
            self.toolbar_dock.show()
            self.palette_dock.show()
            self.properties_dock.show()
            self.layers_dock.hide() # ProtoClass.LTAB does not use the layers list

            # Place ProtoClass.LTAB's widgets into the main window docks
            self.toolbar_dock.setWidget(active_tab.layout_toolbar)

            palette_container = QWidget()
            palette_layout = QVBoxLayout(palette_container)
            palette_layout.setContentsMargins(0, 0, 0, 0)
            palette_layout.addWidget(active_tab.layout_palette)
            palette_layout.addWidget(self.import_panel)
            palette_layout.addStretch(1)
            self.palette_dock.setWidget(palette_container)

            # The property panel for ProtoClass.LTAB has its own unique combination of widgets
            prop_container = QWidget()
            prop_layout = QVBoxLayout(prop_container)
            prop_layout.setContentsMargins(0, 0, 0, 0)
            prop_layout.addWidget(active_tab.property_panel)
            # prop_layout.addWidget(active_tab.margin_spacing_panel)
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
            tab.dpi = new_dpi
            tab.template.dpi = new_dpi
            tab.scene.dpi = new_dpi
            self.on_unit_change(self.settings.unit)

    @Slot(str)
    def on_unit_changed(self, new_unit):
        unit_str_field_like = find_unit_str_like_fields(self, max_depth=4)
        unit = self.settings.unit
        # for item in unit_str_field_like:
        #     item.setUnit(new_unit)
        #     item.setDpi(self.settings.dpi)

    @Slot(int, str)
    def on_tab_title_changed(self, index, new_name: str):
        sender_tab = self.get_tab_at_index(index)
        template = sender_tab.template

    @property
    def current_tab(self):
        tw = getattr(self, "tab_widget")
        return tw.currentWidget() if isinstance(tw, QTabWidget) else None

    def get_tab_at_index(self, index):
        tab_widget = getattr(self, "tab_widget")
        return self.tab_widget.widget(index) if isinstance(tab_widget, QTabWidget) else None           

    # ————— Template File ———— #
    @Slot()
    def on_save_template(self):
        tab = self.current_tab
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
    def open_template_dialog(self):
        if self.is_headless:
            raise RuntimeError("Dialog not available in headless mode.")
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Open Template…", "", "JSON Files (*.json)"
        )
        return Path(path_str)

    def open_templates(self, tpaths: List[Path]):
        templates = []
        for p in tpaths:
            obj = self.open_template(Path(path))
            if self.is_headless:
                templates.append(templates)
        return templates

    def open_template(self, path: Path | str = None, *_):
        """
        Load a template JSON at 'path' and either open it in a new tab (GUI)
        or return the hydrated object (headless).
        """
        if not path and not self.is_headless:
            path = self.open_template_dialog()
        else:
            raise ValueError("At least one template must be opened")
        path = Path(path) if path else None
        if not path.exists():
            raise FileNotFoundError(str(path))

        data = json.load(path.open(mode='r', encoding='utf-8'))
        registry, obj = self.registry(load_with_template(data))

        csvp = hasattr(obj, "csv_path") and getattr(obj, "csv_path", None)
        if csvp:
            self.merge_manager.load_csv(str(csvp), template=obj)
        if self.is_headless:
            return obj
        else:
            self._new_tab(obj, new_template=False)

    @Slot(object)
    def add_new_tab(self, proto):
        """
        Create the appropriate tab for a ComponentTemplate or LayoutTemplate,
        select it, and set the tab label.
        """
        registry, obj = self.registry.new_with_template(proto)
        print(f"registry of type{type(registry)} obj of type: {type(obj)} with name: {obj.name}")

        if isinstance(obj, ComponentTemplate):
            new_tab = ComponentTab(parent=self, main_window=self, registry=registry, template=obj)
        elif isinstance(obj, LayoutTemplate):
            new_tab = LayoutTab(main_window=self, registry=registry, template=obj, parent=self)
            new_tab.scene.addItem(obj)
            # Layout template is added to the scene upon intiializing the new tab.
            # rows, cols = obj.rows, obj.columns
            # setGrid is ony called explicitly outside of cloning and rehydration after creation.
            # obj.setGrid(registry, rows=rows, columns=cols)
            obj.updateGrid()
            # # new_tab.set_template(obj)
            # new_tab.scene.update()

            # print(f"Slots added to the scene {[bool(item.scene()) for item in obj.items]}")
        # else:
        #     raise TypeError(f"Invalid Tab type {type(obj)}; expected {CT_cls.__name__} or {LT_cls.__name__}")

        self.undo_group.addStack(new_tab.undo_stack)
        # Connect the tab's status message signal to the main window's item
        new_tab.status_message_signal.connect(self.show_status_message)
        #new_tab.tab_title_changed.connect(self.on_tab_title_changed)
        index = self.tab_widget.addTab(new_tab, obj.name)
        self.tab_widget.setCurrentIndex(index)
        self.show_status_message("New template tab created.", "info")

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

        if tab_to_close:
            template_pid = tab_to_close.template.pid
            self.remove_template_from_all_tabs(template_pid)
            template = tab_to_close.template
            scene = tab_to_close.scene
            if template in scene.items():  # or however your scene stores items
                scene.removeItem(template)
            tab_to_close.undo_stack.clear()
            tab_to_close.deleteLater()
            gc.collect()      
            self.registry.remove_child(registry)

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
        tab = self.current_tab
        if not tab:
            return
        path = getattr(tab.template, "file_path", None)
        if path is None:
            self.save_as_template()
            return

        self.write_template_to_path(tab.template, tab.registry, path)
        self.show_status_message(f"Saved to {path}", "success")

        idx = self.tab_widget.indexOf(tab)
        self.tab_widget.setTabText(idx, Path(path).stem)

    @Slot()
    def save_as_template(self):
        tab = self.current_tab
        if not tab:
            return

        template = tab.template
        old_name = template.name

        path_str, _ = QFileDialog.getSaveFileName(self, "Save Template As", "", "JSON Files (*.json)")
        if not path_str:
            self.show_status_message("Save cancelled", "info")
            return

        self.write_template_to_path(template, tab.registry, path_str)
        template.file_path = Path(path_str)  # store as Path

        self.show_status_message(f"Saved to {path_str}", "success")
        idx = self.tab_widget.indexOf(tab)
        new_name = Path(path_str).stem
        tab.on_property_changed(template, "name", new_name, old_name)
        self.tab_widget.setTabText(idx, new_name)

    def write_template_to_path(self, template, registry, path):
        p = Path(path)  # accept str|Path
        data = registry.to_dict(template)

        saver = QSaveFile(str(p), self)
        if not saver.open(QIODevice.WriteOnly | QIODevice.Text):
            raise IOError(f"Cannot open {p} for writing")

        saver.write(json.dumps(data, indent=2).encode("utf-8"))
        if not saver.commit():
            raise IOError(f"Could not commit save to {p}")

    @Slot()
    def save_current_tab_template(self):
        current_tab = self.current_tab
        current_template = current_tab.template
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
        pass
        # cb   = QGuiApplication.clipboard()
        # md   = cb.mimeData()
        # # 1) custom python-object clone
        # clone = self.registry.paste_from_mime_data(md)
        # if clone:
        #     self.scene.addItem(clone)
        #     return

        # # 2) image data
        # if md.hasImage():
        #     img = md.imageData()  # a QImage
        #     pix = QPixmap.fromImage(img)
        #     # if an ImageElement is already selected, update it…
        #     sel = self.scene.selectedItems()
        #     if sel and hasattr(sel[0], "setPixmap"):
        #         sel[0].setPixmap(pix)
        #     else:
        #         proto = ProtoClass.IE
        #         # otherwise, create a brand-new ImageElement via registry
        #         new_img_elem = self.registry.create(proto, pixmap=pix)
        #         self.scene.addItem(new_img_elem)
        #     return

        # # 3) plain text
        # if md.hasText():
        #     txt = md.text()
        #     # if the focus is in a QLineEdit, let it paste normally
        #     fw = QApplication.focusWidget()
        #     if isinstance(fw, QLineEdit):
        #         fw.insert(txt)
        #     else:
        #         # or inject into a selected TextElement
        #         sel = self.scene.selectedItems()
        #         if sel and hasattr(sel[0], "setText"):
        #             sel[0].setText(txt)
        #         else:
        #             # or build a new TextElement
        #             proto = ProtoClass.TE
        #             new_te = self.registry.create(proto, content=txt)
        #             self.scene.addItem(new_te)
        #     return

        # # 4) fallback: do nothing or show “nothing to paste”
        # self.statusBar().showMessage("Nothing to paste", 2000)

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
        data = self.merge_manager.load_csv(csv_path, active_tab.template)
        self.import_panel.set_template(active_tab.template)

        # safe debug
        if data:
            self.import_panel.update_for_template(active_tab.template)
        else:
            print("[IMPORT] No CSVData returned")
     
    @Slot()
    def export_from_type(self):
        active_tab = self.tab_widget.currentWidget()
        template = active_tab.template
        em = ExportManager(self.settings, active_tab.registry, self.merge_manager)
        if isinstance(active_tab, ComponentTab):
            folder = QFileDialog.getExistingDirectory(
                self, 
                "Select Export Directory", 
                str(Path.resolve())
            )
            if not folder:
                print("ComponentTemplate export requires a directory")
                return

            em.export_component_to_png(template, folder)
            print(f"[EXPORT COMPLETED] Components exported to {folder}")

        if isinstance(active_tab, LayoutTab):
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
            em.export_with_vector_text_to_pdf(template, output_path)

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

    def cli_init_tabs():
        self.new_tab(ProtoClass.CTAB, "ct")
        self.new_tab(ProtoClass.LTAB, "lt")

    # HEADLESS FLAG
    # -------------
    # Use .is_headless in new code; .is_healdesss remains as a misspelling alias for backward compatibility.
    @property
    def is_headless(self) -> bool:
        return getattr(self, "_is_headless", False)

    @is_headless.setter
    def is_headless(self, value: bool) -> None:
        self._is_headless = bool(value)


    # TYPE CHECKS
    # -----------
    def _is_component_template(self, obj) -> bool:
        if _CT is not None and isinstance(obj, _CT):
            return True
        # structural fallback
        return hasattr(obj, "elements")

    def _is_layout_template(self, obj) -> bool:
        if _LT is not None and isinstance(obj, _LT):
            return True
        # structural fallback
        return hasattr(obj, "slots")


    def _cli_open_template(self, path: Path):
        path = Path(path)
        if path.exists():
            data
            registry, template = self.registry.init_child()
        
    # EXPORTS
    # -------
    def cli_export_to_png(self, ct_obj, export_dir: str | Path) -> None:
        """Headless component export (PNG)."""
        if not self._is_component_template(ct_obj):
            raise TypeError("cli_export_to_png requires a ComponentTemplate")
        out_dir = Path(export_dir).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        em = ProtoClass.EM(settings=self.settings,
                           registry=self.export_registry,
                           merge_manager=self.merge_manager)
        em.export_component_to_png(ct_obj, str(out_dir))

    def cli_export_to_pdf(self, lt_obj, pdf_path: str | Path) -> None:
        """Headless layout export (PDF with vector text)."""
        if not self._is_layout_template(lt_obj):
            raise TypeError("cli_export_to_pdf requires a LayoutTemplate")
        out_path = Path(pdf_path).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        em = ProtoClass.EM(settings=self.settings,
                           registry=self.export_registry,
                           merge_manager=self.merge_manager,
                           dpi=600)
        em.export_with_vector_text_to_pdf(lt_obj, str(out_path))

    # HELPERS
    # -----------------------------------------------        
    def cli_set_include_bleed(self, ct_obj, include: bool) -> None:
        """Enable/disable bleed on a ComponentTemplate for headless runs."""
        if not self._is_component_template(ct_obj):
            raise TypeError("cli_set_include_bleed requires a ComponentTemplate")
        try:
            ct_obj.include_bleed = bool(include)
        except Exception:
            pass  # tolerate models without this property

    def cli_slot_references(self, lt_obj) -> list[tuple[str | None, Path | None]]:
        """
        Return (tpid, file_path) for each slot.content||template, used to lazily open missing CTs.
        Works with attribute or dict-like objects.
        """
        if not self._is_layout_template(lt_obj):
            raise TypeError("cli_slot_references requires a LayoutTemplate")
        refs: list[tuple[str | None, Path | None]] = []
        slots = getattr(lt_obj, "slots", None) or []
        for s in slots:
            content = getattr(s, "content", None) or getattr(s, "template", None) or {}
            tpid = getattr(content, "tpid", None) or getattr(content, "pid", None) or (content.get("tpid") if isinstance(content, dict) else None) or (content.get("pid") if isinstance(content, dict) else None)
            fp = getattr(content, "file_path", None) or (content.get("file_path") if isinstance(content, dict) else None)
            refs.append((tpid, Path(fp) if fp else None))
        return refs
