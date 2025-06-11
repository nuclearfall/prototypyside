from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QSpinBox, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt

class SettingsDialog(QDialog):
    def __init__(self, parent=None, unit="in", display_dpi=72, print_dpi=300):
        super().__init__(parent)
        self.setWindowTitle("Application Settings")

        self._unit = unit
        self._display_dpi = display_dpi
        self._print_dpi = print_dpi

        layout = QVBoxLayout()

        # Unit Selector
        layout.addWidget(QLabel("Display Unit:"))
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["in", "mm", "cm", "pt", "px"])
        self.unit_combo.setCurrentText(unit)
        layout.addWidget(self.unit_combo)

        # Display DPI
        layout.addWidget(QLabel("Display DPI:"))
        self.display_dpi_spin = QSpinBox()
        self.display_dpi_spin.setRange(36, 600)
        self.display_dpi_spin.setValue(display_dpi)
        layout.addWidget(self.display_dpi_spin)

        # Print DPI
        layout.addWidget(QLabel("Print DPI:"))
        self.print_dpi_spin = QSpinBox()
        self.print_dpi_spin.setRange(72, 1200)
        self.print_dpi_spin.setValue(print_dpi)
        layout.addWidget(self.print_dpi_spin)

        # Buttons
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def get_settings(self):
        return (
            self.unit_combo.currentText(),
            self.display_dpi_spin.value(),
            self.print_dpi_spin.value()
        )
