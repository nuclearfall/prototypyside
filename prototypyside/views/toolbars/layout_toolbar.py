from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QComboBox, QLabel, QCheckBox, QSpinBox
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QPageSize
from prototypyside.widgets.unit_field import UnitField
from prototypyside.config import PAGE_SIZES
from prototypyside.utils.unit_converter import to_px
from prototypyside.config import DISPLAY_MODE_FLAGS


class LayoutToolbar(QWidget):
    """
    Top toolbar for LayoutTab.
    Includes: Page size (via QPageSize), orientation, grid dimensions,
    margins, spacing, and auto fill toggle.
    """

    # Signals emitted by toolbar controls
    page_size_changed = Signal(str, QPageSize)    # (display_string, QPageSize)
    orientation_changed = Signal(bool)
    grid_size_changed = Signal(int, int)
    margin_changed = Signal(str, int)
    spacing_changed = Signal(str, int)
    autofill_changed = Signal(bool)
    display_flag_changed = Signal(object)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        # --- Page Size ---
        self.page_size_combo = QComboBox(self)
        self.page_size_combo.addItems(list(PAGE_SIZES.keys()))
        self.page_size_combo.currentTextChanged.connect(self._on_page_size_changed)
        layout.addWidget(QLabel("Page Size:", self))
        layout.addWidget(self.page_size_combo)

        # --- Orientation ---
        self.orientation_checkbox = QCheckBox("Landscape", self)
        self.orientation_checkbox.stateChanged.connect(
            lambda state: self.orientation_changed.emit(state == Qt.Checked)
        )
        layout.addWidget(self.orientation_checkbox)

        # --- Grid Dimensions ---
        self.rows_spin = QSpinBox(self)
        self.rows_spin.setRange(1, 20)
        self.rows_spin.valueChanged.connect(
            lambda val: self.grid_size_changed.emit(val, self.cols_spin.value())
        )
        self.cols_spin = QSpinBox(self)
        self.cols_spin.setRange(1, 20)
        self.cols_spin.valueChanged.connect(
            lambda val: self.grid_size_changed.emit(self.rows_spin.value(), val)
        )

        layout.addWidget(QLabel("Rows:", self))
        layout.addWidget(self.rows_spin)
        layout.addWidget(QLabel("Cols:", self))
        layout.addWidget(self.cols_spin)

        # --- Auto Fill ---
        self.autofill_checkbox = QCheckBox("Auto Fill", self)
        self.autofill_checkbox.setChecked(True)
        self.autofill_checkbox.stateChanged.connect(
            lambda state: self.autofill_changed.emit(state == Qt.Checked)
        )
        layout.addWidget(self.autofill_checkbox)
        self.fitting_combo = QComboBox()
        for k, v in DISPLAY_MODE_FLAGS.items():
            self.fitting_combo.addItem(v.get("desc"), k)
        index = self.fitting_combo.findData("stretch")
        if index != -1:
            self.fitting_combo.setCurrentIndex(index)
        layout.addWidget(self.fitting_combo)
        self.fitting_combo.currentTextChanged.connect(self._on_display_flag_changed)
        layout.addStretch(1)

    @Slot(str)
    def _on_page_size_changed(self, name: str):
        """Handle page size selection and emit (display_string, QPageSize or None for custom)."""
        ps_enum = PAGE_SIZES.get(name)
        if ps_enum is not None:
            ps = QPageSize(ps_enum)
        else:
            ps = None  # Handle custom size logic as needed
        self.page_size_changed.emit(name, ps)

    @Slot(object)
    def _on_display_flag_changed(self, flag_key):
        flag = DISPLAY_MODE_FLAGS.get(display_flag).get("aspect")
        self.display_flag_changed.emit(flag)

    def apply_template(self, template):
        """
        Populate toolbar controls from a LayoutTemplate instance.
        Assumes template.page_size is a display string matching PAGE_SIZES.
        """
        if template.page_size in PAGE_SIZES:
            self.page_size_combo.setCurrentText(template.page_size)
            self._on_page_size_changed(template.page_size)
        self.orientation_checkbox.setChecked(template.landscape)
        self.rows_spin.setValue(template.rows)
        self.cols_spin.setValue(template.columns)
        self.autofill_checkbox.setChecked(template.auto_fill)

    def update_template(self, template):
        """
        Write back toolbar control values into the LayoutTemplate instance.
        All values are stored as unit strings.
        """
        template.page_size = self.page_size_combo.currentText()
        template.landscape = self.orientation_checkbox.isChecked()
        template.rows = self.rows_spin.value()
        template.cols = self.cols_spin.value()
        template.auto_fill = self.autofill_checkbox.isChecked()
