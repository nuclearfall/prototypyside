# prototypyside/views/palettes.py

from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtWidgets import QListWidget, QListWidgetItem

class ComponentListWidget(QListWidget):
    palette_item_clicked = Signal(str)

    def startDrag(self, supportedActions: Qt.DropActions) -> None:
        item = self.currentItem()
        if not item:
            return

        mime_data = QMimeData()
        item_type = item.data(Qt.UserRole)
        if item_type:
            mime_data.setText(item_type)

        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(supportedActions)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        item = self.itemAt(event.position().toPoint())
        if item:
            self.setCurrentItem(item)
  
            prefix = item.data(Qt.UserRole)
            self.palette_item_clicked.emit(prefix)
        super().mousePressEvent(event)

    def remove_template_by_tpid(self, tpid):
        pass
