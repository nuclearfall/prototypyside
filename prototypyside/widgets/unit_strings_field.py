# unit_strings_field.py
from typing import Any, List, Optional
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel

from prototypyside.widgets.unit_str_field import UnitStrField
from prototypyside.services.proto_class import ProtoClass
_US = ProtoClass.US.resolve()      # UnitStr class object

class _RowModel(QObject):
    # UnitStrField listens to this to refresh when 'value' changes.
    item_changed = Signal()
    def __init__(self, us: _US):
        super().__init__()
        self.value: _US = us  # <- authoritative per-row UnitStr

class UnitStringsField(QWidget):
    # Emits (target_item, property_name, new_val_list, old_val_list)
    valueChanged = Signal(object, str, object, object)

    def __init__(self,
                 parent: Optional[QWidget] = None,
                 target_item: Any = None,
                 property_name: Optional[str] = None,
                 display_unit: str = "in",
                 decimal_places: int = 2,
                 dpi: int = 300,
                 labels: Optional[List[str]] = None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.target_item = None
        self.property_name = None
        self._display_unit = display_unit or "in"
        self.decimal_places = decimal_places
        self._dpi = dpi

        self._old_values: List[_US] = []
        self._rows: List[UnitStrField] = []
        self._row_models: List[_RowModel] = []
        self._row_labels: List[QLabel] = []
        self._labels: List[str] = list(labels) if labels else []

        if target_item is not None and property_name:
            self.setTarget(
                target_item, 
                property_name=property_name, 
                display_unit=display_unit,
                labels=labels
            )

    # -------- Public API --------
    def clear(self) -> None:
        """
        Clear all contained UnitStrFields. Does not change the number of rows.
        """
        for f in self._rows:
            if hasattr(f, "clear"):
                f.clear()

    def setTarget(self, target_item: Any, property_name: str,
                  display_unit: Optional[str] = None,
                  labels: Optional[List[str]] = None):
        self.target_item = target_item
        self.property_name = property_name
        if display_unit is not None:
            self._display_unit = display_unit
        if labels is not None:
            self._labels = list(labels)
        if self.target_item is None or self.property_name is None:
            self.clear()

        if hasattr(self.target_item, "item_changed"):
            try:
                self.target_item.item_changed.disconnect(self.update_from_item)
            except Exception:
                pass
            self.target_item.item_changed.connect(self.update_from_item)

        values = getattr(self.target_item, self.property_name, None)
        if isinstance(values, list) and all(isinstance(v, _US) for v in values):
            self._old_values = list(values)
            if values:
                self._dpi = getattr(values[0], "dpi", self._dpi)
            elif getattr(self.target_item, "geometry", None) is not None:
                self._dpi = getattr(self.target_item._geometry, "dpi", self._dpi)
            self._ensure_row_count(len(values))
            self._update_labels()
            self._update_display(values)
        else:
            self._old_values = []
            self._ensure_row_count(0)
            self._update_labels()

    def setLabels(self, labels: List[str]) -> None:
        self._labels = list(labels)
        self._update_labels()

    def values(self) -> List[_US]:
        # Prefer child.value() if it exists; else our row_model.value
        out: List[_US] = []
        for i, f in enumerate(self._rows):
            if hasattr(f, "value"):
                us = f.value()
            else:
                us = self._row_models[i].value
            if isinstance(us, _US):
                out.append(us)
        return out

    def setValues(self, unit_values: List[_US]):
        assert isinstance(unit_values, list) and all(isinstance(v, _US) for v in unit_values), \
            "UnitStringsField.setValues requires List[UnitStr]"
        self._ensure_row_count(len(unit_values))
        self._update_labels()
        self._update_display(unit_values)  # writes into row models & refreshes fields

        old_list = list(self._old_values)
        new_list = self.values()

        if self.target_item is not None and self.property_name:
            setattr(self.target_item, self.property_name, new_list)

        self._old_values = list(new_list)
        self.valuesChanged.emit(self.target_item, self.property_name, new_list, old_list)
        return (self.target_item, self.property_name, new_list, old_list)

    # -------- Internals --------

    def _ensure_row_count(self, count: int):
        # grow
        while len(self._rows) < count:
            idx = len(self._rows)

            # UI row layout: [QLabel][UnitStrField]
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)

            lbl = QLabel(self._label_text_for_index(idx))
            self._row_labels.append(lbl)
            row_layout.addWidget(lbl)

            # row model placeholder (will be replaced/assigned in _update_display)
            model = _RowModel(us=_US(0, unit=self._display_unit, dpi=self._dpi))  # create a benign UnitStr
            self._row_models.append(model)

            field = UnitStrField(
                parent=self,
                display_unit=self._display_unit,
                decimal_places=self.decimal_places,
                dpi=self._dpi,
            )
            # IMPORTANT: use UnitStrField's setTarget (not setValue)
            field.setTarget(model, "value", display_unit=self._display_unit)

            # When child field changes, we get a UnitStr back
            if hasattr(field, "valueChanged"):
                field.valueChanged.connect(lambda us, i=idx: self._on_row_changed(i, us))
            self._rows.append(field)

            row_layout.addWidget(field)
            self._layout.addLayout(row_layout)

        # shrink
        while len(self._rows) > count:
            last = self._layout.takeAt(self._layout.count() - 1)
            if last and last.layout():
                lyt = last.layout()
                while lyt.count():
                    sub = lyt.takeAt(0)
                    w = sub.widget()
                    if w is not None:
                        w.setParent(None)
                        w.deleteLater()
            f = self._rows.pop()
            f.setParent(None)
            f.deleteLater()

            m = self._row_models.pop()
            m.deleteLater()
            lbl = self._row_labels.pop()
            lbl.setParent(None)
            lbl.deleteLater()

    def _label_text_for_index(self, idx: int) -> str:
        return self._labels[idx] if idx < len(self._labels) else f"#{idx + 1}"

    def _update_labels(self):
        for i, lbl in enumerate(self._row_labels):
            lbl.setText(self._label_text_for_index(i))

    def _update_display(self, values: List[_US]):
        # Write UnitStrs into row models and nudge children via item_changed
        for i, us in enumerate(values):
            model = self._row_models[i]
            model.value = us  # keep raw UnitStr (no conversion)
            # make sure display settings are in sync (child handles formatting)
            f = self._rows[i]
            if hasattr(f, "setDisplayUnit"): f.setDisplayUnit(self._display_unit)
            if hasattr(f, "setDecimalPlaces"): f.setDecimalPlaces(self.decimal_places)
            if hasattr(f, "setDpi"): f.setDpi(self._dpi)
            model.item_changed.emit()  # tells UnitStrField to refresh from model.value

    @Slot()
    def update_from_item(self):
        if not (self.target_item and self.property_name):
            return
        values = getattr(self.target_item, self.property_name, None)
        if isinstance(values, list) and all(isinstance(v, _US) for v in values):
            self._ensure_row_count(len(values))
            self._update_labels()
            self._update_display(values)

    @Slot(object)
    def _on_row_changed(self, index: int, us: _US):
        if not isinstance(us, _US):
            return
        current = self.values()
        if index >= len(current):
            self._ensure_row_count(index + 1)
            self._update_labels()
            current = self.values()
        current[index] = us

        old_list = list(self._old_values)
        new_list = current

        if self.target_item is not None and self.property_name:
            setattr(self.target_item, self.property_name, new_list)

        self._old_values = list(new_list)
        self.valuesChanged.emit(self.target_item, self.property_name, new_list, old_list)

    # pass-throughs
    def setDisplayUnit(self, unit: str):
        self._display_unit = unit
        for f in self._rows:
            if hasattr(f, "setDisplayUnit"):
                f.setDisplayUnit(unit)

    def setDecimalPlaces(self, places: int):
        self.decimal_places = places
        for f in self._rows:
            if hasattr(f, "setDecimalPlaces"):
                f.setDecimalPlaces(places)

    def setDpi(self, dpi: int):
        self._dpi = dpi
        for f in self._rows:
            if hasattr(f, "setDpi"):
                f.setDpi(dpi)
