# unit_strings_field.py

from __future__ import annotations
from typing import Any, List, Optional, Sequence

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QWidget, QGridLayout, QLabel, QLineEdit

from prototypyside.models.component_element import ComponentElement
from prototypyside.utils.units.unit_str import UnitStr


class UnitStringsField(QWidget):
    """
    Compound widget for editing a List[UnitStr] property on a target object.
    - Renders N labeled QLineEdits, one per UnitStr.
    - Emits a single valueChanged event with the entire updated list.
    - Formatting / behavior parallels UnitStrGeometryField.
    """

    # Emits: target_object, property_name, new_values (List[UnitStr]), old_values (List[UnitStr])
    valueChanged = Signal(object, str, object, object)

    def __init__(
        self,
        target_item: Optional[Any] = None,
        property_name: Optional[str] = None,
        labels: Optional[Sequence[str]] = None,
        display_unit: Optional[str] = None,
        parent: Optional[QWidget] = None,
        decimal_places: int = 4,
    ):
        super().__init__(parent)
        self.target_item: Optional[Any] = None
        self.property_name: Optional[str] = None
        self._display_unit: Optional[str] = display_unit
        self._decimal_places: int = decimal_places

        # ui
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(5)

        # model
        self._old_values: Optional[List[UnitStr]] = None
        self._dpi: Optional[int] = None

        # dynamic sub-fields
        self._labels: List[str] = list(labels) if labels else []
        self._edits: List[QLineEdit] = []
        self._build_rows(self._labels)

        if target_item and property_name:
            self.setTarget(target_item, property_name, display_unit=display_unit)

    # --------------------------
    # Public API
    # --------------------------
    def setTarget(self, target_item: Any, property_name: str, display_unit: Optional[str] = None):
        self.target_item = target_item
        self.property_name = property_name
        if display_unit is not None:
            self._display_unit = display_unit

        # Keep in sync with external changes
        if isinstance(self.target_item, ComponentElement):
            try:
                self.target_item.item_changed.disconnect(self.update_from_item)
            except Exception:
                pass
            self.target_item.item_changed.connect(self.update_from_item)

        # Read property
        values = getattr(self.target_item, self.property_name, None)
        if isinstance(values, list) and all(isinstance(v, UnitStr) for v in values):
            self._old_values = list(values)
            self._dpi = values[0].dpi if values else getattr(self.target_item, "_geometry", None) and self.target_item._geometry.dpi
            self._ensure_row_count(len(values))
            self._update_display(values)
        else:
            self._clear_fields()
            self._old_values = None

    def on_unit_change(self, display_unit: str):
        self._display_unit = display_unit
        if self.target_item and self._old_values is not None:
            self._update_display(self._old_values)

    @Slot()
    def update_from_item(self):
        # Refresh from target if property changed elsewhere
        if not self.target_item or not self.property_name:
            return
        values = getattr(self.target_item, self.property_name, None)
        if isinstance(values, list) and all(isinstance(v, UnitStr) for v in values):
            self._ensure_row_count(len(values))
            self._old_values = list(values)
            self._dpi = values[0].dpi if values else self._dpi
            self._update_display(values)

    # --------------------------
    # Internals
    # --------------------------
    def _build_rows(self, labels: Sequence[str]):
        # Clear old
        for i, edit in enumerate(self._edits):
            try:
                edit.editingFinished.disconnect()
            except Exception:
                pass
            self._layout.removeWidget(edit)
            edit.deleteLater()
        for i in reversed(range(self._layout.count())):
            # remove labels as well
            w = self._layout.itemAt(i).widget()
            if w:
                self._layout.removeWidget(w)
                w.deleteLater()
        self._edits = []

        # Build new
        for row, text in enumerate(labels):
            lbl = QLabel(text, self)
            edit = QLineEdit(self)
            # stash index to identify sender
            edit.setProperty("row_index", row)
            edit.editingFinished.connect(self._on_editing_finished)
            self._layout.addWidget(lbl, row, 0)
            self._layout.addWidget(edit, row, 1)
            self._edits.append(edit)

    def _ensure_row_count(self, count: int):
        # Expand or shrink rows to match property length (keeps labels if already provided)
        if len(self._edits) == count:
            return
        # If labels weren't specified or mismatch, synthesize generic ones
        if not self._labels or len(self._labels) != count:
            self._labels = [f"V{i}" for i in range(count)]
        self._build_rows(self._labels)

    def _clear_fields(self):
        for e in self._edits:
            e.clear()

    def _update_display(self, values: List[UnitStr]):
        if not values:
            self._clear_fields()
            return
        unit = self._display_unit
        dpi = values[0].dpi if values[0] is not None else self._dpi
        fmt = f".{self._decimal_places}g"
        for i, e in enumerate(self._edits):
            if i < len(values) and isinstance(values[i], UnitStr):
                e.setText(values[i].fmt(fmt, unit=unit, dpi=dpi))
            else:
                e.clear()

    def _make_unit_str(self, text: str, dpi: int) -> UnitStr:
        s = (text or "").strip()
        if not s:
            s = "0"
        if s.startswith('.'):
            s = '0' + s
        elif s.startswith('-.'):
            s = '-0' + s[1:]
        return UnitStr(s, unit=self._display_unit, dpi=dpi)

    @Slot()
    def _on_editing_finished(self):
        if not self.target_item or not self.property_name or self._old_values is None:
            # still drop focus for UX parity with other fields
            sender = self.sender()
            if isinstance(sender, QLineEdit):
                sender.clearFocus()
            return

        dpi = self._dpi or (self._old_values[0].dpi if self._old_values else 72)
        # Build a fresh list from all fields (not just the edited one)
        try:
            new_values: List[UnitStr] = [self._make_unit_str(e.text(), dpi) for e in self._edits]
        except ValueError:
            # revert
            self._update_display(self._old_values)
            sender = self.sender()
            if isinstance(sender, QLineEdit):
                sender.clearFocus()
            return

        # Compare by .value (canonical internal magnitude)
        unchanged = (
            len(new_values) == len(self._old_values) and
            all(a.value == b.value for a, b in zip(new_values, self._old_values))
        )
        if unchanged:
            self._update_display(new_values)  # normalize formatting
            sender = self.sender()
            if isinstance(sender, QLineEdit):
                sender.clearFocus()
            return

        # Emit for undo/redo; actual assignment is handled by the consumer (like your PropertyPanel)
        self.valueChanged.emit(self.target_item, self.property_name, new_values, self._old_values)

        # Update local state
        self._old_values = new_values
        self._update_display(new_values)

        sender = self.sender()
        if isinstance(sender, QLineEdit):
            sender.clearFocus()
