from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QComboBox, QVBoxLayout, QLabel, QDialogButtonBox)

from prototypyside.config import PAGE_SIZES

class PageSizeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Page Size")
        layout = QVBoxLayout(self)

        self.label = QLabel("Choose a standard page size:")
        layout.addWidget(self.label)

        self.combo = QComboBox()
        self.combo.addItems(PAGE_SIZES.keys())
        layout.addWidget(self.combo)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def selected_page_size(self):
        key = self.combo.currentText()
        return key, PAGE_SIZES[key]