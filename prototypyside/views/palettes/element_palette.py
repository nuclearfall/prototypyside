from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QListWidget, QListWidgetItem
)


class ElementPalette(QListWidget):
    element_type_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__()

        # Drag-enabled list
        self.setDragEnabled(True)
        self.itemClicked.connect(self._on_item_clicked)
        # layout.addWidget(self)

        # Populate list
        self.add_component_item("Text Field", "te", "T")
        self.add_component_item("Image Container", "ie", "🖼️")

    def add_component_item(self, label: str, prefix: str, icon: str = ""):
        item = QListWidgetItem(f"{icon} {label}")
        item.setData(Qt.UserRole, prefix)
        self.addItem(item)

    def on_element_type_selected(self, prefix: str):
        print(f"We've selected {prefix}")
        self._pending_element_prefix = prefix
        self.status_message_signal.emit(f"Selected element prefix: {prefix}", "info", 3000)

        if hasattr(self.scene, "set_tool_mode"):
            self.scene.set_tool_mode(prefix)

    def _on_item_clicked(self, item: QListWidgetItem):
        print("Has an Item been clicked?")
        etype = item.data(Qt.UserRole)
        print("Anything?", etype)
        self.on_element_type_selected.emit(etype)

    def startDrag(self):
        item = self.currentItem()
        if not item:
            return

        mime_data = QMimeData()
        prefix = item.data(Qt.UserRole)
        print(f"We've started dragging of prefix mime data: {prefix}")

        if prefix:
            f"We've started dragging of prefix mime data: {prefix}"
            mime_data.setText(item.data(Qt.UserRole))

        drag = QDrag(self)
        drag.setMimeData(mime_data)
        print(mime_data)
        drag.exec(Qt.CopyAction)

    def mouseMoveEvent(self, event: QMouseEvent):
        # Start drag on move
        if event.buttons() & Qt.LeftButton:
            self.startDrag()

