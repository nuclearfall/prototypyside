# prototypyside/views/main_window.py

import sys
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
import gc
from PySide6.QtWidgets import (QMainWindow, QDockWidget, QTabWidget, QWidget, QStackedWidget,
                               QVBoxLayout, QLabel, QFileDialog, QMessageBox,
                               QToolBar, QPushButton, QHBoxLayout, QSizePolicy, QCheckBox, QTabBar) # Added QPushButton, QHBoxLayout for temporary property panel layout
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QStandardPaths, QSaveFile, QIODevice
from PySide6.QtGui import QIcon, QAction, QKeySequence, QShortcut, QUndoStack, QUndoGroup, QUndoCommand, QPainter



from prototypyside.services.app_settings import AppSettings
from prototypyside.services.proto_registry import ProtoRegistry, RootRegistry
from prototypyside.utils.pkey_sequence import PKeySequence, Key
from prototypyside.utils.valid_path import ValidPath
 
from prototypyside.services.merge_manager import MergeManager
from prototypyside.views.panels.import_panel import ImportPanel
from prototypyside.services.export_manager import ExportManager

from prototypyside.utils.qt_helpers import find_unit_str_like_fields
from prototypyside.services.proto_class import ProtoClass
from prototypyside.models.component_template import ComponentTemplate
from prototypyside.models.layout_template import LayoutTemplate
from prototypyside.views.tabs.component_tab import ComponentTab
from prototypyside.views.tabs.layout_tab import LayoutTab

pc = ProtoClass

class MainDesignerWindow(QMainWindow):
    logical_disp_change = Signal()
    send_unit_changed = Signal(str)
    template_name_changed = Signal(str)

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
        self.merge_manager = MergeManager()

        self._is_headless = is_headless

        # Autosave every 5 minutes (300 000 ms):
        # self._autosave_timer = QTimer(self)
        # self._autosave_timer.setInterval(5 * 60 * 1000)
        # self._autosave_timer.timeout.connect(self._auto_save_current_tab)
        # self._autosave_timer.start()

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

    # in MainWindow.__init__
    def setup_dock_widgets(self):
        # Create one set of docks for the whole window
        self.toolbar_dock = QDockWidget("Toolbar", self)
        self.left_dock    = QDockWidget("Palette", self)
        self.right_dock   = QDockWidget("Properties", self)

        # Pretend the toolbar dock is a window-level toolbar
        self.toolbar_dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.toolbar_dock.setTitleBarWidget(QWidget())

        # Each dock contains a stack; we’ll switch pages per-tab
        self.toolbar_stack = QStackedWidget()
        self.left_stack    = QStackedWidget()
        self.right_stack   = QStackedWidget()
        for dock in [self.left_dock, self.right_dock]:
            dock.setMaximumWidth(300)

        # Add an empty fallback page so docks aren’t blank on startup
        self._empty_toolbar = QWidget()
        self._empty_left    = QWidget()
        self._empty_right   = QWidget()
        self.toolbar_stack.addWidget(self._empty_toolbar)
        self.left_stack.addWidget(self._empty_left)
        self.right_stack.addWidget(self._empty_right)

        self.toolbar_dock.setWidget(self.toolbar_stack)
        self.left_dock.setWidget(self.left_stack)
        self.right_dock.setWidget(self.right_stack)

        self.addDockWidget(Qt.TopDockWidgetArea, self.toolbar_dock)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.left_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.right_dock)

        # when tabs change, swap the visible pages
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

    def on_tab_changed(self, index: int):
        tab = self.tab_widget.widget(index)
        if not tab:
            # show fallbacks
            self.toolbar_stack.setCurrentWidget(self._empty_toolbar)
            self.left_stack.setCurrentWidget(self._empty_left)
            self.right_stack.setCurrentWidget(self._empty_right)
            return
        self.disable_export_by_tab_type(index)
        # assume each tab provides these attrs
        self.toolbar_stack.setCurrentWidget(getattr(tab, "toolbar", self._empty_toolbar))
        self.left_stack.setCurrentWidget(getattr(tab, "left_dock", self._empty_left))
        self.right_stack.setCurrentWidget(getattr(tab, "right_dock", self._empty_right))

    def disable_export_by_tab_type(self, index):
        tab = self.tab_widget.widget(index)
        if not tab:
            return

        if pc.isproto(tab, pc.LTAB):
            # In LayoutTab → allow PDF, disallow PNG
            self.export_pdf_action.setEnabled(True)
            self.export_png_action.setEnabled(False)
        else:
            # In ComponentTab (or others) → allow PNG, disallow PDF
            self.export_pdf_action.setEnabled(False)
            self.export_png_action.setEnabled(True)

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
        self.export_png_action.triggered.connect(self.export_to_png)

        self.export_pdf_action = file_menu.addAction("&Export Current Tab as PDF...")
        self.export_pdf_action.triggered.connect(self.export_to_pdf)

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
        self.import_data_action.setEnabled(pc.isproto(current_tab, pc.CTAB))

    # ––—— Current Tab  ———— #
    @Slot()
    def add_item_to_current(self):
        pass
        self.current_tab.add_item_from_action()

    @Slot()
    def remove_item_from_current(self):
        self.current_tab.remove_selected_item()

    # ———— Tab Handling ———— #
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
        name = Path(path).stem
        template.name = name
        for tab in self.tabs:
            tab.tab_title_changed.emit(name)
        self.tab_widget.setTabText(self.tab_widget.currentIndex(), name)

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
        registry, obj = self.registry.load_with_template(data)

        csvp = hasattr(obj, "csv_path") and getattr(obj, "csv_path", None)
        if csvp:
            self.merge_manager.load_csv(str(csvp), template=obj)
        if self.is_headless:
            return obj
        else:
            self.add_new_tab(obj, loaded=[registry, obj])

    @Slot(object)
    def add_new_tab(self, proto, loaded=None):
        if not loaded:
            registry, obj = self.registry.new_with_template(proto)
        else:
            registry, obj = loaded

        if pc.isproto(obj, pc.CT):
            new_tab = ComponentTab(parent=self, main_window=self, registry=registry, template=obj)
        elif pc.isproto(obj, pc.LT):
            new_tab = LayoutTab(main_window=self, registry=registry, template=obj, parent=self)
            new_tab.scene.addItem(obj)
            obj.updateGrid()
        print(f"Template dimensions for {obj.pid} are {obj.geometry.px.rect}")
        # Register the tab’s widgets in the stacks exactly once
        # Tab must expose .toolbar, .left_dock, .right_dock (plain QWidget)
        if getattr(new_tab, "toolbar", None):
            if new_tab.toolbar.parent() is not None:
                new_tab.toolbar.setParent(None)
            self.toolbar_stack.addWidget(new_tab.toolbar)

        if getattr(new_tab, "left_dock", None):
            if new_tab.left_dock.parent() is not None:
                new_tab.left_dock.setParent(None)
            self.left_stack.addWidget(new_tab.left_dock)

        if getattr(new_tab, "right_dock", None):
            if new_tab.right_dock.parent() is not None:
                new_tab.right_dock.setParent(None)
            self.right_stack.addWidget(new_tab.right_dock)

        self.undo_group.addStack(new_tab.undo_stack)
        new_tab.status_message_signal.connect(self.show_status_message)

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

        csv_path = ValidPath.file(dialog.selectedFiles()[0], must_exist=True)
        tmpl = active_tab.template
        self.merge_manager.add_path(csv_path, pid=tmpl.pid)
        self.import_panel.set_template(active_tab.template)
     
    @Slot()
    def export_to_png(self):
        active_tab = self.tab_widget.currentWidget()
        template = active_tab.template
        em = ExportManager(self.settings, active_tab.registry, self.merge_manager)
        if pc.isproto(active_tab, pc.CTAB):
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

    @Slot()
    def export_to_pdf(self):
        active_tab = self.tab_widget.currentWidget()
        template = active_tab.template
        em = ExportManager(self.settings, self.merge_manager)
        if pc.isproto(active_tab, pc.LTAB):
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
            em.export_pdf(template, output_path)

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
        if _CT is not None and pc.isproto(obj, pc.CT):
            return True
        # structural fallback
        return hasattr(obj, "elements")

    def _is_layout_template(self, obj) -> bool:
        if _LT is not None and pc.isproto(obj, pc.LT):
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
