from PySide6.QtWidgets import QTabWidget, QTabBar, QLineEdit
from PySide6.QtCore import QRect, Qt, Signal

class EditableTabBar(QTabBar):
    nameChanged = Signal(int, str)  # index, new name

    def mouseDoubleClickEvent(self, event):
        idx = self.tabAt(event.pos())
        if idx < 0:
            return super().mouseDoubleClickEvent(event)

        # get the rectangle of the tab we clicked
        rect: QRect = self.tabRect(idx)
        print(f"Tab Rect is {rect}")
        # create an editor on top of the tab
        le = QLineEdit(self)
        le.setText(self.tabText(idx))
        le.setFrame(False)
        le.setGeometry(rect.adjusted(24, 2, -10, -2))
        le.selectAll()
        le.show()        # <— make it visible!
        le.raise_()      # <— ensure it’s on top
        le.setFocus(Qt.MouseFocusReason)

        def finish_edit():
            new_text = le.text().strip() or self.tabText(idx)
            self.setTabText(idx, new_text)
            self.nameChanged.emit(idx, new_text)
            le.deleteLater()

        # commit on enter or focus out
        le.editingFinished.connect(finish_edit)

    # ensure the rest of the behavior still works
    # (optional) you may want to forward clicks, drags, etc.
