# file: unit_widgets.py

from PySide6.QtWidgets import QLineEdit, QWidget, QLabel, QGridLayout
from PySide6.QtCore import Signal, Slot
from typing import Optional, Any

# Assuming these are in a sibling directory or accessible via the python path
from prototypyside.models.component_elements import ComponentElement
from prototypyside.utils.unit_str import UnitStr
from prototypyside.utils.unit_str_geometry import UnitStrGeometry


class UnitField(QLineEdit):
    """
    A QLineEdit widget that binds to a target object's `UnitStr` property.

    It displays the value in a specified display unit. When editing is
    finished, it updates the target's property with a new UnitStr object
    and emits a comprehensive signal for undo/redo purposes.
    """
    # Signal emitted after a value has been successfully changed.
    # Emits: target_object, property_name, old_UnitStr_value, new_UnitStr_value
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
        self.target_item = None
        self.property_name = None
        self.display_unit = display_unit
        self._dpi = None
        if target_item:
            self._old_value = self.target_item.geometry
            self._dpi = self.target_item.geometry.dpi
        self._old_value: Optional[UnitStr] = None

        if target_item and property_name:
            self.setTarget(target_item, property_name)

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
        """
        unit = self.target_item.geometry.unit
        current_text = super().text()
        if not current_text.strip():
            return UnitStr("0", unit=unit, dpi=self._dpi)
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

        new_value = self.value()

        # Do nothing if the value hasn't changed (compared in inches)
        if new_value.value == self._old_value.value:
            self.clearFocus()
            return

        # Update the target object's property
        setattr(self.target_item, self.property_name, new_value)

        # Emit the signal for undo/redo stack
        self.valueChanged.emit(self.target_item, self.property_name, self._old_value, new_value)

        # The new value becomes the old one for the next edit
        self._old_value = new_value
        self.clearFocus()


class UnitStrGeometryField(QWidget):
    """
    A compound widget for editing a UnitStrGeometry property on a target object.
    It provides four fields for x, y, width, and height.
    """
    # Signal emitted after a value has been successfully changed.
    # Emits: target_object, property_name, old_Geometry_value, new_Geometry_value
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
        # Use a standard QLineEdit; this controller widget manages all logic.
        field = QLineEdit()
        layout.addWidget(label, row, col)
        layout.addWidget(field, row, col + 1)
        # Connect the editingFinished signal to the main handler
        field.editingFinished.connect(self._on_editing_finished)
        return field

    def setTarget(self, target_item: Any, property_name: str, display_unit: str):
        """Sets the target object and its UnitStrGeometry property to edit."""
        self.target_item = target_item
        self.property_name = property_name
        self._display_unit = display_unit
        if isinstance(self.target_item, ComponentElement):
            print("We have an element")
            self.target_item.element_changed.connect(self.update_from_element)

        if self.target_item and self.property_name:
            geom: Optional[UnitStrGeometry] = getattr(self.target_item, self.property_name, None)
            if isinstance(geom, UnitStrGeometry):
                self._old_geometry = geom
                self._update_display(geom)
            else:
                self._clear_fields()
        else:
            self._clear_fields()

    def update_from_element(self):
        if self.target_item:
            self._update_display(self.target_item.geometry)

    def _update_display(self, geom: UnitStrGeometry):
        """Populates the four fields from a UnitStrGeometry object."""
        self.x_field.setText(geom.pos_x.fmt(".4g", self._display_unit, dpi=geom.dpi))
        self.y_field.setText(geom.pos_y.fmt(".4g", self._display_unit, dpi=geom.dpi))
        self.w_field.setText(geom.width.fmt(".4g", self._display_unit, dpi=geom.dpi))
        self.h_field.setText(geom.height.fmt(".4g", self._display_unit, dpi=geom.dpi))

    def _clear_fields(self):
        """Clears all input fields."""
        self.x_field.clear()
        self.y_field.clear()
        self.w_field.clear()
        self.h_field.clear()
        self._old_geometry = None

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
        
        # Create a UnitStr from each field's text
        try:
            x_val = UnitStr(self.x_field.text(), unit=self._display_unit, dpi=dpi)
            y_val = UnitStr(self.y_field.text(), unit=self._display_unit, dpi=dpi)
            w_val = UnitStr(self.w_field.text(), unit=self._display_unit, dpi=dpi)
            h_val = UnitStr(self.h_field.text(), unit=self._display_unit, dpi=dpi)
        except ValueError: # Handle invalid input
             self._update_display(self._old_geometry) # Revert to old values
             if isinstance(self.sender(), QLineEdit): self.sender().clearFocus()
             return

        # Construct the new geometry object
        new_geometry = UnitStrGeometry(
            x=x_val, y=y_val, width=w_val, height=h_val,
            unit=self._old_geometry.unit, dpi=dpi, 
        )

        # Emit the signal with all necessary info for an undo command
        self.valueChanged.emit(self.target_item, self.property_name, new_geometry, self._old_geometry)

        # The new geometry becomes the old one for the next edit
        self._old_geometry = new_geometry
        
        if isinstance(self.sender(), QLineEdit):
            self.sender().clearFocus()

# # unit_field.py

# from PySide6.QtWidgets import QLineEdit
# from PySide6.QtCore import Signal
# from typing import Optional

# from prototypyside.utils.unit_converter import parse_dimension
# from prototypyside.utils.unit_str import UnitStr


# class UnitField(QLineEdit):
#     editingFinishedWithValue = Signal(object)  # Emits UnitStr

#     def __init__(self, initial: 'UnitStr' = None, unit=None, dpi=None, parent=None):
#         super().__init__(parent)
#         self._value = initial if initial is not None else None
#         self._active = initial is not None
#         self._dpi = dpi
#         self._unit = unit
#         self.editingFinished.connect(self._on_editing_finished)
#         self.sync_display()

#     def sync_display(self):
#         """Update the display to reflect the current value, using self._display_unit and self._dpi."""
#         if not self._active or self._value is None:
#             self.setText("")
#             self.setDisabled(True)
#         else:
#             self.setEnabled(True)
#             self.setText(self._value.fmt(".4g", unit=self._unit, dpi=self._dpi))

#     def _on_editing_finished(self):
#         if not self._active:
#             return
#         try:
#             txt = self.text().strip()
#             # whatever the display unit is, set based on the value's original unit.
#             storage_unit = self._value.unit
#             storage_dpi = self._value.dpi
#             self._value = UnitStr(txt, unit=storage_unit, dpi=storage_dpi)
#             self.sync_display()
#             self.editingFinishedWithValue.emit(self._value)
#         except Exception:
#             self.sync_display()
#         self.clearFocus()

#     def setValue(self, value: 'UnitStr'):
#         if value is None:
#             self._value = None
#             self._active = False
#         else:
#             self._value = value
#             self._active = True
#         self.sync_display()

#     def getValue(self):
#         return self._value if self._active else None

#     def on_unit_changed(self, unit: str):
#         """
#         Called when the measurement unit or dpi has changed (e.g. from inches to mm).
#         Updates the display unit but leaves the internal value unchanged.
#         """
#         self._unit = unit
#         self.sync_display()

