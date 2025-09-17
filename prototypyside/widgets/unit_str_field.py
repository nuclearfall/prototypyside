# unit_field.py

from PySide6.QtWidgets import QLineEdit, QWidget, QLabel, QGridLayout
from PySide6.QtCore import Signal, Slot
from typing import Optional, Any, List

from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.services.proto_class import ProtoClass

pc = ProtoClass

class UnitStrField(QLineEdit):
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
        parent: Optional[QWidget] = None,
        decimal_places: Optional[int] = 4,
        dpi: Optional[int] = None
    ):
        """
        Initializes the UnitStrField.

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
        self.places = decimal_places
        self._dpi = dpi or None
        if target_item:
            self._old_value = self.target_item.geometry
            self._dpi = self.target_item._geometry.dpi
        self._old_value: Optional[UnitStr] = None
        # UnitStringsField is dependent on the target not having the property
        if target_item:
            self.setTarget(target_item, property_name, display_unit = self.display_unit)

        self.editingFinished.connect(self._on_editing_finished)

    # In unit_str_field.py, add this method to UnitStrField class
    def clearTarget(self, *, clear_ui: bool = True, disable: bool = False):
        """
        Safely unbind from the current model/property and (optionally) blank the UI.
        """
      # Clear binding and local cache
        self.target_item = None
        self.property_name = None
        self._old_value = None
        
        # Clear UI if requested
        if clear_ui:
            self.clear()  # Directly call QLineEdit.clear()
            self.blockSignals(False)
        
        # Disable if requested
        if disable and hasattr(self, "setEnabled"):
            self.setEnabled(False)

    def setTarget(self, target_item: Any, property_name: str=None, display_unit: str=None, value=None):
        """Sets or resets the target object and property for the field."""
        self.target_item = target_item
        self.property_name = property_name or self.property_name
        self.display_unit = display_unit or self.display_unit
        if self.target_item and self.property_name:
            intial_value = value
            if not value:
                initial_value = getattr(self.target_item, self.property_name, None)
            if pc.isproto(initial_value, pc.US):
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
        # Display value formatted to the display_unit
        formatted_value = value.fmt(f".{self.places}f", unit=self.display_unit, dpi=self._dpi)
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

    def setValue(self, value: UnitStr):
        """
        Programmatically set the field's UnitStr value and update the display,
        without emitting valueChanged. Also updates _old_value so the first edit
        compares against this value.
        """
        # Optional safety: ignore non-UnitStr
        if not isinstance(value, UnitStr):
            self.clear()
            self._old_value = None
            return

        # Avoid signal storms when used inside composites
        old = self.blockSignals(True)
        try:
            self._old_value = value
            self.setTextFromValue(value)  # already formats to display_unit
        finally:
            self.blockSignals(old)

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
        
    # Optional helpers
    def setDisplayUnit(self, unit: str):
        self._display_unit = unit

    def setDecimalPlaces(self, places: int):
        self.decimal_places = places

    def setDpi(self, dpi: int):
        self._dpi = dpi