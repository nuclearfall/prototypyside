from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QComboBox, QLabel, QCheckBox, QSpinBox, QPushButton
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QPageSize
from prototypyside.widgets.unit_str_field import UnitStrField
from prototypyside.config import PAGE_SIZES
from prototypyside.utils.unit_converter import to_px
from prototypyside.config import DISPLAY_MODE_FLAGS
from prototypyside.services.pagination.page_manager import PageManager, PRINT_POLICIES


class LayoutToolbar(QWidget):
    """
    Top toolbar for LayoutTab.
    Includes: Page size (via QPageSize), is_landscape, grid dimensions,
    margins, spacing, and auto fill toggle.
    """

    # Signals emitted by toolbar controls
    page_size_changed = Signal(str)    # (display_string, QPageSize)
    orientation_changed = Signal(bool)

    grid_size_changed = Signal(int, int)
    margin_changed = Signal(str, int)
    spacing_changed = Signal(str, int)
    autofill_changed = Signal(bool)
    display_flag_changed = Signal(object)
    pagination_policy_changed = Signal(object)
    number_of_copies = Signal(int)
    orientation_property_change = Signal(str, bool, bool)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        # --- Page Size ---
        self.page_size_combo = QComboBox(self)
        # Populate combo with userData=key
        for key, cfg in PAGE_SIZES.items():
            self.page_size_combo.addItem(cfg["display"], key)

        # Connect to the index‐changed overload so we get an int
        self.page_size_combo.currentIndexChanged[int].connect(
            self._on_page_size_changed
        )
        layout.addWidget(QLabel("Page Size:", self))
        layout.addWidget(self.page_size_combo)

        # --- Orientation ---
        self.is_landscape_checkbox = QCheckBox("Landscape", self)
        self.is_landscape_checkbox.toggled.connect(self.change_orientation)
        layout.addWidget(self.is_landscape_checkbox)

        # --- Grid Dimensions ---
        self.rows_spin = QSpinBox(self)
        self.rows_spin.setRange(1, 20)

        self.cols_spin = QSpinBox(self)
        self.cols_spin.setRange(1, 20)

        self.rows_spin.valueChanged.connect(self.emit_grid_size_changed)
        self.cols_spin.valueChanged.connect(self.emit_grid_size_changed)

        # --- Auto Fill ---
        self.autofill_checkbox = QCheckBox("Auto Fill", self)
        self.autofill_checkbox.setChecked(True)
        self.autofill_checkbox.stateChanged.connect(
            lambda state: self.autofill_changed.emit(state == Qt.Checked)
        )

        #layout.addWidget(self.autofill_checkbox)

        layout.addStretch(1)

        # ── Pagination Policy selector ─────────────────────────────
        self.policy_combo_box = QComboBox(self)
        self.policy_combo_box.setToolTip("Pagination mode")
        for name in PRINT_POLICIES:
            self.policy_combo_box.addItem(name)
        layout.addWidget(self.policy_combo_box)

        # Signals
        self.policy_combo_box.currentTextChanged.connect(self._emit_policy_changed)

    @Slot(bool)
    def change_orientation(self, checked: bool):
        # checked == True  → Landscape; False → Portrait
        new = self.is_landscape_checkbox.isChecked()
        old = not new
        self.orientation_property_change.emit("is_landscape", new, old)

    def emit_grid_size_changed(self):
        rows = self.rows_spin.value()
        cols = self.cols_spin.value()
        self.grid_size_changed.emit(rows, cols)

    @Slot(int)
    def _on_page_size_changed(self, index: int):
        # Pull out the key you stored earlier in userData
        key = self.page_size_combo.itemData(index)
        self.page_size_changed.emit(key)

    @Slot(object)
    def _on_display_flag_changed(self, flag_key):
        flag = DISPLAY_MODE_FLAGS.get(display_flag).get("aspect")
        self.display_flag_changed.emit(flag)

    def apply_template(self, template):
        """
        Populate toolbar controls from a LayoutTemplate instance.
        Assumes template.page_size is a display string matching PAGE_SIZES.
        """
        idx = self.page_size_combo.findData(template.page_size)
        if idx != -1:
            self.page_size_combo.setCurrentIndex(idx)
        self.is_landscape_checkbox.setChecked(template.is_landscape)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _emit_policy_changed(self):
        self.pagination_policy_changed.emit(self.policy_combo_box.currentText())