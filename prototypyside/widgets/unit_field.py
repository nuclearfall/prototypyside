# unit_field.py

from PySide6.QtWidgets import QLineEdit, QWidget, QLabel, QGridLayout
from PySide6.QtCore import Signal, Slot
from typing import Optional, Any

# Assuming these are in a sibling directory or accessible via the python path
from prototypyside.models.component_element import ComponentElement
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry


class UnitField(QLineEdit):
    """
    A QLineEdit widget that binds to a target object's `UnitStr` property.

    It displays the value in a specified display unit. When editing is
    finished, it updates the target's property with a new UnitStr object
    and emits a comprehensive signal for undo/redo purposes.
    """
    # Signal emitted after a value has been successfully changed.
    # Emits: target_object, property_name, new_UnitStr_value, old_UnitStr_value
    valueChanged = Signal(object, str, object, object)

    def __init__(
        self,
        target_item: Optional[Any] = None,
        property_name: Optional[str] = None,
        display_unit: str = None,
        parent: Optional[QWidget] = None
    ):
        """
        Initializes the UnitField.

        Args:
            target_item: The object to be modified.
            property_name: The name of the UnitStr property on the target_item.
            display_unit: The unit to display the value in (e.g., "px", "mm").
            parent: The parent widget.
        """
        super().__init__(parent)
        self.target_item = target_item
        self.property_name = property_name
        self.display_unit = display_unit
        self._dpi = None
        if target_item:
            self._old_value = self.target_item.geometry
            self._dpi = self.target_item._geometry.dpi
        self._old_value: Optional[UnitStr] = None

        if target_item and property_name:
            self.setTarget(target_item, property_name, display_unit = self.display_unit)

        self.editingFinished.connect(self._on_editing_finished)

    def setTarget(self, target_item: Any, property_name: str, display_unit: str):
        """Sets or resets the target object and property for the field."""
        self.target_item = target_item
        self.property_name = property_name
        self.display_unit = display_unit
        if self.target_item and self.property_name:
            initial_value = getattr(self.target_item, self.property_name, None)
            if isinstance(initial_value, UnitStr):
                self._dpi = initial_value.dpi
                self._old_value = initial_value
                self.setTextFromValue(initial_value)
            else:
                self.clear()
        else:
            self.clear()

    def on_unit_change(self, display_unit):
        self.display_unit = display_unit
        self.setTarget(self.target_item, self.property_name, display_unit)

    def setTextFromValue(self, value: UnitStr):
        """
        Sets the displayed text by formatting the given UnitStr value.
        The text shown is the numeric value only, without the unit suffix.
        """
        if not isinstance(value, UnitStr):
            self.clear()
            return
        # Display value formatted to the display_unit, without the unit suffix
        formatted_value = value.fmt(".4f", unit=self.display_unit, dpi=self._dpi)
        self._old_value = value
        self.setText(formatted_value)

    def value(self) -> UnitStr:
        """
        Returns a new UnitStr object from the current text in the line edit.
        The text is interpreted as being in the widget's `display_unit`.
        Corrects common input errors like missing leading zeros.
        """
        unit = self.display_unit
        current_text = super().text().strip()

        if not current_text:
            return UnitStr("0", unit=unit, dpi=self._dpi)

        # Correct input: ".24" -> "0.24" or "-.24" -> "-0.24"
        if current_text.startswith('.'):
            current_text = '0' + current_text
        elif current_text.startswith('-.'):
            current_text = '-0' + current_text[1:]

        # Create the UnitStr. If the user-provided text has no unit,
        # the 'unit' parameter (set to self.display_unit) will be used.
        return UnitStr(current_text, unit=unit, dpi=self._dpi)

    @Slot()
    def _on_editing_finished(self):
        """
        Handles the end of an edit. If the value has changed, this method
        updates the target property and emits the `valueChanged` signal.
        """
        if not self.target_item or not self.property_name or self._old_value is None:
            self.clearFocus()
            return

        try:
            new_value = self.value()
        except ValueError:
            # Revert to the old value on invalid input and reformat text
            self.setTextFromValue(self._old_value)
            self.clearFocus()
            return

        # Do nothing if the value hasn't changed (compared in inches)
        if new_value.value == self._old_value.value:
            # Still reformat the text to ensure consistent display
            self.setTextFromValue(new_value)
            self.clearFocus()
            return

        # Emit the signal for undo/redo stack
        self.valueChanged.emit(self.target_item, self.property_name, new_value, self._old_value)

        # The new value becomes the old one for the next edit
        self._old_value = new_value
        
        # Update the display with the newly formatted value
        self.setTextFromValue(new_value)
        
        self.clearFocus()


class UnitStrGeometryField(QWidget):
    """
    A compound widget for editing a UnitStrGeometry property on a target object.
    It provides four fields for x, y, width, and height.
    """
    # Signal emitted after a value has been successfully changed.
    # Emits: target_object, property_name, new_Geometry_value, old_Geometry_value
    valueChanged = Signal(object, str, object, object)

    def __init__(
        self,
        target_item: Optional[Any] = None,
        property_name: Optional[str] = None,
        display_unit: str = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.target_item = None
        self.property_name = None
        self._old_geometry: Optional[UnitStrGeometry] = None
        self._display_unit = display_unit

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Create the four sub-fields for x, y, width, and height
        self.x_field = self._create_sub_field("X", 0, 0, layout)
        self.y_field = self._create_sub_field("Y", 1, 0, layout)
        self.w_field = self._create_sub_field("W", 0, 2, layout)
        self.h_field = self._create_sub_field("H", 1, 2, layout)

        if target_item and property_name:
            self.setTarget(target_item, property_name, display_unit=display_unit)

    def _create_sub_field(self, label_text: str, row: int, col: int, layout: QGridLayout) -> QLineEdit:
        """Helper to create a label and a basic QLineEdit."""
        label = QLabel(label_text)
        field = QLineEdit()
        layout.addWidget(label, row, col)
        layout.addWidget(field, row, col + 1)
        field.editingFinished.connect(self._on_editing_finished)
        return field

    def setTarget(self, target_item: Any, property_name: str, display_unit: str):
        """Sets the target object and its UnitStrGeometry property to edit."""
        self.target_item = target_item
        self.property_name = property_name
        self._display_unit = display_unit
        if isinstance(self.target_item, ComponentElement):
            self.target_item.item_changed.connect(self.update_from_item)

        if self.target_item and self.property_name:
            geom: Optional[UnitStrGeometry] = getattr(self.target_item, self.property_name, None)
            if isinstance(geom, UnitStrGeometry):
                self._old_geometry = geom
                self._update_display(geom)
            else:
                self._clear_fields()
        else:
            self._clear_fields()

    def on_unit_change(self, display_unit):
        self._display_unit = display_unit
        if self.target_item:
            self._update_display(self.target_item.geometry)

    def update_from_item(self):
        if self.target_item:
            self._update_display(self.target_item.geometry)

    def _update_display(self, geom: UnitStrGeometry):
        """Populates the four fields from a UnitStrGeometry object."""
        dpi = geom.dpi
        self.x_field.setText(geom.pos_x.fmt(".4g", self._display_unit, dpi=dpi))
        self.y_field.setText(geom.pos_y.fmt(".4g", self._display_unit, dpi=dpi))
        self.w_field.setText(geom.width.fmt(".4g", self._display_unit, dpi=dpi))
        self.h_field.setText(geom.height.fmt(".4g", self._display_unit, dpi=dpi))

    def _clear_fields(self):
        """Clears all input fields."""
        self.x_field.clear()
        self.y_field.clear()
        self.w_field.clear()
        self.h_field.clear()
        self._old_geometry = None

    def _create_unit_str_from_text(self, text: str, dpi: int) -> UnitStr:
        """
        Helper to create a UnitStr from a string, performing input correction.
        """
        text = text.strip()
        if not text:
            text = "0"

        if text.startswith('.'):
            text = '0' + text
        elif text.startswith('-.'):
            text = '-0' + text[1:]

        return UnitStr(text, unit=self._display_unit, dpi=dpi)

    @Slot()
    def _on_editing_finished(self):
        """
        Called when any sub-field finishes editing.
        Constructs a new UnitStrGeometry, updates the target, and emits a signal.
        """
        if not self.target_item or not self.property_name or self._old_geometry is None:
            if isinstance(self.sender(), QLineEdit): self.sender().clearFocus()
            return

        dpi = self._old_geometry.dpi

        try:

            x_val = self._create_unit_str_from_text(self.x_field.text(), dpi)
            y_val = self._create_unit_str_from_text(self.y_field.text(), dpi)
            w_val = self._create_unit_str_from_text(self.w_field.text(), dpi)
            h_val = self._create_unit_str_from_text(self.h_field.text(), dpi)
        except ValueError:
             self._update_display(self._old_geometry)
             if isinstance(self.sender(), QLineEdit): self.sender().clearFocus()
             return

        new_geometry = UnitStrGeometry(
            x=x_val, y=y_val, width=w_val, height=h_val,
            unit=self._old_geometry.unit, dpi=self.dpi, 
        )

        # If value is unchanged, just re-format the text and lose focus.
        if (new_geometry.pos_x.value == self._old_geometry.pos_x.value and
            new_geometry.pos_y.value == self._old_geometry.pos_y.value and
            new_geometry.width.value == self._old_geometry.width.value and
            new_geometry.height.value == self._old_geometry.height.value):
            self._update_display(new_geometry)
            if isinstance(self.sender(), QLineEdit): self.sender().clearFocus()
            return

        self.valueChanged.emit(self.target_item, self.property_name, new_geometry, self._old_geometry)

        self._old_geometry = new_geometry
        
        # Update the display with the newly formatted values
        self._update_display(new_geometry)
        
        if isinstance(self.sender(), QLineEdit):
            self.sender().clearFocus()
