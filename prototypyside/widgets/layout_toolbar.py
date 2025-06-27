from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QComboBox, QLabel, QCheckBox, QSpinBox
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QPageSize
from prototypyside.widgets.unit_field import UnitField
from prototypyside.config import PAGE_SIZES
from prototypyside.utils.unit_converter import to_px

class LayoutToolbar(QWidget):
    """
    Top toolbar for LayoutTab.
    Includes: Page size (via QPageSize), orientation, grid dimensions,
    margins, spacing, and auto fill toggle.
    """

    # Signals emitted by toolbar controls
    page_size_changed = Signal(QPageSize)
    orientation_changed = Signal(bool)
    grid_size_changed = Signal(int, int)
    margin_changed = Signal(str, int)
    spacing_changed = Signal(str, int)
    autofill_changed = Signal(bool)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        # --- Page Size ---
        self.page_size_combo = QComboBox(self)
        self.page_size_combo.addItems(PAGE_SIZES.keys())
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

        # # --- Margins ---
        # self.margin_top = UnitField(unit="in", dpi=self.settings.dpi)
        # self.margin_bottom = UnitField(unit="in", dpi=self.settings.dpi)
        # self.margin_left = UnitField(unit="in", dpi=self.settings.dpi)
        # self.margin_right = UnitField(unit="in", dpi=self.settings.dpi)
        # for name, field in (
        #     ("margin_top", self.margin_top),
        #     ("margin_bottom", self.margin_bottom),
        #     ("margin_left", self.margin_left),
        #     ("margin_right", self.margin_right),
        # ):
        #     field.editingFinishedWithValue.connect(
        #         lambda val, n=name: self.margin_changed.emit(n, val)
        #     )
        # layout.addWidget(QLabel("Top:", self))
        # layout.addWidget(self.margin_top)
        # layout.addWidget(QLabel("Bottom:", self))
        # layout.addWidget(self.margin_bottom)
        # layout.addWidget(QLabel("Left:", self))
        # layout.addWidget(self.margin_left)
        # layout.addWidget(QLabel("Right:", self))
        # layout.addWidget(self.margin_right)

        # # --- Spacing ---
        # self.spacing_x = UnitField(unit="in", dpi=self.settings.dpi)
        # self.spacing_y = UnitField(unit="in", dpi=self.settings.dpi)
        # for name, field in (
        #     ("slot_spacing_x", self.spacing_x),
        #     ("slot_spacing_y", self.spacing_y),
        # ):
        #     field.editingFinishedWithValue.connect(
        #         lambda val, n=name: self.spacing_changed.emit(n, val)
        #     )
        # layout.addWidget(QLabel("Spacing X:", self))
        # layout.addWidget(self.spacing_x)
        # layout.addWidget(QLabel("Spacing Y:", self))
        # layout.addWidget(self.spacing_y)

        # --- Auto Fill ---
        self.autofill_checkbox = QCheckBox("Auto Fill", self)
        self.autofill_checkbox.setChecked(True)
        self.autofill_checkbox.stateChanged.connect(
            lambda state: self.autofill_changed.emit(state == Qt.Checked)
        )
        layout.addWidget(self.autofill_checkbox)
        layout.addStretch(1)

    @Slot(str)
    def _on_page_size_changed(self, name: str):
        """
        Compute page width/height in pixels from QPageSize and emit.
        """
        ps = QPageSize(PAGE_SIZES[name])
        size_in = ps.size(QPageSize.Unit.Inch)
        w_px = to_px(f"{size_in.width()}in")
        h_px = to_px(f"{size_in.height()}in")
        self.page_size_changed.emit(ps)

    def apply_template(self, template):
        """
        Populate toolbar controls from a LayoutTemplate instance.
        """
        self.page_size_combo.setCurrentText(template.page_size)
        # Force width/height emission
        self._on_page_size_changed(template.page_size)
        self.orientation_checkbox.setChecked(template.landscape)
        self.rows_spin.setValue(template.rows)
        self.cols_spin.setValue(template.cols)
        # # Margins
        # self.margin_top.setValue(to_px(template.margin_top))
        # self.margin_bottom.setValue(to_px(template.margin_bottom))
        # self.margin_left.setValue(to_px(template.margin_left))
        # self.margin_right.setValue(to_px(template.margin_right))
        # # Spacing
        # self.spacing_x.setValue(to_px(template.slot_spacing_x))
        # self.spacing_y.setValue(to_px(template.slot_spacing_y))
        # # Auto fill
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
        template.margin_top = self.margin_top.text()
        template.margin_bottom = self.margin_bottom.text()
        template.margin_left = self.margin_left.text()
        template.margin_right = self.margin_right.text()
        template.slot_spacing_x = self.spacing_x.text()
        template.slot_spacing_y = self.spacing_y.text()
        template.auto_fill = self.autofill_checkbox.isChecked()
