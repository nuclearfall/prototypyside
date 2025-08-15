from PySide6.QtCore import Qt, Signal, QMimeData, Slot, QPoint
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QApplication


class ElementPalette(QListWidget):
    on_item_type_selected = Signal(str)

    def __init__(self, parent=None, tab=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setSelectionMode(QListWidget.SingleSelection)

        self._pending_item_prefix: str | None = None
        self._press_pos: QPoint | None = None
        self._dragging: bool = False

        # IMPORTANT: do NOT connect itemClicked to the signal (would double-emit).
        # If you want extra UI reactions on click, connect to _on_item_clicked instead:
        # self.itemClicked.connect(self._on_item_clicked)

    @Slot()
    def clear_active_selection(self):
        """Called by the Scene when it cancels armed creation."""
        self.clearSelection()
        self.setCurrentItem(None)

    def add_item(self, label: str, prefix: str, icon: str = ""):
        item = QListWidgetItem(f"{icon} {label}" if icon else label)
        item.setData(Qt.UserRole, prefix)
        self.addItem(item)

    # Optional: if you want a UI reaction on click without emitting again
    def _on_item_clicked(self, item: QListWidgetItem):
        prefix = item.data(Qt.UserRole)
        self._pending_item_prefix = prefix
        # Intentionally NOT emitting here to avoid duplicate arm events.
        # print(f"[Palette] Item clicked (no emit) prefix={prefix}")

    def _emit_prefix(self, prefix: str):
        self._pending_item_prefix = prefix
        # print(f"[Palette] Emitting on_item_type_selected: {prefix}")
        self.on_item_type_selected.emit(prefix)

    def mousePressEvent(self, event: QMouseEvent):
        super().mousePressEvent(event)  # lets QListWidget update selection first

        item = self.currentItem()
        if not item:
            self._press_pos = None
            self._dragging = False
            return

        prefix = item.data(Qt.UserRole)
        self._press_pos = event.pos()
        self._dragging = False

        if prefix:
            # Arm the scene immediately on press (click-to-create flow).
            self._emit_prefix(prefix)

    def mouseMoveEvent(self, event: QMouseEvent):
        # If left button down and we moved far enough, start a drag
        if (event.buttons() & Qt.LeftButton) and self._press_pos is not None:
            if not self._dragging:
                dist = (event.pos() - self._press_pos).manhattanLength()
                if dist >= QApplication.startDragDistance():
                    self._dragging = True
                    self.startDrag()
                    return
        # Otherwise, default behavior
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._press_pos = None
        self._dragging = False
        super().mouseReleaseEvent(event)

    def startDrag(self, supportedActions=Qt.CopyAction):
        item = self.currentItem()
        if not item:
            return

        prefix = item.data(Qt.UserRole)
        if not prefix:
            return

        mime_data = QMimeData()
        mime_data.setText(prefix)
        # print(f"[Palette] Dragging prefix: {prefix}")

        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(supportedActions)
