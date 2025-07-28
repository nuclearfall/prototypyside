# layout_palette.py
from shiboken6 import isValid
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem, QLabel
from PySide6.QtCore import Qt, QMimeData, QEvent, QPoint, Signal
from PySide6.QtGui import QDrag, QMouseEvent
from functools import partial

from prototypyside.utils.proto_helpers import get_prefix


class LayoutPalette(QWidget):
    """
    Palette showing all open component templates available for layout assignment.
    """
    palette_selection_changed = Signal(str)
    palette_deselected = Signal()
    select_template = Signal(str)
    remove_template = Signal(str)

    def __init__(self, root_registry, parent=None):
        super().__init__(parent)
        self.registry = root_registry
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.label = QLabel("Component Templates", self)
        self.list_widget = DraggableListWidget(self, self.registry)
        self.list_widget.setDragEnabled(True)
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        self.setMinimumHeight(20)
        self.setMinimumWidth(100) 
        layout.addWidget(self.label)
        layout.addWidget(self.list_widget)
        button_row = QHBoxLayout()
        self.select_btn = QPushButton("Select", self)
        self.remove_btn = QPushButton("Remove", self)
        button_row.addWidget(self.select_btn)
        button_row.addWidget(self.remove_btn)
        self.select_btn.clicked.connect(self._on_select_clicked)
        self.remove_btn.clicked.connect(self._on_remove_clicked)
        layout.addLayout(button_row)
        layout.addStretch(1)

        self.list_widget.itemClicked.connect(self._on_list_item_clicked)
        # Connect signals
        self.registry.object_registered.connect(self._on_component_registered)

        self.registry.object_deregistered.connect(self._on_component_deregistered)

        self.refresh()

    def refresh(self):
        # print("[LayoutPalette] Refreshing list of component templates")
        self.list_widget.clear()
        seen_pids = set()
        objects = self.registry.global_get_by_prefix("ct")
        # print(f"[LayoutPalette] Found {len(objects)} objects with prefix 'ct'")
        for obj in objects:
            if not isValid(obj):
                # print(f"[LayoutPalette] Object {obj.pid} is not valid (Qt object deleted?)")
                continue
            if obj.pid in seen_pids:
                # print(f"[LayoutPalette] Duplicate PID: {obj.pid}")
                continue
            seen_pids.add(obj.pid)
            # print(f"[LayoutPalette] Adding component: {obj.name} (PID: {obj.pid})")
            self._add_component_item(obj)

    def _on_list_item_clicked(self):
        item = self.list_widget.currentItem()
        self.palette_selection_changed.emit(item.data(Qt.UserRole))

    def _add_component_item(self, obj):
        item = QListWidgetItem(obj.name)
        item.setData(Qt.ItemDataRole.UserRole, obj.pid)  # <- store only PID
        self.list_widget.addItem(item)

        # Listen for changes on the template itself
        if hasattr(obj, "template_changed"):
            obj.template_changed.connect(partial(self._on_template_update, obj.pid))

        # Listen for element-level changes
        for el in getattr(obj, "items", []):
            if hasattr(el, "item_changed"):
                el.item_changed.connect(partial(self._on_template_update, obj.pid))

    def _on_component_registered(self, pid):
        if get_prefix(pid) == "ct":
            for i in range(self.list_widget.count()):
                if self.list_widget.item(i).data(Qt.UserRole) == pid:
                    return
            # print(f"Object pid is {pid}")
            obj = self.registry.global_get(pid)
            self._add_component_item(obj)

    def _on_component_deregistered(self, pid):
        if get_prefix(pid) == "ct":
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                if item.data(Qt.UserRole) == pid:
                    removed_item = self.list_widget.takeItem(i)
                    return

    def _on_template_update(self, pid):
        """Update palette entry when a template or one of its elements changes."""
        obj = self.registry.global_get(pid)
        if not obj or not isValid(obj):
            return

        for i in range(self.list_widget.count()):
            lw_item = self.list_widget.item(i)
            if lw_item.data(Qt.UserRole) == pid:
                lw_item.setText(obj.name)
                break

    def _on_select_clicked(self):
        """Emit select_template for the currently highlighted item."""
        item = self.list_widget.currentItem()
        if not item:
            return
        pid = item.data(Qt.UserRole)
        self.pid_lock = True
        self.select_btn.setEnabled(False)
        self.select_template.emit(pid)

    def _on_remove_clicked(self):
        """Emit remove_template for the currently highlighted item."""
        item = self.list_widget.currentItem()
        if not item:
            return
        pid = item.data(Qt.UserRole)
        self.select_btn.setEnabled(True)
        self.remove_template.emit(pid)

    def remove_template_by_pid(self, pid: str):
        """Remove the QListWidget item corresponding to the given component template PID."""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.UserRole) == pid:
                removed_item = self.list_widget.takeItem(i)
                del removed_item  # optional, but helps avoid lingering C++ object warnings
                return True
        return False  # not found


class DraggableListWidget(QListWidget):
    def __init__(self, parent=None, registry=None):
        super().__init__(parent)
        self.setMinimumHeight(20)
        self.setMinimumWidth(60)

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.LeftButton:
            current = self.currentItem()
            if not current:
                return

            pid = current.data(Qt.UserRole)
            if not pid:
                raise ValueError("List item has no valid pid.")

            mime_data = QMimeData()
            mime_data.setData("application/x-component-pid", pid.encode("utf-8"))

            drag = QDrag(self)
            drag.setMimeData(mime_data)
            drag.setHotSpot(QPoint(10, 10))
            drag.exec(Qt.CopyAction)
