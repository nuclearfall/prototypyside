# file: property_panel.py
from typing import Optional, Any, List, Tuple, Union
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLabel, QLineEdit, QComboBox, QCheckBox,
    QVBoxLayout, QFrame, QTextEdit, QPushButton, QFileDialog, QColorDialog, 
    QStackedWidget, QTextEdit, QSizePolicy)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont, QTextOption, QKeyEvent


# Assuming these modules are in the same directory or accessible via python path
from prototypyside.widgets.unit_str_field import UnitStrField
from prototypyside.widgets.unit_str_geometry_field import UnitStrGeometryField
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.models.text_element import TextElement
from prototypyside.models.image_element import ImageElement
from prototypyside.models.vector_element import VectorElement
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

# class FocusTextEdit(QTextEdit):
#     """
#     A custom QTextEdit widget with word wrap that emits a signal on losing focus.

#     The signal `editingFinished` carries the target_item, the content key, the new
#     text value, and the old text value.
#     """
#     editingFinished = Signal(object, str, object, object)

#     def __init__(self, target_item=None, content_key="content", parent=None):
#         super().__init__(parent)
#         self.setWordWrapMode(QTextOption.WordWrap)
#         self._content_key = content_key
#         self._target_item = None
#         self._original_value = None
#         if target_item:
#             self._target_item = target_item
#             self._original_value = getattr(target_item, content_key, "")
#             self.setText(self._original_value)
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

class PropertyPanel(QWidget):
    """
    A panel to display and edit properties of a selected ComponentElement.
    """
    # Emits (target_object, property_name, old_value, new_value)
    property_changed = Signal(object, str, object, object)
    batch_property_changed = Signal(list, str, object, list)

    def __init__(self, target, display_unit:str, dpi: int = 300, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._targets: List[object] = []
        if target is not None:
            self._targets = target if isinstance(target, list) else [target]

        self._display_unit = display_unit
        self._connected_item = None
        self.dpi = dpi

        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self._content_text_max_height_px = 100
        self.setLayout(self.main_layout)

        # A frame to hold the properties
        self.main_frame = QFrame()
        self.main_frame.setObjectName("propertyFrame")
        self.form_layout = QFormLayout(self.main_frame)
        self.form_layout.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.main_layout.addWidget(self.main_frame)

        # --- Create all possible widgets ---
        self.name_edit = FocusLineEdit()

        # Content widgets in a stacked layout
        self.content_stack = QStackedWidget()
        self.content_text_edit = FocusTextEdit()

        self.content_path_button = QPushButton("Select Image...") # For image path
        self.content_path_button.setMaximumHeight(32)
        self.content_stack.addWidget(self.content_text_edit)
        self.content_stack.addWidget(self.content_path_button)

        self.content_stack.setMinimumHeight(self._content_text_max_height_px)
        self.content_stack.setMaximumHeight(self._content_text_max_height_px)
        self.geometry_field = UnitStrGeometryField(target, "geometry", labels=["Width", "Height", "X", "Y"], display_unit=display_unit, dpi=self.dpi)
        self.rotation_field = RotationField()
        self.color_picker = ColorPickerWidget()
        self.bg_color_picker = ColorPickerWidget()
        self.border_color_picker = ColorPickerWidget()
        self.border_width_field = UnitStrField(property_name="border_width", display_unit=display_unit, dpi=self.dpi)
        self.corner_radius_field = UnitStrField(property_name="corner_radius", display_unit=display_unit, dpi=self.dpi)     
        self.font_toolbar = FontToolbar()

        # Conditional widgets

        self.keep_aspect_checkbox = QCheckBox("Keep Aspect Ratio")

        # Add widgets to layout
        self.form_layout.addRow("Name:", self.name_edit)
        self.form_layout.addRow("Content:", self.content_stack)
        self.form_layout.addRow("Geometry:", self.geometry_field)
        self.form_layout.addRow("Rotation", self.rotation_field)
        self.form_layout.addRow("Color:", self.color_picker)
        self.form_layout.addRow("Background Color:", self.bg_color_picker)
        self.form_layout.addRow("Border Color:", self.border_color_picker)
        self.form_layout.addRow("Border Width:", self.border_width_field)
        self.form_layout.addRow("Corner Radius", self.corner_radius_field)
        self.form_layout.addRow(self.font_toolbar)
        self.form_layout.addRow(self.keep_aspect_checkbox)

        self.keep_aspect_checkbox.setTristate(True)

        self._connect_signals()
        self.clear_target()


    def _connect_signals(self):
        # Text: NAME (unique per item; usually we disable in multi)
        self.name_edit.editingFinishedWithValue.connect(
            lambda value: self._handle_panel_edit("name", value)
        )

        # Content text (TextElement). We’ll re-route through _handle_panel_edit
        self.content_text_edit.editingFinished.connect(
            lambda tgt, key, new, old: self._handle_panel_edit(key, new)
        )
        self.content_text_edit.resized.connect(self._autosize_content_text_edit)

        self.content_path_button.clicked.connect(self._choose_image_path)

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
        self.rotation_field.editingFinished.connect(self._on_rotation_finished)
        self.rotation_field.angleChanged.connect(self._preview_rotation_only)

        # Colors
        self.color_picker.color_changed.connect(lambda c: self._handle_panel_edit("color", c))
        self.bg_color_picker.color_changed.connect(lambda c: self._handle_panel_edit("bg_color", c))
        self.border_color_picker.color_changed.connect(lambda c: self._handle_panel_edit("border_color", c))

        # Keep aspect (tri-state)
        self.keep_aspect_checkbox.stateChanged.connect(self._on_keep_aspect_state)

        # Font toolbar (Text-only)
        self.font_toolbar.fontChanged.connect(lambda tgt, prop, new, old: self._handle_panel_edit(prop, new))
        self.font_toolbar.hAlignChanged.connect(lambda tgt, prop, new, old: self._handle_panel_edit(prop, new))
        self.font_toolbar.vAlignChanged.connect(lambda tgt, prop, new, old: self._handle_panel_edit(prop, new))

    # def _enable_panel(self):
    #     # Important: enable the whole ancestry chain
    #     w = self
    #     while w is not None:
    #         if not w.isEnabled():
    #             w.setEnabled(True)
    #         w = w.parentWidget()

    # def _disable_panel(self):
    #     self.setDisabled(True)

    def _autosize_content_text_edit(self):
        """
        Resize the QTextEdit to its content height (wrap-aware), clamped to a max height.
        """
        te = self.content_text_edit
        if te is None or te.isHidden():
            return

        # 1) ensure document knows its wrapping width
        #    (use the viewport width; that’s where text actually wraps)
        viewport_w = te.viewport().width()
        if viewport_w <= 0:
            return  # nothing to do yet (not laid out)

        doc = te.document()
        # Setting textWidth makes documentLayout().documentSize() reflect wrapped height
        doc.setTextWidth(viewport_w)

        # 2) measure content height
        size = doc.documentLayout().documentSize()
        content_h = int(size.height())

        # account for internal margins + frame
        margins = te.contentsMargins()
        frame = int(te.frameWidth()) * 2
        total_h = content_h + int(margins.top() + margins.bottom()) + frame

        # 3) clamp to max
        max_h = int(self._content_text_max_height_px)
        clamped = min(total_h, max_h)

        # 4) apply
        #    Minimum so it grows to fit; Maximum so it won’t exceed cap.
        te.setMinimumHeight(clamped)
        te.setMaximumHeight(clamped)

        # scrollbars: if content is taller than cap, allow vertical scrolling
        if total_h > max_h:
            te.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        else:
            te.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    # ---------------- Multi-select helpers ----------------
    def on_external_property_changed(self, item, prop: str, new_value):
        """
        Update only the relevant editors from an external change without emitting
        property_changed/batch_property_changed.
        """
        try:
            self.blockSignals(True)
            # Example — adjust to your field names:
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

    def set_targets(self, items: List[object]):
        """Bind to multiple items at once."""
        self.set_target(items)  # alias

    def _is_multi(self) -> bool:
        return len(self._targets) > 1

    def _targets_of_type(self, cls) -> List[object]:
        return [t for t in self._targets if isinstance(t, cls)]

    def _all_same(self, prop: str, eligible: Optional[List[object]] = None) -> Tuple[bool, Any]:
        """Return (all_same, common_value or None)."""
        items = eligible if eligible is not None else self._targets
        if not items:
            return False, None
        vals = []
        for it in items:
            if not hasattr(it, prop):
                return False, None
            vals.append(getattr(it, prop))
        first = vals[0]
        for v in vals[1:]:
            if v != first:
                return False, None
        return True, first

    def _mixed_label(self) -> str:
        return "—"  # InDesign-style mixed indicator (you can choose "" if preferred)

    def _emit_single_or_batch(self, prop_name: str, new_value: Any):
        """Emit property_changed for single target or batch_property_changed for multi."""
        if not self._targets:
            return
        if not self._is_multi():
            tgt = self._targets[0]
            old_value = getattr(tgt, prop_name, None)
            if old_value != new_value:
                self.property_changed.emit(tgt, prop_name, new_value, old_value)
            return

        # Multi: collect olds, then emit batch
        olds = [getattr(t, prop_name, None) for t in self._targets]
        # Avoid no-op batches when every old equals new
        if all(o == new_value for o in olds):
            return
        self.batch_property_changed.emit(self._targets, prop_name, new_value, olds)

    def _populate_fields(self):
        """
        Populate UI from current selection (single or multi),
        showing common values or mixed indicators.
        """
        items = self._targets
        if not items:
            return

        # Common type subsets
        text_items = self._targets_of_type(TextElement)
        image_items = self._targets_of_type(ImageElement)
        vector_items = self._targets_of_type(VectorElement)

        # Name: typically unique — disable on multi to avoid unintended rename
        if self._is_multi():
            self.name_edit.setPlaceholderText(self._mixed_label())
            self.name_edit.setText("")
        else:
            el = items[0]
            self.name_edit.setText(getattr(el, "name", "") or "")

        # Geometry: show if all have same geometry; else show mixed and disable editor
        same_geom, common_geom = self._all_same("geometry")
        if same_geom and common_geom is not None:
            self.geometry_field.setTarget(items[0], "geometry", display_unit=self._display_unit)
        else:
            # neutral/mixed state
            self.geometry_field.setTarget(None, None)         
            # clear binding; user input applies to all
            # self.geometry_field.setPlaceholderText(self._mixed_label())

        # Rotation
        same_rot, common_rot = self._all_same("rotation")
        if same_rot and common_rot is not None:
            self.rotation_field.setAngle(float(common_rot), emit_signal=False)
        else:
            self.rotation_field.setAngle(0.0, emit_signal=False)  # neutral display
            # keep enabled so user can set unified rotation

        # Colors
        def put_color(widget, prop):
            same, val = self._all_same(prop)
            if same:
                widget.set_color(val)
            else:
                widget.set_color(None)  # show "no color"/mixed

        put_color(self.color_picker, "color")
        put_color(self.bg_color_picker, "bg_color")
        put_color(self.border_color_picker, "border_color")

        # Border width / corner radius
        def put_unit_field(field, prop):
            same, val = self._all_same(prop)
            if same and val is not None:
                field.setTarget(items[0], prop, display_unit=self._display_unit)
            else:
                field.setTarget(None, None)   # break binding
                field.setPlaceholderText(self._mixed_label())

        put_unit_field(self.border_width_field, "border_width")
        put_unit_field(self.corner_radius_field, "corner_radius")

        # Keep Aspect (only if all selected support it)
        keep_aspectables = [it for it in items if hasattr(it, "keep_aspect")]
        if keep_aspectables and len(keep_aspectables) == len(items):
            same, val = self._all_same("keep_aspect", keep_aspectables)
            self.keep_aspect_checkbox.setVisible(True)
            if same:
                self.keep_aspect_checkbox.setCheckState(Qt.Checked if bool(val) else Qt.Unchecked)
            else:
                self.keep_aspect_checkbox.setCheckState(Qt.PartiallyChecked)
        else:
            self.keep_aspect_checkbox.setVisible(False)

        # Content & font toolbar
        show_text_editor = len(text_items) == len(items) and len(items) > 0
        show_image_button = len(image_items) == len(items) and len(items) > 0
        show_vector_button = len(vector_items) == len(items) and len(items) > 0

        # Mutually exclusive stacks
        if show_text_editor:
            same_text, cv = self._all_same("content", text_items)
            self.content_stack.setCurrentWidget(self.content_text_edit)
            self.content_stack.setMaximumHeight(self._content_text_max_height_px)
            if same_text:
                self.content_text_edit.setTarget(text_items[0], "content")
                self.content_text_edit.setText(cv or "")
            else:
                self.content_text_edit.setTarget(None, "content")
                self.content_text_edit.setText("")  # neutral
                self.content_text_edit.setPlaceholderText(self._mixed_label())
            # Font toolbar (only for text)
            self.font_toolbar.setVisible(True)
            if self._is_multi():
                # If mixed, disbind toolbar and let applied changes be batch
                self.font_toolbar.setTarget(text_items[0] if same_text else None)
            else:
                self.font_toolbar.setTarget(text_items[0])
        elif show_image_button or show_vector_button:
            self.content_stack.setCurrentWidget(self.content_path_button)
            self.content_stack.setMaximumHeight(20)
            self.font_toolbar.setVisible(False)
        else:
            # Heterogeneous selection that doesn't share a content concept
            self.form_layout.labelForField(self.content_stack).hide()
            self.content_stack.hide()
            self.font_toolbar.setVisible(False)

 # -------------- single/multi edit routing --------------

    def _handle_panel_edit(self, prop_name: str, new_value: Any):
        """Central router for edits coming from widgets."""
        if not self._targets:
            return
        self._emit_single_or_batch(prop_name, new_value)

    # --- existing slots adapted to route through _emit_single_or_batch ---

    @Slot()
    def _choose_image_path(self):
        # Applies to images or vectors; in multi we batch-apply
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select File", "", "Images (*.png *.jpg *.bmp *.gif);;SVG Files (*.svg)"
        )
        if file_path:
            self._emit_single_or_batch("content", file_path)

    @Slot()
    def _on_rotation_finished(self):
        if not self._targets:
            return
        new_value = float(self.rotation_field.angle())
        self._emit_single_or_batch("rotation", new_value)

    @Slot(float)
    def _preview_rotation_only(self, v):
        # Preview only, do not emit (same as your original)
        if not self._targets:
            return
        try:
            for t in self._targets:
                if hasattr(t, "rotation"):
                    t.rotation = float(v)
                    if hasattr(t, "element_changed"):
                        t.element_changed.emit()
        except Exception:
            pass

    @Slot(int)
    def _on_keep_aspect_state(self, state: int):
        if not self._targets:
            return
        if state == Qt.PartiallyChecked:
            return  # user hasn’t committed a concrete state yet
        self._emit_single_or_batch("keep_aspect", state == Qt.Checked)

    # ---------------- bind / clear ----------------

    def clear_target(self):
        self.set_target(None)

    def set_target(self, item: Optional[Union[object, List[object]]]):
        """Accept single object, list of objects, or None."""
        # Normalize
        targets: List[object] = []
        if item is None:
            targets = []
        elif isinstance(item, list):
            targets = item
        else:
            targets = [item]

        # If same set, just refresh visuals
        if set(getattr(self, "_targets", [])) == set(targets):
            self._populate_fields() if targets else self._reset_common_fields()
            self.set_panel_enabled(bool(targets))
            return

        self._block_all(True)
        self._disconnect_from_item()  # legacy single-item connection
        self._targets = targets

        if not targets:
            self._reset_common_fields()
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



    def _reset_common_fields(self):
        # Safely clear text/fields that may not accept None gracefully
        self.name_edit.clear()
        try:
            self.content_text_edit.setText("")
        except Exception:
            pass
        # If your editors support unbinding, do it explicitly
        try:
            self.content_text_edit.setTarget(None, None)
        except Exception:
            pass
        try:
            self.geometry_field.clear()
        except Exception:
            pass

        # Colors to a neutral state (use whatever your app considers "no color")
        try:
            self.color_picker.set_color(None)
            self.bg_color_picker.set_color(None)
            self.border_color_picker.set_color(None)
        except Exception:
            pass

        # Border/geometry numeric fields—clear or set to defaults
        try:
            self.border_width_field.clear()
            # self.border_width_field.clear() # <- This line is redundant
        except Exception:
            pass
        try:
            self.corner_radius_field.clear()
            # self.corner_radius_field.clear() # <- This line is redundant
        except Exception:
            pass

        # Rotation back to 0, but do NOT emit change
        try:
            self.rotation_field.setAngle(0.0, emit_signal=False)
        except Exception:
            pass

        # Hide/clear optional toolbars & toggles
        try:
            self.font_toolbar.setVisible(False)
            # If your font_toolbar has unbind/clear, do it:
            if hasattr(self.font_toolbar, "setTarget"):
                self.font_toolbar.setTarget(None)
            if hasattr(self.font_toolbar, "clear"):
                self.font_toolbar.clear()
        except Exception:
            pass

        try:
            self.keep_aspect_checkbox.setVisible(False)
            self.keep_aspect_checkbox.setChecked(False)
        except Exception:
            pass

        # Restore content stack to a neutral state
        try:
            # Show the stack label again (since set_target may have hidden it)
            lbl = self.form_layout.labelForField(self.content_stack)
            if lbl:
                lbl.show()
            # Choose a default page; disabling is more important than which page
            self.content_stack.setCurrentIndex(0)
            self.content_stack.show()
        except Exception:
            pass

    # ---------- internal helpers ----------
    def _connect_to_item(self, item):
        """Connect directly to a stable instance method."""
        if self._connected_item is item:
            return
        self._disconnect_from_item()  # ensure previous is gone

        if item is None:
            return

        # Connect the item's changed signal directly to our update slot
        if hasattr(item, "item_changed"):
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
        if not self._targets:
            return

        # Geometry
        same_geom, common_geom = self._all_same("geometry")
        if same_geom and common_geom is not None:
            self.geometry_field.setTarget(self._targets[0], "geometry", display_unit=self._display_unit)
        else:
            self.geometry_field.setTarget(None, None)
            self.geometry_field.setPlaceholderText(self._mixed_label())

        # Border width
        same_bw, _ = self._all_same("border_width")
        if same_bw:
            self.border_width_field.setTarget(self._targets[0], "border_width", display_unit=self._display_unit)
        else:
            self.border_width_field.setTarget(None, None)
            self.border_width_field.setPlaceholderText(self._mixed_label())

        # Corner radius
        same_cr, _ = self._all_same("corner_radius")
        if same_cr:
            self.corner_radius_field.setTarget(self._targets[0], "corner_radius", display_unit=self._display_unit)
        else:
            self.corner_radius_field.setTarget(None, None)
            self.corner_radius_field.setPlaceholderText(self._mixed_label())


    # --- Keep only ONE refresh; make it multi-aware and lightweight ---
    @Slot()
    def refresh(self):
        """
        Re-populate the panel from current targets.
        (Call this when any selected item emits its change signal, or when the
        selection changes.)
        """
        if self._targets:
            self._populate_fields()
        else:
            # Nothing selected; reset
            self._reset_common_fields()
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
        put("x",      getattr(geom, "pos_x",  None))
        put("y",      getattr(geom, "pos_y",  None))

    def _clear_fields(self):
        self._fields.clear()
        self._old_geometry = None