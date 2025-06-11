from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QComboBox, QHBoxLayout,
    QLabel, QDoubleSpinBox, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QPageSize
from PySide6.QtCore import QSizeF

from prototypyside.config import PAGE_SIZES

class PageSizeSelector(QWidget):
    pageSizeChanged = Signal(QPageSize)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signals()
        self._update_custom_inputs_visibility(False)

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.combo = QComboBox()
        self.combo.addItems(PAGE_SIZES.keys())
        layout.addWidget(QLabel("Select Page Size:"))
        layout.addWidget(self.combo)

        self.custom_inputs = QWidget()
        custom_layout = QHBoxLayout(self.custom_inputs)
        self.width_spin = QDoubleSpinBox()
        self.height_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.1, 100.0)
        self.height_spin.setRange(0.1, 100.0)
        self.width_spin.setValue(8.5)
        self.height_spin.setValue(11)

        custom_layout.addWidget(QLabel("Width:"))
        custom_layout.addWidget(self.width_spin)
        custom_layout.addWidget(QLabel("Height:"))
        custom_layout.addWidget(self.height_spin)

        self.unit_group = QButtonGroup(self)
        self.inches_radio = QRadioButton("in")
        self.mm_radio = QRadioButton("mm")
        self.inches_radio.setChecked(True)
        self.unit_group.addButton(self.inches_radio)
        self.unit_group.addButton(self.mm_radio)

        custom_layout.addWidget(self.inches_radio)
        custom_layout.addWidget(self.mm_radio)

        layout.addWidget(self.custom_inputs)

    def _connect_signals(self):
        self.combo.currentTextChanged.connect(self._on_selection_changed)
        self.width_spin.valueChanged.connect(self._emit_custom_size)
        self.height_spin.valueChanged.connect(self._emit_custom_size)
        self.inches_radio.toggled.connect(self._emit_custom_size)

    def _on_selection_changed(self, name):
        is_custom = PAGE_SIZES[name] is None
        self._update_custom_inputs_visibility(is_custom)

        if not is_custom:
            page_id = PAGE_SIZES[name]
            self.pageSizeChanged.emit(QPageSize(page_id))
        else:
            self._emit_custom_size()

    def _update_custom_inputs_visibility(self, visible: bool):
        self.custom_inputs.setVisible(visible)

    def _emit_custom_size(self):
        if not self.custom_inputs.isVisible():
            return

        width = self.width_spin.value()
        height = self.height_spin.value()
        unit = QPageSize.Inch if self.inches_radio.isChecked() else QPageSize.Millimeter
        name = f"Custom {width}×{height} {'in' if unit == QPageSize.Inch else 'mm'}"
        sizef = QSizeF(width, height)

        self.pageSizeChanged.emit(QPageSize(sizef, unit, name))

    def get_current_page_size(self) -> QPageSize:
        current_text = self.combo.currentText()
        if PAGE_SIZES[current_text] is None:
            width = self.width_spin.value()
            height = self.height_spin.value()
            unit = QPageSize.Inch if self.inches_radio.isChecked() else QPageSize.Millimeter
            return QPageSize(QSizeF(width, height), unit, "Custom")
        else:
            return QPageSize(PAGE_SIZES[current_text])
