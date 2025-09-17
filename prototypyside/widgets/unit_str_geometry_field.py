from contextlib import suppress
from PySide6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout, QFormLayout
)
from PySide6.QtCore import Signal, Slot
from typing import Optional, Any, Dict, List

# Treat UnitField as the ProtoClass.US-aware field widget
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.widgets.unit_str_field import UnitStrField


class UnitStrGeometryField(QWidget):
    """
    Edits a UnitStrGeometry using ProtoClass.US-aware fields for W/H/(X/Y).
    labels: ['width','height'] or ['width','height','x','y']
    If only W/H are present, X/Y are pulled from the target (rect_x/rect_y or x/y).
    Layout is customizable via box_cls (row) and stack_cls (overall).
    """
    valueChanged = Signal(object, str, object, object)  # (target, prop, new_USG, old_USG)

    def __init__(
        self,
        target_item: Optional[Any] = None,
        property_name: Optional[str] = None,
        display_unit: Optional[str] = None,
        parent: Optional[QWidget] = None,
        *,
        labels: Optional[List[str]] = None,
        is_pos: bool = False,
        decimal_places: int = 4,
        box_cls=QHBoxLayout,   # orientation for each label+field pair
        stack_cls=QVBoxLayout, # how rows are stacked
        dpi = 300
    ):
        super().__init__(parent)
        self.target_item: Optional[Any] = None
        self.property_name: Optional[str] = None
        self._old_geometry: Optional["UnitStrGeometry"] = None
        self._display_unit: Optional[str] = display_unit
        self._decimal_places: int = decimal_places
        self._is_pos: bool = is_pos
        self._box_cls = box_cls
        self._stack_cls = stack_cls
        self._dpi = dpi

        # normalize requested labels
        lbls = [s.strip().lower() for s in (labels or ["width", "height", "x", "y"])]
        if len(lbls) not in (2, 4):
            raise ValueError("labels must have length 2 or 4")
        self._labels = ["width", "height"] if len(lbls) == 2 else ["width", "height", "x", "y"]

        # stack layout containing per-row boxes
        self._stack = self._stack_cls(self)
        self._stack.setContentsMargins(0, 0, 0, 0)
        self._stack.setSpacing(6)
        self.setLayout(self._stack)

        # ProtoClass.US fields
        self._fields: Dict[str, UnitStrField] = {}

        def add_pair(key: str, title: str):
            row_container = QWidget(self)
            row = self._box_cls(row_container)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            row_container.setLayout(row)

            lab = QLabel(title, row_container)
            fld = UnitStrField(
                target_item=None,            # standalone; we manage target/dpi
                property_name=None,          # standalone; avoid auto-emits
                display_unit=self._display_unit or "px",
                parent=row_container,
                decimal_places=self._decimal_places,
                dpi=self._dpi,
            )
            lab.setBuddy(fld)

            # make field expand; label stays compact
            try:
                row.addWidget(lab, 0)
                row.addWidget(fld, 1)
                if hasattr(row, "setStretch"):
                    row.setStretch(0, 0)
                    row.setStretch(1, 1)
            except TypeError:
                # e.g., QFormLayout
                if isinstance(row, QFormLayout):
                    row.addRow(lab, fld)
                else:
                    row.addWidget(lab)
                    row.addWidget(fld)

            # listen to the field finishing edits; we’ll aggregate and emit once
            fld.editingFinished.connect(self._on_editing_finished)

            self._fields[key] = fld
            self._stack.addWidget(row_container)

        # Build rows in canonical order
        add_pair("width",  "Width")
        add_pair("height", "Height")
        if len(self._labels) == 4:
            add_pair("x", "X")
            add_pair("y", "Y")

        if target_item and property_name:
            self.setTarget(target_item, property_name, display_unit=display_unit)

    # ---------------- target / display unit ----------------
    # In unit_str_geometry_field.py, modify the clearTarget method
    def clearTarget(self, clear_ui=True, disable=False):
        """Unbind composite, ask children to clear themselves, and disable the composite."""
        # Disconnect composite from previous target
        prev = getattr(self, "target_item", None)
   
        self.target_item = None
        self.property_name = None
        self._old_geometry = None
        
        # Delegate to each UnitStrField (UI clear, do NOT disable children permanently)
        for f in self._fields.values():
            with suppress(Exception):
                # let the field clear its own target & UI; don't disable the child
                f.clearTarget(clear_ui=True, disable=False)
        
        # Disable only the composite to signal "no selection"
        if hasattr(self, "setEnabled"):
            self.setEnabled(False)

    def clear(self):
        self.clearTarget(clear_ui=True, disable=False)

    def setTarget(self, target_item, property_name, display_unit=None):
        if not target_item or not property_name:
            if display_unit:
                self._display_unit = display_unit
            self.clearTarget()
            return

        # Disconnect from old target if different
        if self.target_item is not None and self.target_item is not target_item:
            with suppress(Exception):
                if hasattr(self.target_item, "item_changed"):
                    self.target_item.item_changed.disconnect(self.update_from_item)

        self.target_item = target_item
        self.property_name = property_name
        if display_unit:
            self._display_unit = display_unit

        # Re-enable composite and children; propagate display unit & DPI
        if hasattr(self, "setEnabled"):
            self.setEnabled(True)

        tgt_dpi = getattr(self.target_item, "dpi", None)
        for f in self._fields.values():
            with suppress(Exception):
                if hasattr(f, "setEnabled"):
                    f.setEnabled(True)  # in case a child was previously disabled
                if hasattr(f, "setDisplayUnit") and self._display_unit:
                    f.setDisplayUnit(self._display_unit)
                if hasattr(f, "setDpi"):
                    f.setDpi(tgt_dpi if tgt_dpi is not None else getattr(f, "_dpi", 96))

        # Connect composite to target signals (single connection)
        with suppress(Exception):
            if hasattr(self.target_item, "item_changed"):
                self.target_item.item_changed.connect(self.update_from_item)

        self.update_from_item()

    def on_unit_change(self, display_unit: str):
        self._display_unit = display_unit
        for f in self._fields.values():
            # Prefer explicit unit-change API if present
            if hasattr(f, "on_unit_change"):
                f.on_unit_change(display_unit)
            elif hasattr(f, "setDisplayUnit"):
                f.setDisplayUnit(display_unit)
        self.update_from_item()

    def update_from_item(self):
        # When unbound, ensure fields clear and stay disabled
        if not (self.target_item and self.property_name):
            self.clear()
            self.setEnabled(False)
            return

        self.setEnabled(True)  # we have a target
        geom = getattr(self.target_item, self.property_name, None)
        self._update_display(geom if isinstance(geom, UnitStrGeometry) else None)

    # ---------------- display helpers ----------------

    def _update_display(self, geom):
        if not isinstance(geom, UnitStrGeometry):
            # ask children to clear themselves (UI only)
            for f in self._fields.values():
                with suppress(Exception):
                    f.clearTarget(clear_ui=True, disable=False)
            self._old_geometry = None
            return

        self._old_geometry = geom
        mapping = [
            ("width",  getattr(geom, "width", None)),
            ("height", getattr(geom, "height", None)),
        ]
        if "x" in self._fields and "y" in self._fields:
            mapping += [
                ("x", getattr(geom, "pos_x", getattr(geom, "x", None))),
                ("y", getattr(geom, "pos_y", getattr(geom, "y", None))),
            ]

        for key, val in mapping:
            f = self._fields.get(key)
            if not f:
                continue
            with suppress(Exception):
                if hasattr(f, "blockSignals"):
                    f.blockSignals(True)
                try:
                    if val is None:
                        f.clearTarget(clear_ui=True, disable=False)
                    else:
                        if hasattr(f, "setTextFromValue"):
                            f.setTextFromValue(val)
                        elif hasattr(f, "setText"):
                            f.setText(str(val))
                finally:
                    if hasattr(f, "blockSignals"):
                        f.blockSignals(False)

    def _fallback_pos_from_target(self) -> (UnitStr, UnitStr):
        """Prefer rect_x/rect_y → pos_x/pos_y → x/y → 0."""
        def as_unit(v) -> UnitStr:
            if isinstance(v, UnitStr):
                return v
            try:
                return UnitStr(float(v), unit="px", dpi=getattr(self.target_item, "dpi", 96))
            except Exception:
                return UnitStr(0, unit="px", dpi=getattr(self.target_item, "dpi", 96))

        for kx, ky in (("rect_x", "rect_y"), ("pos_x", "pos_y"), ("x", "y")):
            vx, vy = getattr(self.target_item, kx, None), getattr(self.target_item, ky, None)
            if vx is not None and vy is not None:
                return as_unit(vx), as_unit(vy)
        return as_unit(0), as_unit(0)

    # ---------------- commit ----------------

    @Slot()
    def _on_editing_finished(self):
        if not self.target_item or not self.property_name or self._old_geometry is None:
            self.clearFocus()
            return

        old = self._old_geometry
        tgt_dpi = getattr(self.target_item, "dpi", old.dpi)
        disp_unit = self._display_unit or old.unit

        try:
            # Pull ProtoClass.USs from the UnitFields directly
            w_us = max(self._fields["width"].value(), UnitStr("1px", dpi=tgt_dpi))
            h_us = max(self._fields["height"].value(), UnitStr("1px", dpi=tgt_dpi))
            if "x" in self._fields and "y" in self._fields:
                x_us = self._fields["x"].value()
                y_us = self._fields["y"].value()
            else:
                x_fallback, y_fallback = self._fallback_pos_from_target()
                x_us, y_us = x_fallback, y_fallback

            # Rewrap to target dpi / display unit (ProtoClass.US can take a ProtoClass.US)
            new_geometry = UnitStrGeometry(
                width=UnitStr(w_us, unit=disp_unit, dpi=tgt_dpi),
                height=UnitStr(h_us, unit=disp_unit, dpi=tgt_dpi),
                x=UnitStr(x_us, unit=disp_unit, dpi=tgt_dpi),
                y=UnitStr(y_us, unit=disp_unit, dpi=tgt_dpi),
                unit=disp_unit,
                dpi=tgt_dpi,
            )

        except ValueError:
            # revert UI on invalid input
            self._update_display(old)
            self.clearFocus()
            return

        # Emit once with the full geometry object
        self.valueChanged.emit(self.target_item, self.property_name, new_geometry, old)

        # Update local state & UI
        self._old_geometry = new_geometry
        self._update_display(new_geometry)
        self.clearFocus()

    # Optional helpers
    def setDisplayUnit(self, unit: str):
        self._display_unit = unit
        for f in self._fields.values():
            f.setDisplayUnit(unit)

    def setDecimalPlaces(self, places: int):
        self.decimal_places = places
        for f in self._fields.values():
            f.setDecimalPlaces(places)

    def setDpi(self, dpi: int):
        self._dpi = dpi
        for f in self._fields.values():
            f.setDpi(dpi)