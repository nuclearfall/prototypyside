# unit_strings_field.py
from __future__ import annotations
from typing import Any, List, Optional
from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel

from prototypyside.widgets.unit_str_field import UnitStrField
from prototypyside.utils.units.unit_str import UnitStr as _US

class UnitStringsField(QWidget):
    """
    A composite field that manages a grid of UnitStrField children and
    aggregates their values into a single list, emitting:
        valueChanged(target_item, property_name, new_list, old_list)
    """
    valueChanged = Signal(object, str, object, object)  # (target, prop_name, new_values, old_values)

    def __init__(
        self,
        target_item: Optional[Any],
        property_name: Optional[str],
        labels: Optional[List[str]],
        rows: int,
        columns: int,
        dpi: int,
        display_unit: str = "in",
        decimal_places: int = 2,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        # Model
        self.target_item: Optional[Any] = target_item
        self.property_name: Optional[str] = property_name
        self._labels_text: List[str] = labels or []
        self._rows_count = int(rows)
        self._cols_count = int(columns)
        self._dpi = int(dpi)
        self._display_unit = display_unit
        self._decimal_places = int(decimal_places)

        # UI containers
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        # Children
        self._labels: List[QLabel] = []
        self._fields: List[UnitStrField] = []  # flattened row-major order

        # State
        self._old_values: List[_US] = []

        # Build grid
        total = self._rows_count * self._cols_count
        for r in range(self._rows_count):
            row_layout = QHBoxLayout()
            for c in range(self._cols_count):
                idx = r * self._cols_count + c

                # Label (optional)
                lbl_text = self._labels_text[idx] if idx < len(self._labels_text) else f"#{idx + 1}"
                lbl = QLabel(lbl_text)
                self._labels.append(lbl)
                row_layout.addWidget(lbl)

                # Child field (target for children can be None; they will carry their own value)
                child_prop = f"{self.property_name}_{idx}" if self.property_name else f"unit[{idx}]"
                uf = UnitStrField(
                    target_item=None,  # important: child doesn't need a real prop on the target
                    property_name=child_prop,
                    display_unit=self._display_unit,
                    decimal_places=self._decimal_places,
                    dpi=self._dpi,
                    parent=self,
                )
                # Whenever a child changes, aggregate & emit
                uf.valueChanged.connect(self._on_child_changed)
                self._fields.append(uf)
                row_layout.addWidget(uf)

            self._layout.addLayout(row_layout)

        # Initialize from target, if present
        if self.target_item is not None and self.property_name:
            maybe_list = getattr(self.target_item, self.property_name, None)
            if isinstance(maybe_list, list) and all(isinstance(v, _US) for v in maybe_list):
                self.setValues(maybe_list)
            else:
                # no initial list; keep old_values aligned with field count
                self._old_values = [getattr(f, "value", lambda: None)() or _US("0", self._dpi) for f in self._fields]
        else:
            self._old_values = [getattr(f, "value", lambda: None)() or _US("0", self._dpi) for f in self._fields]

    # ---------- Public API ----------

    def setTarget(self, target_item: Optional[Any]) -> None:
        """Point this composite at a new target. Pulls current list from property if available."""
        self.target_item = target_item
        if self.target_item is not None and self.property_name:
            vals = getattr(self.target_item, self.property_name, None)
            if isinstance(vals, list) and all(isinstance(v, _US) for v in vals):
                self.setValues(vals)
            else:
                # no list present on target; do not clobber target, just refresh UI from children
                self._old_values = self.values()

    def values(self) -> List[_US]:
        """Return the list composed from all child fields (row-major)."""
        out: List[_US] = []
        for f in self._fields:
            if hasattr(f, "value"):
                us = f.value()
                if isinstance(us, _US):
                    out.append(us)
                else:
                    # best-effort: try to coerce; UnitStr usually accepts strings or numbers
                    out.append(_US(str(us), self._dpi))
            else:
                out.append(_US("0", self._dpi))
        return out

    def setValues(self, unit_values: List[_US]) -> tuple[Any, Optional[str], List[_US], List[_US]]:
        """Set all child field values, then emit aggregated change."""
        assert isinstance(unit_values, list) and all(isinstance(v, _US) for v in unit_values), \
            "UnitStringsField.setValues requires List[UnitStr]"

        # Write into children (truncate/pad to grid size)
        total = len(self._fields)
        for i in range(total):
            us = unit_values[i] if i < len(unit_values) else unit_values[-1] if unit_values else _US("0", self._dpi)
            if hasattr(self._fields[i], "setValue"):
                self._fields[i].setValue(us)

        old_list = list(self._old_values)
        new_list = self.values()

        # Update target's list property if configured
        if self.target_item is not None and self.property_name:
            setattr(self.target_item, self.property_name, new_list)

        self._old_values = list(new_list)
        self.valueChanged.emit(self.target_item, self.property_name or "", new_list, old_list)
        return (self.target_item, self.property_name, new_list, old_list)

    def clear(self) -> None:
        for f in self._fields:
            if hasattr(f, "clear"):
                f.clear()
        self._old_values = self.values()

    # ---------- Child passthroughs ----------

    def setDisplayUnit(self, unit: str) -> None:
        self._display_unit = unit
        for f in self._fields:
            if hasattr(f, "setDisplayUnit"):
                f.setDisplayUnit(unit)

    def setDecimalPlaces(self, places: int) -> None:
        self._decimal_places = int(places)
        for f in self._fields:
            if hasattr(f, "setDecimalPlaces"):
                f.setDecimalPlaces(self._decimal_places)

    def setDpi(self, dpi: int) -> None:
        self._dpi = int(dpi)
        for f in self._fields:
            if hasattr(f, "setDpi"):
                f.setDpi(self._dpi)

    # ---------- Internals ----------

    @Slot(object, str, object, object)
    def _on_child_changed(self, _child_target: Any, _child_prop: str, _new: _US, _old: _US) -> None:
        """
        Any child changed → aggregate all child values and emit single valueChanged
        with the real (composite) property name, ignoring the child's fake prop.
        """
        old_list = list(self._old_values)
        new_list = self.values()

        # write through to target if configured
        if self.target_item is not None and self.property_name:
            setattr(self.target_item, self.property_name, new_list)

        self._old_values = list(new_list)
        self.valueChanged.emit(self.target_item, self.property_name or "", new_list, old_list)
