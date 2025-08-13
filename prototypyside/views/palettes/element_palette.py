from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtWidgets import QListWidget, QListWidgetItem


class ElementPalette(QListWidget):
    on_item_type_selected = Signal(str)

    def __init__(self, parent=None, tab=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.itemClicked.connect(self.on_item_clicked)
        self._pending_item_prefix = None

        # # Example items (you can remove or customize these)
        # self.add_item("Text Field", "te", "T")
        # self.add_item("Image Container", "ie", "🖼️")

    def add_item(self, label: str, prefix: str, icon: str = ""):
        item = QListWidgetItem(f"{icon} {label}")
        item.setData(Qt.UserRole, prefix)
        self.addItem(item)

    def on_item_clicked(self, item: QListWidgetItem):
        prefix = item.data(Qt.UserRole)
        self._pending_item_prefix = prefix
        print(f"Item clicked with prefix: {prefix}")
        self.on_item_type_selected.emit(prefix)

    def startDrag(self, supportedActions=Qt.CopyAction):
        item = self.currentItem()
        if not item:
            return

        mime_data = QMimeData()
        prefix = item.data(Qt.UserRole)

        if prefix:
            mime_data.setText(prefix)
            print(f"Dragging prefix: {prefix}")

        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(supportedActions)

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.LeftButton:
            self.startDrag()
        else:
            super().mouseMoveEvent(event)
