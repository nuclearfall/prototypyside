# file: template_property_panel.py
from typing import Optional, Any, List, Tuple, Union
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLabel, QLineEdit, QComboBox, QCheckBox,
    QVBoxLayout, QHBoxLayout, QFrame, QTextEdit, QPushButton, QFileDialog, QColorDialog, 
    QStackedWidget, QTextEdit, QSizePolicy)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont, QTextOption, QKeyEvent


# Assuming these modules are in the same directory or accessible via python path
from prototypyside.widgets.unit_str_field import UnitStrField
from prototypyside.widgets.unit_str_geometry_field import UnitStrGeometryField
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.models.component_template import SHAPES
from prototypyside.widgets.color_picker import ColorPickerWidget
from prototypyside.widgets.rotation_field import RotationField
from prototypyside.views.toolbars.font_toolbar import FontToolbar


class FocusLineEdit(QLineEdit):
    editingFinishedWithValue = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.returnPressed.connect(self.clearFocus)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.editingFinishedWithValue.emit(self.text())


class FocusTextEdit(QTextEdit):
    editingFinished = Signal(object, str, object, object)
    resized = Signal()  # <— add this

    def __init__(self, target_item=None, content_key="content", parent=None):
        super().__init__(parent)
        self.setWordWrapMode(QTextOption.WordWrap)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # wrapping; no horiz scroll
        # optional: let the widget shrink/grow vertically
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._content_key = content_key
        self._target_item = None
        self._original_value = None
        if target_item:
            self._target_item = target_item
            self._original_value = getattr(target_item, content_key, "")
            self.setText(self._original_value)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resized.emit()  # <— notify panel that width (hence wrap height) may have changed

    def focusOutEvent(self, event):
        """
        Overrides the focusOutEvent to emit a signal with the data.
        """
        new_value = self.toPlainText()
        if new_value != self._original_value:
            self.editingFinished.emit(self._target_item, self._content_key, new_value, self._original_value)
            self._original_value = new_value  # Update original value for next edit
        super().focusOutEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        """
        Overrides the keyPressEvent to clear focus on Enter/Return key press.
        """
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.clearFocus()
        else:
            super().keyPressEvent(event)

    def setTarget(self, target_item, content_key="content"):
        """
        Sets the target item and content key for the widget.
        """
        self._target_item = target_item
        self._content_key = content_key
        self._original_value = getattr(target_item, content_key, "")
        self.setText(self._original_value)


# --- Main Property Panel Widget ---

class ComponentPropertyPanel(QWidget):
    """
    A panel to display and edit properties of the ComponentTemplate.
    """
    # Emits (target_object, property_name, old_value, new_value)
    property_changed = Signal(object, str, object, object)

    def __init__(self, target, display_unit:str, dpi: int = 300, layout = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._target = target
        self._display_unit = display_unit
        self._connected_item = None
        self.dpi = dpi

        # Main layout
        # allow for QHBoxLayout for a psuedo-toolbar
        self.main_layout = layout if layout else QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)

        # A frame to hold the properties
        self.main_frame = QFrame()
        self.main_frame.setObjectName("propertyFrame")
        self.form_layout = QFormLayout(self.main_frame)
        self.form_layout.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.main_layout.addWidget(self.main_frame)

        # --- Create all possible widgets ---
        self.name_edit = QLabel(self._target.name)
        self.geometry_field = UnitStrGeometryField(target, "geometry", labels=["Width", "Height"], display_unit=display_unit, dpi=self.dpi)
        self.rotation_field = RotationField()
        self.bg_color_pick = ColorPickerWidget(target.bg_color)
        self.border_color_pick = ColorPickerWidget(target.border_color)
        self.border_width_field = UnitStrField(
            target_item=target,
            property_name="border_width", 
            display_unit=self._display_unit, 
            dpi=self.dpi
        )
        #self.shape = QComboBox(parent=self)
        #self.sides = FocusLineEdit(parent=self) 
        self.corner_radius_field = UnitStrField(
            target_item=target,
            property_name="corner_radius", 
            display_unit=self._display_unit, 
            dpi=self.dpi
        )
        self.bg_image_button = QPushButton("Select Image...") # For image path
        self.bg_image_button.setMaximumHeight(32)     

        # Add widgets to layout
        self.form_layout.addRow("Name:", self.name_edit)
        self.form_layout.addRow("Geometry:", self.geometry_field)
        self.form_layout.addRow("Rotation", self.rotation_field)
        hbox = QHBoxLayout()
        hbox.addWidget(QLabel("Background"))
        hbox.addWidget(self.bg_color_pick)
        hbox.addWidget(QLabel("Border"))
        hbox.addWidget(self.border_color_pick)
        self.form_layout.addRow(hbox)
        self.form_layout.addRow("Border Width:", self.border_width_field)
        self.form_layout.addRow("Corner Radius", self.corner_radius_field)
        self.form_layout.addRow("Background Image", self.bg_image_button)

        # self.ep_aspect_checkbox.setTristate(True)
        self._connect_signals()

    def _connect_signals(self):
        # Text: NAME (unique per item; usually we disable in multi)
        # self.name_edit.editingFinishedWithValue.connect(
        #     lambda value: self._handle_panel_edit("name", value)
        # )

        self.bg_image_button.clicked.connect(self._choose_image_path)

        # Geometry / numbers (we’ll translate these into batch/single)
        self.geometry_field.valueChanged.connect(
            lambda tgt, prop, new, old: self._handle_panel_edit(prop, new)
        )
        self.border_width_field.valueChanged.connect(
            lambda tgt, prop, new, old: self._handle_panel_edit(prop, new)
        )
        self.corner_radius_field.valueChanged.connect(
            lambda tgt, prop, new, old: self._handle_panel_edit(prop, new)
        )

        # Rotation preview/commit
        # self.rotation_field.editingFinished.connect(self._on_rotation_finished)
        # self.rotation_field.angleChanged.connect(self._preview_rotation_only)

        # Colors
        self.bg_color_pick.color_changed.connect(lambda c: self._handle_panel_edit("bg_color", c))
        self.border_color_pick.color_changed.connect(lambda c: self._handle_panel_edit("border_color", c))

        # # Keep aspect (tri-state)
        # self.keep_aspect_checkbox.stateChanged.connect(self._on_keep_aspect_state)

    # ---------------- Multi-select helpers ----------------
    def on_external_property_changed(self, item, prop: str, new_value):
        """
        Update only the relevant editors from an external change without emitting
        property_changed.
        """
        try:
            self.blockSignals(True)
            # Example — adjust to your field names:
            if prop == "name":
                self.name_edit.setText(self._target.name)
            if prop == "geometry" and hasattr(self, "geometry_field"):
                # If you support multi-target, pass the list of current targets
                self.geometry_field.update_from_item()  # UnitStrGeometry
            else:
                # Fallback full refresh
                self.refresh()
        finally:
            self.blockSignals(False)

    def refresh_selected(self):
        """Lightweight refresh from current targets (no signal emissions)."""
        try:
            self.blockSignals(True)
            self.refresh()
        finally:
            self.blockSignals(False)

    def _emit_property_change(self, prop_name: str, new_value: Any):
        """Emit property_changed for template."""
        tgt = self._target
        old_value = getattr(tgt, prop_name, None)
        if old_value != new_value:
            self.property_changed.emit(tgt, prop_name, new_value, old_value)
        return

    def _populate_fields(self):
        """
        Populate UI from current selection (single or multi),
        showing common values or mixed indicators.
        """
        item = self._target
        if not item:
            return

        # Name: typically unique — disable on multi to avoid unintended rename
        self.name_edit.setText(item, "name", "")
        self.geometry_field.setTarget(item, "geometry", display_unit=self._display_unit)

        # self.rotation_field.setAngle(float(common_rot), emit_signal=False)
        # else:
        #     self.rotation_field.setAngle(0.0, emit_signal=False)  # neutral display
        #     # keep enabled so user can set unified rotation

        # Colors
        def put_color(widget, prop):
            same, val = self._all_same(prop)
            if same:
                widget.set_color(val)
            else:
                widget.set_color(None)  # show "no color"/mixed

        put_color(self.bg_color_pick, "bg_color")
        put_color(self.border_color_pick, "border_color")

        # Border width / corner radius
        def put_unit_field(field, prop):
            same, val = self._all_same(prop)
            if same and val is not None:
                field.setTarget(item, prop, display_unit=self._display_unit)
            else:
                field.setTarget(None, None)   # break binding
                field.setPlaceholderText(self._mixed_label())

        put_unit_field(self.border_width_field, "border_width")
        put_unit_field(self.corner_radius_field, "corner_radius")

        # # Keep Aspect (only if all selected support it)
        # keep_aspectables = [it for it in items if hasattr(it, "keep_aspect")]
        # if keep_aspectables and len(keep_aspectables) == len(items):
        #     same, val = self._all_same("keep_aspect", keep_aspectables)
        #     self.keep_aspect_checkbox.setVisible(True)
        #     if same:
        #         self.keep_aspect_checkbox.setCheckState(Qt.Checked if bool(val) else Qt.Unchecked)
        #     else:
        #         self.keep_aspect_checkbox.setCheckState(Qt.PartiallyChecked)
        # else:
        #     self.keep_aspect_checkbox.setVisible(False)

 # -------------- single/multi edit routing --------------

    def _handle_panel_edit(self, prop_name: str, new_value: Any):
        """Central router for edits coming from widgets."""
        if not self._target:
            return
        self._emit_property_change(prop_name, new_value)

    # --- existing slots adapted to route through _emit_property_change ---

    @Slot()
    def _choose_image_path(self):
        # Applies to images or vectors; in multi we batch-apply
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select File", "", "Images (*.png *.jpg *.bmp *.gif);;SVG Files (*.svg)"
        )
        if file_path:
            self._emit_property_change("bg_image", file_path)

    # @Slot()
    # def _on_rotation_finished(self):
    #     new_value = float(self.rotation_field.angle())
    #     self._emit_property_change("rotation", new_value)

    # @Slot(float)
    # def _preview_rotation_only(self, v):
    #     # Preview only, do not emit (same as your original)
    #     if not self._targets:
    #         return
    #     try:
    #         for t in self._targets:
    #             if hasattr(t, "rotation"):
    #                 t.rotation = float(v)
    #                 if hasattr(t, "element_changed"):
    #                     t.element_changed.emit()
    #     except Exception:
    #         pass

    # @Slot(int)
    # def _on_keep_aspect_state(self, state: int):
    #     if not self._targets:
    #         return
    #     if state == Qt.PartiallyChecked:
    #         return  # user hasn’t committed a concrete state yet
    #     self._emit_property_change("keep_aspect", state == Qt.Checked)

    # ---------------- bind / clear ----------------

    def clear_target(self):
        self.set_target(None)

    def set_target(self, item: Optional[Union[object, List[object]]]):
        """Accept single object, list of objects, or None."""
        # Normalize
        target = item
        if item is None:
            target = None

        # If same set, just refresh visuals
        self._populate_fields() if target else self._reset_fields()
        self.set_panel_enabled(bool(target))

        self._block_all(True)
        self._disconnect_from_item()  # legacy single-item connection
        self._target = target

        if not targets:
            self._reset_fields()
            self.set_panel_enabled(False)
            self._block_all(False)
            return

        # For legacy updates we keep listening to the first item’s change signal.
        # In multi-select, you’ll likely refresh via external selectionChanged anyway.
        self._connect_to_item(targets[0])
        self.set_panel_enabled(True)
        self._populate_fields()
        self._block_all(False)

    def set_panel_enabled(self, enabled: bool):
        # You can disable just the form container instead of the entire dock
        self.main_frame.setEnabled(enabled)

    # --- Helpers ---------------------------------------------------------------

    def _block_all(self, block: bool):
        for w in self.main_frame.findChildren(QWidget):
            try:
                w.blockSignals(block)
            except Exception:
                pass

    def _reset_fields(self):
        # Safely clear text/fields that may not accept None gracefully
        self.name_edit.clear()
        self.geometry_field.clear()
        self.bg_color_pick.set_color(None)
        self.border_color_pick.set_color(None)

        self.border_width_field.clear()
        self.corner_radius_field.clear()

        # Rotation back to 0, but do NOT emit change
        # try:
        #     self.rotation_field.setAngle(0.0, emit_signal=False)
        # except Exception:
        #     pass

        self.keep_aspect_checkbox.setVisible(False)
        self.keep_aspect_checkbox.setChecked(False)

    # ---------- internal helpers ----------
    def _connect_to_item(self, item):
        """Connect directly to a stable instance method."""
        if self._connected_item is item:
            return
        self._disconnect_from_item()  # ensure previous is gone

        if item is None:
            return

        # Connect the item's changed signal directly to our update slot
        if hasattr(item, "template_changed"):
            item.item_changed.connect(self.refresh, Qt.UniqueConnection)
            self._connected_item = item

    def _disconnect_from_item(self):
        """Disconnect the stable instance method."""
        if self._connected_item and hasattr(self._connected_item, "item_changed"):
            try:
                # Disconnect the same method we connected
                self._connected_item.item_changed.disconnect(self.refresh)
            except (TypeError, RuntimeError):
                # This can happen if the item was destroyed; it's safe to ignore.
                pass
        self._connected_item = None

    # ---------- public bind/clear ----------

    def clear_target(self):
        """Completely unbinds, clears, and disables the panel."""
        self.set_target(None)

    # ---------- slots / updates ----------
    @Slot(str)
    def on_unit_change(self, display_unit: str):
        """
        Switch display units (e.g., 'px' -> 'in'). For multi-selection:
        - If all share the property, bind to the first (to show the common value).
        - If mixed, unbind and show a neutral/mixed placeholder, but keep enabled
          so the user can enter a unified value (applies to all).
        """
        self._display_unit = display_unit
        if not self._target:
            return
        for fld in [geometry_field, corner_radius_field, border_width_field]:
            fld.on_unit_change(display_unit=self._display_unit)
        self.border_width_field.on_unit_change(display_unit=self._display_unit)


    # --- Keep only ONE refresh; make it multi-aware and lightweight ---
    @Slot()
    def refresh(self):
        """
        Re-populate the panel from current targets.
        (Call this when any selected item emits its change signal, or when the
        selection changes.)
        """
        if self._target:
            self._populate_fields()
        else:
            # Nothing selected; reset
            self._reset_fields()
            self.set_panel_enabled(False)

    def _update_display(self, geom: Optional[UnitStrGeometry]):
        if not isinstance(geom, UnitStrGeometry):
            self._clear_fields()
            return
        self._old_geometry = geom

        # Block signals; explicitly set text
        def put(key, val):
            if key in self._fields and val is not None:
                f = self._fields[key]
                try:
                    f.blockSignals(True)
                    f.setTextFromValue(val)
                finally:
                    f.blockSignals(False)

        put("width",  getattr(geom, "width",  None))
        put("height", getattr(geom, "height", None))


    def _clear_fields(self):
        self._fields.clear()
        self._old_geometry = None