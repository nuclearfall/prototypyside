from PySide6.QtWidgets import (
    QWidget, QToolBar, QFontComboBox, QComboBox, QToolButton, QHBoxLayout,
    QApplication
)
from PySide6.QtGui import QFont, QIntValidator
from PySide6.QtCore import Qt, Signal, Slot


class FontToolbar(QWidget):
    """
    A toolbar widget for selecting and editing font properties.
    It binds to a target object's 'font' property and emits changes.
    """
    # Emits (target_object, property_name, old_value, new_value)
    font_changed = Signal(object, str, object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.target = None
        
        # --- UI Components ---
        self.font_combo = QFontComboBox()
        self.size_combo = QComboBox()
        self.bold_btn = QToolButton()
        self.italic_btn = QToolButton()
        self.underline_btn = QToolButton()

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        # Set up size combo box with common font sizes
        for size in range(8, 31, 2):
            self.size_combo.addItem(str(size))
        self.size_combo.setEditable(True)
        self.size_combo.setValidator(QIntValidator(1, 200, self))


        # Configure tool buttons for font styles
        self.bold_btn.setText("B")
        self.bold_btn.setCheckable(True)
        self.bold_btn.setToolTip("Bold")
        self.bold_btn.setFont(QFont("Arial", weight=QFont.Bold))


        self.italic_btn.setText("I")
        self.italic_btn.setCheckable(True)
        self.italic_btn.setToolTip("Italic")
        font = QFont("Arial")
        font.setItalic(True)
        self.italic_btn.setFont(font)


        self.underline_btn.setText("U")
        self.underline_btn.setCheckable(True)
        self.underline_btn.setToolTip("Underline")
        font = QFont("Arial")
        font.setUnderline(True)
        self.underline_btn.setFont(font)


        # Set the layout
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.font_combo)
        layout.addWidget(self.size_combo)
        layout.addWidget(self.bold_btn)
        layout.addWidget(self.italic_btn)
        layout.addWidget(self.underline_btn)
        self.setLayout(layout)

    def _connect_signals(self):
        """Connect UI component signals to the main change handler."""
        self.font_combo.currentFontChanged.connect(self._on_font_property_changed)
        self.size_combo.currentIndexChanged.connect(self._on_font_property_changed)
        # Handle custom text entry for size
        self.size_combo.lineEdit().editingFinished.connect(self._on_font_property_changed)
        self.bold_btn.toggled.connect(self._on_font_property_changed)
        self.italic_btn.toggled.connect(self._on_font_property_changed)
        self.underline_btn.toggled.connect(self._on_font_property_changed)

    def setTarget(self, target):
        """
        Set the target object and update the toolbar's UI to reflect its font.
        """
        self.target = target
        if self.target and hasattr(self.target, 'font'):
            # Block signals to prevent emitting while we set the UI
            self.blockSignals(True)
            self.set_font(self.target.font)
            self.blockSignals(False)

    @Slot()
    def _on_font_property_changed(self):
        """
        Construct a new font from the UI, update the target, and emit the change.
        """
        if not self.target or not hasattr(self.target, 'font'):
            return

        old_font = self.target.font

        # Construct the new font from the current state of the UI controls
        family = self.font_combo.currentFont().family()
        try:
            size = int(self.size_combo.currentText())
        except (ValueError, TypeError):
            size = old_font.pointSize() # Fallback to old size on invalid input

        new_font = QFont(family, size)
        new_font.setBold(self.bold_btn.isChecked())
        new_font.setItalic(self.italic_btn.isChecked())
        new_font.setUnderline(self.underline_btn.isChecked())

        # Only proceed and emit if the font has actually changed
        if old_font != new_font:
            self.target.font = new_font
            self.font_changed.emit(self.target, "font", new_font, old_font)

    def set_font(self, font: QFont):
        """A helper method to update all UI controls from a given QFont."""
        self.font_combo.setCurrentFont(font)
        self.size_combo.setCurrentText(str(font.pointSize()))
        self.bold_btn.setChecked(font.bold())
        self.italic_btn.setChecked(font.italic())
        self.underline_btn.setChecked(font.underline())