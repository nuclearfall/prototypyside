from PySide6.QtWidgets import (
    QWidget, QToolBar, QFontComboBox, QComboBox, QToolButton, QHBoxLayout,
    QApplication
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Signal, Slot


class FontToolbar(QWidget):
    font_changed = Signal(QFont)
    # property_changed = Signal(QFont)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.font_combo = QFontComboBox()
        self.size_combo = QComboBox()
        self.bold_btn = QToolButton()
        self.italic_btn = QToolButton()
        self.underline_btn = QToolButton()

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        # Set up size combo box
        for size in range(8, 31, 2):
            self.size_combo.addItem(str(size))
        self.size_combo.setEditable(True)

        # Set up buttons
        self.bold_btn.setText("B")
        self.bold_btn.setCheckable(True)
        self.bold_btn.setToolTip("Bold")

        self.italic_btn.setText("I")
        self.italic_btn.setCheckable(True)
        self.italic_btn.setToolTip("Italic")

        self.underline_btn.setText("U")
        self.underline_btn.setCheckable(True)
        self.underline_btn.setToolTip("Underline")

        # Layout
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.font_combo)
        layout.addWidget(self.size_combo)
        layout.addWidget(self.bold_btn)
        layout.addWidget(self.italic_btn)
        layout.addWidget(self.underline_btn)
        self.setLayout(layout)

    def _connect_signals(self):
        self.font_combo.currentFontChanged.connect(self.emit_font)
        self.size_combo.currentIndexChanged.connect(self.emit_font)
        self.size_combo.editTextChanged.connect(self.emit_font)
        self.bold_btn.toggled.connect(self.emit_font)
        self.italic_btn.toggled.connect(self.emit_font)
        self.underline_btn.toggled.connect(self.emit_font)

    @Slot()
    def emit_font(self):
        family = self.font_combo.currentFont().family()
        try:
            size = int(self.size_combo.currentText())
        except ValueError:
            size = 12  # fallback size
        font = QFont(family, size)
        font.setBold(self.bold_btn.isChecked())
        font.setItalic(self.italic_btn.isChecked())
        font.setUnderline(self.underline_btn.isChecked())
        self.font_changed.emit(font)

    def set_font(self, font: QFont):
        self.font_combo.setCurrentFont(font)
        self.size_combo.setCurrentText(str(font.pointSize()))
        self.bold_btn.setChecked(font.bold())
        self.italic_btn.setChecked(font.italic())
        self.underline_btn.setChecked(font.underline())
