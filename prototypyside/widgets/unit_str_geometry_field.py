from PySide6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout, QFormLayout
)
from PySide6.QtCore import Signal, Slot
from typing import Optional, Any, Dict, List

# Your UnitStr stack
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.models.component_element import ComponentElement
# Treat UnitField as the UnitStr-aware field widget
from prototypyside.widgets.unit_str_field import UnitStrField


class UnitStrGeometryField(QWidget):
    """
    Edits a UnitStrGeometry using UnitStr-aware fields for W/H/(X/Y).
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
        self._old_geometry: Optional[UnitStrGeometry] = None
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

        # UnitStr fields
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

    def setTarget(self, target_item: Any, property_name: str, display_unit: Optional[str]):
        self.target_item = target_item
        self.property_name = property_name
        self._display_unit = display_unit or self._display_unit

        # Set each subfield’s display unit + dpi (use target dpi if available)
        tgt_dpi = getattr(self.target_item, "dpi", None)
        for f in self._fields.values():
            f.display_unit = self._display_unit or f.display_unit
            # force dpi (UnitField relies on having a dpi)
            f._dpi = tgt_dpi if tgt_dpi is not None else (f._dpi or 96)

        # keep UI in sync with the element (if provided)
        if isinstance(self.target_item, ComponentElement):
            try:
                self.target_item.item_changed.connect(self.update_from_item)
            except Exception:
                pass

        self.update_from_item()

    def on_unit_change(self, display_unit: str):
        self._display_unit = display_unit
        # propagate to subfields
        for f in self._fields.values():
            f.on_unit_change(display_unit)
        self.update_from_item()

    def update_from_item(self):
        if not (self.target_item and self.property_name):
            self._clear_fields()
            return
        geom = getattr(self.target_item, self.property_name, None)
        self._update_display(geom if isinstance(geom, UnitStrGeometry) else None)

    # ---------------- display helpers ----------------

    def _update_display(self, geom: Optional[UnitStrGeometry]):
        if not isinstance(geom, UnitStrGeometry):
            self._clear_fields()
            return
        self._old_geometry = geom
        # feed UnitStrs directly into fields (UnitField handles formatting)
        self._fields["width"].setTextFromValue(geom.width)
        self._fields["height"].setTextFromValue(geom.height)
        if "x" in self._fields:
            self._fields["x"].setTextFromValue(geom.pos_x)
        if "y" in self._fields:
            self._fields["y"].setTextFromValue(geom.pos_y)

    def _clear_fields(self):
        for f in self._fields.values():
            f.clear()
        self._old_geometry = None

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
            # Pull UnitStrs from the UnitFields directly
            w_us = self._fields["width"].value()
            h_us = self._fields["height"].value()
            if "x" in self._fields and "y" in self._fields:
                x_us = self._fields["x"].value()
                y_us = self._fields["y"].value()
            else:
                x_fallback, y_fallback = self._fallback_pos_from_target()
                x_us, y_us = x_fallback, y_fallback

            # Rewrap to target dpi / display unit (UnitStr can take a UnitStr)
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

# from PySide6.QtWidgets import (
#     QWidget, QLabel, QHBoxLayout, QVBoxLayout, QFormLayout
# )
# from PySide6.QtCore import Signal, Slot
# from typing import Optional, Any, Dict, List

# # Your UnitStr stack
# from prototypyside.utils.units.unit_str import UnitStr
# from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
# from prototypyside.models.component_element import ComponentElement
# # Treat UnitStrField as the UnitStr-aware field widget
# from prototypyside.widgets.unit_str_field import UnitStrField


# class UnitStrGeometryField(QWidget):
#     """
#     Edits a UnitStrGeometry using UnitStr-aware fields for W/H/(X/Y).
#     labels: ['width','height'] or ['width','height','x','y']
#     If only W/H are present, X/Y are pulled from the target (rect_x/rect_y or x/y).
#     Layout is customizable via box_cls (row) and stack_cls (overall).
#     """
#     valueChanged = Signal(object, str, object, object)  # (target, prop, new_USG, old_USG)

#     def __init__(
#         self,
#         target_item: Optional[Any] = None,
#         property_name: Optional[str] = None,
#         display_unit: Optional[str] = None,
#         parent: Optional[QWidget] = None,
#         *,
#         labels: Optional[List[str]] = None,
#         is_pos: bool = False,
#         decimal_places: int = 4,
#         box_cls=QHBoxLayout,   # orientation for each label+field pair
#         stack_cls=QVBoxLayout  # how rows are stacked
#     ):
#         super().__init__(parent)
#         self.target_item: Optional[Any] = None
#         self.property_name: Optional[str] = None
#         self._old_geometry: Optional[UnitStrGeometry] = None
#         self._display_unit: Optional[str] = display_unit
#         self._decimal_places: int = decimal_places
#         self._is_pos: bool = is_pos
#         self._box_cls = box_cls
#         self._stack_cls = stack_cls

#         # normalize requested labels
#         lbls = [s.strip().lower() for s in (labels or ["width", "height", "x", "y"])]
#         if len(lbls) not in (2, 4):
#             raise ValueError("labels must have length 2 or 4")
#         self._labels = ["width", "height"] if len(lbls) == 2 else ["width", "height", "x", "y"]

#         # stack layout containing per-row boxes
#         self._stack = self._stack_cls(self)
#         self._stack.setContentsMargins(0, 0, 0, 0)
#         self._stack.setSpacing(6)
#         self.setLayout(self._stack)

#         # UnitStr fields
#         self._fields: Dict[str, UnitStrField] = {}

#         def add_pair(key: str, title: str):
#             row_container = QWidget(self)
#             row = self._box_cls(row_container)
#             row.setContentsMargins(0, 0, 0, 0)
#             row.setSpacing(6)
#             row_container.setLayout(row)

#             lab = QLabel(title, row_container)
#             fld = UnitStrField(
#                 target_item=None,            # standalone; we manage target/dpi
#                 property_name=None,          # standalone; avoid auto-emits
#                 display_unit=self._display_unit or "px",
#                 parent=row_container,
#                 decimal_places=self._decimal_places,
#             )
#             lab.setBuddy(fld)

#             # make field expand; label stays compact
#             try:
#                 row.addWidget(lab, 0)
#                 row.addWidget(fld, 1)
#                 if hasattr(row, "setStretch"):
#                     row.setStretch(0, 0)
#                     row.setStretch(1, 1)
#             except TypeError:
#                 # e.g., QFormLayout
#                 if isinstance(row, QFormLayout):
#                     row.addRow(lab, fld)
#                 else:
#                     row.addWidget(lab)
#                     row.addWidget(fld)

#             # listen to the field finishing edits; we’ll aggregate and emit once
#             fld.editingFinished.connect(self._on_editing_finished)

#             self._fields[key] = fld
#             self._stack.addWidget(row_container)

#         # Build rows in canonical order
#         add_pair("width",  "Width")
#         add_pair("height", "Height")
#         if len(self._labels) == 4:
#             add_pair("x", "X")
#             add_pair("y", "Y")

#         if target_item and property_name:
#             self.setTarget(target_item, property_name, display_unit=display_unit)

#     # ---------------- target / display unit ----------------

#     def setTarget(self, target_item: Any, property_name: str, display_unit: Optional[str]):
#         self.target_item = target_item
#         self.property_name = property_name
#         self._display_unit = display_unit or self._display_unit

#         # Set each subfield’s display unit + dpi (use target dpi if available)
#         tgt_dpi = getattr(self.target_item, "dpi", None)
#         for f in self._fields.values():
#             f.display_unit = self._display_unit or f.display_unit
#             # force dpi (UnitStrField relies on having a dpi)
#             f._dpi = tgt_dpi if tgt_dpi is not None else (f._dpi or 96)

#         # keep UI in sync with the element (if provided)
#         if isinstance(self.target_item, ComponentElement):
#             try:
#                 self.target_item.item_changed.connect(self.update_from_item)
#             except Exception:
#                 pass

#         self.update_from_item()

#     def on_unit_change(self, display_unit: str):
#         self._display_unit = display_unit
#         # propagate to subfields
#         for f in self._fields.values():
#             f.on_unit_change(display_unit)
#         self.update_from_item()

#     def update_from_item(self):
#         if not (self.target_item and self.property_name):
#             self._clear_fields()
#             return
#         geom = getattr(self.target_item, self.property_name, None)
#         self._update_display(geom if isinstance(geom, UnitStrGeometry) else None)

#     # ---------------- display helpers ----------------

#     def _update_display(self, geom: Optional[UnitStrGeometry]):
#         if not isinstance(geom, UnitStrGeometry):
#             self._clear_fields()
#             return
#         self._old_geometry = geom
#         # feed UnitStrs directly into fields (UnitStrField handles formatting)
#         self._fields["width"].setTextFromValue(geom.width)
#         self._fields["height"].setTextFromValue(geom.height)
#         if "x" in self._fields:
#             self._fields["x"].setTextFromValue(geom.pos_x)
#         if "y" in self._fields:
#             self._fields["y"].setTextFromValue(geom.pos_y)

#     def _clear_fields(self):
#         for f in self._fields.values():
#             f.clear()
#         self._old_geometry = None

#     def _fallback_pos_from_target(self) -> (UnitStr, UnitStr):
#         """Prefer rect_x/rect_y → pos_x/pos_y → x/y → 0."""
#         def as_unit(v) -> UnitStr:
#             if isinstance(v, UnitStr):
#                 return v
#             try:
#                 return UnitStr(float(v), unit="px", dpi=getattr(self.target_item, "dpi", 96))
#             except Exception:
#                 return UnitStr(0, unit="px", dpi=getattr(self.target_item, "dpi", 96))

#         for kx, ky in (("rect_x", "rect_y"), ("pos_x", "pos_y"), ("x", "y")):
#             vx, vy = getattr(self.target_item, kx, None), getattr(self.target_item, ky, None)
#             if vx is not None and vy is not None:
#                 return as_unit(vx), as_unit(vy)
#         return as_unit(0), as_unit(0)

#     # ---------------- commit ----------------

#     @Slot()
#     def _on_editing_finished(self):
#         if not self.target_item or not self.property_name or self._old_geometry is None:
#             self.clearFocus()
#             return

#         old = self._old_geometry
#         tgt_dpi = getattr(self.target_item, "dpi", old.dpi)
#         disp_unit = self._display_unit or old.unit

#         try:
#             # Pull UnitStrs from the UnitStrFields directly
#             w_us = self._fields["width"].value()
#             h_us = self._fields["height"].value()
#             if "x" in self._fields and "y" in self._fields:
#                 x_us = self._fields["x"].value()
#                 y_us = self._fields["y"].value()
#             else:
#                 x_fallback, y_fallback = self._fallback_pos_from_target()
#                 x_us, y_us = x_fallback, y_fallback

#             # Rewrap to target dpi / display unit (UnitStr can take a UnitStr)
#             new_geometry = UnitStrGeometry(
#                 width=UnitStr(w_us, unit=disp_unit, dpi=tgt_dpi),
#                 height=UnitStr(h_us, unit=disp_unit, dpi=tgt_dpi),
#                 x=UnitStr(x_us, unit=disp_unit, dpi=tgt_dpi),
#                 y=UnitStr(y_us, unit=disp_unit, dpi=tgt_dpi),
#                 unit=disp_unit,
#                 dpi=tgt_dpi,
#             )

#         except ValueError:
#             # revert UI on invalid input
#             self._update_display(old)
#             self.clearFocus()
#             return

#         # Emit once with the full geometry object
#         self.valueChanged.emit(self.target_item, self.property_name, new_geometry, old)

#         # Update local state & UI
#         self._old_geometry = new_geometry
#         self._update_display(new_geometry)
#         self.clearFocus()
