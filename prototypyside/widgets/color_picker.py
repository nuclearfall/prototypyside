from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QPushButton, QComboBox,
    QGroupBox, QFormLayout, QCheckBox, QColorDialog
)
from PySide6.QtCore import Qt, Signal, QRectF, QTimer
from PySide6.QtGui import QColor, QPalette # Import QColor
from prototypyside.widgets.unit_field import UnitField
from prototypyside.widgets.font_toolbar import FontToolbar

# --- NEW WIDGET: ColorPickerWidget ---
class ColorPickerWidget(QPushButton):
    """
    A custom widget that displays a color and opens a QColorDialog when clicked.
    Emits color_changed(QColor) when a new color is selected.
    """
    color_changed = Signal(QColor)

    def __init__(self, initial_color: QColor = QColor(0, 0, 0), parent: QWidget = None):
        super().__init__("", parent) # No text on the button
        self._current_color = initial_color
        self.setFixedSize(50, 24) # Adjust size as needed for your layout
        self.setFlat(True) # Make it look less like a standard button

        self.clicked.connect(self._open_color_dialog)
        self._update_style() # Set initial background color

    def _update_style(self):
        """Updates the button's background color via stylesheet."""
        # Use a border to make it visible even for white colors
        self.setStyleSheet(
            f"background-color: {self._current_color.name()}; "
            "border: 1px solid gray;"
        )

    def set_color(self, color: QColor):
        """Sets the widget's displayed color."""
        if self._current_color != color:
            self._current_color = color
            self._update_style()

    def get_color(self) -> QColor:
        """Returns the current QColor."""
        return self._current_color

    def _open_color_dialog(self):
        """Opens the QColorDialog and handles the selection."""
        # Get the initial color from the current displayed color
        initial_color = self._current_color if self._current_color.isValid() else QColor(0,0,0)
        
        # Open the color dialog
        color = QColorDialog.getColor(initial_color, self.parentWidget()) # Use parent for better dialog placement

        if color.isValid():
            self.set_color(color) # Update the widget's color
            self.color_changed.emit(color) # Emit the signal with the new QColor