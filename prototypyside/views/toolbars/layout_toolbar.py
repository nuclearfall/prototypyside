from PySide6.QtWidgets import QWidget, QHBoxLayout, QComboBox, QLabel, QCheckBox
from PySide6.QtCore import Slot
from prototypyside.services.pagination.page_manager import PRINT_POLICIES
from prototypyside.config import VALID_MEASURES

class LayoutToolbar(QWidget):
    """
    Top toolbar for LayoutTab.
    Includes: Page size (via QPageSize), is_landscape, grid dimensions,
    margins, spacing, and auto fill toggle.
    """

    def __init__(self, tab, parent=None):
        super().__init__(parent)
        self.tab = tab
        self.template = tab.template
        self.settings = tab.settings
 
        self.unit_selector = QComboBox(parent=self)
        for u in VALID_MEASURES:
            self.unit_selector.addItem(u, u)
        self.grid_checkbox = QCheckBox(parent=self)
        self.policy_combo_box = QComboBox(parent=self)
        self.policy_combo_box.setToolTip("Pagination mode")
        for name in PRINT_POLICIES:
            self.policy_combo_box.addItem(name, name)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(QLabel("Unit:"))
        layout.addWidget(self.unit_selector)
        layout.addWidget(QLabel("Show Grid:"))
        layout.addWidget(self.grid_checkbox)
        layout.addWidget(QLabel("Policy:"))
        layout.addWidget(self.policy_combo_box)

        # Signals
        self.unit_selector.currentTextChanged.connect(self._unit_changed)
        self.grid_checkbox.toggled.connect(self._grid_toggled)
        self.policy_combo_box.currentTextChanged.connect(self._policy_changed)

        self.set_initial_values()

    def set_initial_values(self):
        # Block signals during initial priming to avoid firing slots
        u_block = self.unit_selector.blockSignals(True)
        p_block = self.policy_combo_box.blockSignals(True)
        g_block = self.grid_checkbox.blockSignals(True)

        # all units in the list are guaranteed to exist.
        unit = self.tab.settings.display_unit
        self.unit_selector.setCurrentText(unit)

        self.grid_checkbox.setChecked(True)
        self.tab.inc_grid.setEnabled(True)

        policy = self.tab.template.polkey
        self.policy_combo_box.setCurrentText(policy)

        # Restore signal delivery
        self.unit_selector.blockSignals(u_block)
        self.policy_combo_box.blockSignals(p_block)
        self.grid_checkbox.blockSignals(g_block)

    @Slot(bool)
    def _grid_toggled(self, state: bool):
        self.tab.inc_grid.setEnabled(state)

    @Slot(str)
    def _unit_changed(self, unit):
        self.tab.on_unit_change(unit)

    @Slot(str)
    def _policy_changed(self, policy):
        self.tab.on_policy_changed(policy)
