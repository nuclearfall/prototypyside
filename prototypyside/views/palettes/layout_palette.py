# layout_palette.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel
from PySide6.QtCore import Qt, QMimeData, QEvent, QPoint, Signal
from PySide6.QtGui import QDrag, QMouseEvent

from prototypyside.utils.proto_helpers import get_prefix
class LayoutPalette(QWidget):
    """
    Palette showing all open component templates available for layout assignment.
    """
    palette_selection_changed = Signal(str)
    palette_deselected = Signal()

    def __init__(self, registry, parent=None):
        super().__init__(parent)
        # registry is the global registry
        self.registry = registry
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.label = QLabel("Component Templates", self)
        self.list_widget = DraggableListWidget(self, registry)
        self.list_widget.setDragEnabled(True)        
        self.setMinimumHeight(20)
        self.setMinimumWidth(100) 
        layout.addWidget(self.label)
        layout.addWidget(self.list_widget)
        layout.addStretch(1)
        self.list_widget.itemClicked.connect(self._on_list_item_clicked)
        # Connect signals
        self.registry.object_registered.connect(self._on_component_registered)
        self.registry.object_deregistered.connect(self._on_component_deregistered)

        self.refresh()

    def refresh(self):
        """(Re)populate the list with all open component templates."""
        self.list_widget.clear()
        existing_components = self.registry.get_global_by_type("ct")
        for obj in existing_components:
            self._add_component_item(obj)

    def _on_list_item_clicked(self):
        item = self.list_widget.currentItem()
        self.palette_selection_changed.emit(item.data(Qt.UserRole))


    def _add_component_item(self, obj):
        item = QListWidgetItem(obj.name)
        item.setData(Qt.ItemDataRole.UserRole, obj.pid)
        self.list_widget.addItem(item)

    def _on_component_registered(self, obj):
        if get_prefix(obj.pid) == "ct":
            # Avoid duplicates: only add if not already present
            for i in range(self.list_widget.count()):
                if self.list_widget.item(i).data(Qt.UserRole) == obj.pid:
                    return
            self._add_component_item(obj)

    def _on_component_deregistered(self, obj_to_remove):
        if get_prefix(obj_to_remove.pid) == "ct":
            pid_to_remove = obj_to_remove.pid
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                if item.data(Qt.UserRole) == pid_to_remove:
                    removed_item = self.list_widget.takeItem(i)
                    print(f"LayoutPalette: Removed item for PID: {pid_to_remove}, '{removed_item.text()}', from list.")
                    return

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