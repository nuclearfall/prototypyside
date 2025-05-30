# prototypyside/widgets/unit_field.py
from typing import Optional
from PySide6.QtWidgets import QLineEdit
from PySide6.QtCore import Signal
from prototypyside.utils.unit_converter import parse_dimension, format_dimension

class UnitField(QLineEdit):
    editingFinishedWithValue = Signal(int)

    def __init__(self, initial_px: Optional[int] = 0, unit: str = "in", dpi: int = 72, parent=None):
        super().__init__(parent)
        self._dpi = dpi
        self._unit = unit
        self._px_value = initial_px
        self._active = initial_px is not None

        self.editingFinished.connect(self._on_editing_finished)
        self._sync_display()

    def _sync_display(self):
        if not self._active:
            self.setText("")
            self.setDisabled(True)
        else:
            self.setEnabled(True)
            self.setText(format_dimension(self._px_value, unit=self._unit, dpi=self._dpi))

    def _on_editing_finished(self):
        if not self._active:
            return
        try:
            new_px = parse_dimension(self.text(), dpi=self._dpi)
            self._px_value = new_px
            self._sync_display()
            self.editingFinishedWithValue.emit(new_px)
        except Exception:
            self._sync_display()

    def set_px_value(self, px: Optional[int]):
        self._px_value = px
        self._active = px is not None
        self._sync_display()

    def get_px_value(self) -> Optional[int]:
        return self._px_value if self._active else None

    def set_unit(self, unit: str):
        self._unit = unit
        self._sync_display()

    def set_dpi(self, dpi: int):
        self._dpi = dpi
        self._sync_display()

