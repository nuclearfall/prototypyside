# unit_field.py

from PySide6.QtWidgets import QLineEdit
from PySide6.QtCore import Signal
from typing import Optional

from prototypyside.utils.unit_str import UnitStr


class UnitField(QLineEdit):
    editingFinishedWithValue = Signal(object)  # Emits UnitStr

    def __init__(self, initial: 'UnitStr' = None, unit="px", dpi=300, parent=None):
        super().__init__(parent)
        self._value = initial if initial is not None else None
        self._active = initial is not None
        self._unit = unit
        self._dpi = dpi
        self.editingFinished.connect(self._on_editing_finished)
        self.sync_display()

    def sync_display(self):
        """Update the display to reflect the current value, using self._unit and self._dpi."""
        if not self._active or self._value is None:
            self.setText("")
            self.setDisabled(True)
        else:
            self.setEnabled(True)
            # Show value in the selected unit, e.g. "25.4 mm" even if underlying is inches
            self.setText(self._value.format(".4g", unit=self._unit))

    def _on_editing_finished(self):
        if not self._active:
            return
        try:
            txt = self.text().strip()
            display_unit = self._unit
            display_dpi = self._dpi

            # Try to parse the unit from the text directly (allows user to enter e.g. "50 mm")
            try:
                new_value = UnitStr(txt, dpi=display_dpi)
                # If user entered "100 px" but UI is in "in", convert to "in"
                if new_value.unit == "px" and display_unit != "px":
                    # Convert px to current unit
                    val_in_unit = new_value.to(display_unit, dpi=display_dpi)
                    new_value = UnitStr(val_in_unit, unit=display_unit, dpi=display_dpi)
            except Exception:
                # Fallback: treat as number in current unit
                val = float(txt)
                new_value = UnitStr(val, unit=display_unit, dpi=display_dpi)

            self._value = new_value
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
        Called when the measurement unit has changed (e.g. from inches to mm).
        Updates the display unit but leaves the internal value unchanged.
        """
        self._unit = unit
        self.sync_display()

# from typing import Optional
# from PySide6.QtWidgets import QLineEdit
# from PySide6.QtCore import Signal
# from prototypyside.utils.unit_converter import parse_dimension, format_dimension

# class UnitField(QLineEdit):
#     editingFinishedWithValue = Signal(int)

#     def __init__(self, initial_px: Optional[int] = 0, unit: str = "in", dpi: int = 300, pdpi: int = 300, parent=None):
#         super().__init__(parent)
#         self._dpi = dpi
#         self._pdpi = 300
#         self._unit = unit
#         self._px_value = initial_px
#         self._active = initial_px is not None
#         self._physical_unit = "in"

#         self.editingFinished.connect(self._on_editing_finished)
#         self.sync_display()

#     def _sync_display(self):
#         if not self._active:
#             self.setText("")
#             self.setDisabled(True)
#         else:
#             self.setEnabled(True)
#             self.setText(format_dimension(self._px_value, unit=self._unit, dpi=self._dpi))

#     def _on_editing_finished(self):
#         if not self._active:
#             return
#         try:
#             self._physical = parse_dimension(self.text(), dpi=self._dpi)
#             new_px = parse_dimension(self.text(), dpi=self._dpi)
#             self._px_value = new_px
#             self.sync_display()
#             self.editingFinishedWithValue.emit(new_px)
#         except Exception:
#             self.sync_display()

#     def set_px_value(self, px: Optional[int]):
#         self._px_value = px
#         self._active = px is not None
#         self.sync_display()

#     def setValue(self, px: Optional[int]):
#         self.set_px_value(px)

#     def get_px_value(self) -> Optional[int]:
#         return self._px_value if self._active else None

#     def set_unit(self, unit: str):
#         self._unit = unit
#         self.sync_display()

#     def set_dpi(self, dpi: int):
#         self._dpi = dpi
#         self.sync_display()

