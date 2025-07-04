# unit_field.py

from PySide6.QtWidgets import QLineEdit
from PySide6.QtCore import Signal
from typing import Optional

from prototypyside.utils.unit_converter import parse_dimension
from prototypyside.utils.unit_str import UnitStr


class UnitField(QLineEdit):
    editingFinishedWithValue = Signal(object)  # Emits UnitStr

    def __init__(self, initial: 'UnitStr' = None, unit=None, dpi=None, parent=None):
        super().__init__(parent)
        self._value = initial if initial is not None else None
        self._active = initial is not None
        self._dpi = dpi
        self._unit = unit
        self.editingFinished.connect(self._on_editing_finished)
        self.sync_display()

    def sync_display(self):
        """Update the display to reflect the current value, using self._display_unit and self._dpi."""
        if not self._active or self._value is None:
            self.setText("")
            self.setDisabled(True)
        else:
            self.setEnabled(True)
            self.setText(self._value.fmt(".4g", unit=self._unit, dpi=self._dpi))

    def _on_editing_finished(self):
        if not self._active:
            return
        try:
            txt = self.text().strip()
            # whatever the display unit is, set based on the value's original unit.
            storage_unit = self._value.unit
            storage_dpi = self._value.dpi
            self._value = UnitStr(txt, unit=storage_unit, dpi=storage_dpi)
            self.sync_display()
            self.editingFinishedWithValue.emit(self._value)
        except Exception:
            self.sync_display()
        self.clearFocus()

    def setValue(self, value: 'UnitStr'):
        if value is None:
            self._value = None
            self._active = False
        else:
            self._value = value
            self._active = True
        self.sync_display()

    def getValue(self):
        return self._value if self._active else None

    def on_unit_changed(self, unit: str):
        """
        Called when the measurement unit or dpi has changed (e.g. from inches to mm).
        Updates the display unit but leaves the internal value unchanged.
        """
        self._unit = unit
        self.sync_display()

