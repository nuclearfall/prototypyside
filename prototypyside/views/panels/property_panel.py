# file: property_panel.py

from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLabel, QLineEdit, QComboBox, QCheckBox,
    QVBoxLayout, QFrame, QTextEdit, QPushButton, QFileDialog, QColorDialog, QStackedWidget, QTextEdit)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont, QTextOption
from typing import Optional, Any

# Assuming these modules are in the same directory or accessible via python path
from prototypyside.widgets.unit_field import UnitField, UnitStrGeometryField
from prototypyside.models.component_elements import ComponentElement, TextElement, ImageElement
from prototypyside.views.toolbars.font_toolbar import FontToolbar
from prototypyside.widgets.color_picker import ColorPickerWidget


# --- Main Property Panel Widget ---

class PropertyPanel(QWidget):
    """
    A panel to display and edit properties of a selected ComponentElement.
    """
    # Emits (target_object, property_name, old_value, new_value)
    property_changed = Signal(object, str, object, object)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.target_item: Optional[ComponentElement] = None
        self._display_unit = "in" # Default, can be changed

        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)

        # A frame to hold the properties
        self.main_frame = QFrame()
        self.main_frame.setObjectName("propertyFrame")
        self.form_layout = QFormLayout(self.main_frame)
        self.form_layout.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.main_layout.addWidget(self.main_frame)

        # --- Create all possible widgets ---
        self.pid_label = QLabel()
        self.template_pid_label = QLabel()
        self.name_edit = QLineEdit()

        # Content widgets in a stacked layout
        self.content_stack = QStackedWidget()
        self.content_text_edit = QTextEdit()
        self.content_text_edit.setWordWrapMode(QTextOption.WordWrap)
        self.content_path_edit = QLineEdit() # For image path
        self.content_stack.addWidget(self.content_text_edit)
        self.content_stack.addWidget(self.content_path_edit)

        self.geometry_field = UnitStrGeometryField()
        self.color_picker = ColorPickerWidget()
        self.bg_color_picker = ColorPickerWidget()
        self.border_color_picker = ColorPickerWidget()
        self.border_width_field = UnitField()
        
        # Alignment ComboBox
        self.alignment_map = {
            "Top Left": Qt.AlignTop | Qt.AlignLeft, "Top Center": Qt.AlignTop | Qt.AlignHCenter,
            "Top Right": Qt.AlignTop | Qt.AlignRight, "Center Left": Qt.AlignVCenter | Qt.AlignLeft,
            "Center": Qt.AlignCenter, "Center Right": Qt.AlignVCenter | Qt.AlignRight,
            "Bottom Left": Qt.AlignBottom | Qt.AlignLeft, "Bottom Center": Qt.AlignBottom | Qt.AlignHCenter,
            "Bottom Right": Qt.AlignBottom | Qt.AlignRight,
        }
        self.alignment_combo = QComboBox()
        self.alignment_combo.addItems(self.alignment_map.keys())
        self.alignment_rev_map = {v: k for k, v in self.alignment_map.items()}

        # Conditional widgets
        self.font_toolbar = FontToolbar()
        self.keep_aspect_checkbox = QCheckBox("Keep Aspect Ratio")

        # Add widgets to layout
        self.form_layout.addRow("PID:", self.pid_label)
        self.form_layout.addRow("Template PID:", self.template_pid_label)
        self.form_layout.addRow("Name:", self.name_edit)
        self.form_layout.addRow("Content:", self.content_stack)
        self.form_layout.addRow("Geometry:", self.geometry_field)
        self.form_layout.addRow("Color:", self.color_picker)
        self.form_layout.addRow("Background Color:", self.bg_color_picker)
        self.form_layout.addRow("Border Color:", self.border_color_picker)
        self.form_layout.addRow("Border Width:", self.border_width_field)
        self.form_layout.addRow("Alignment:", self.alignment_combo)
        self.form_layout.addRow(self.font_toolbar)
        self.form_layout.addRow(self.keep_aspect_checkbox)

        # Connect signals
        self._connect_signals()

        # Initially hide everything
        self.clear_target()

    def _connect_signals(self):
        self.name_edit.editingFinished.connect(lambda: self._handle_property_change("name", self.name_edit.text()))
        self.content_text_edit.textChanged.connect(lambda: self._handle_property_change("content", self.content_text_edit.toPlainText()))
        self.content_path_edit.editingFinished.connect(lambda: self._handle_property_change("content", self.content_path_edit.text()))
        self.geometry_field.valueChanged.connect(self.property_changed.emit)
        self.color_picker.color_changed.connect(lambda c: self._handle_property_change("color", c))
        self.bg_color_picker.color_changed.connect(lambda c: self._handle_property_change("bg_color", c))
        self.border_color_picker.color_changed.connect(lambda c: self._handle_property_change("border_color", c))
        self.border_width_field.valueChanged.connect(self.property_changed.emit)
        self.alignment_combo.currentIndexChanged.connect(self._on_alignment_changed)
        self.font_toolbar.font_changed.connect(self.property_changed.emit)
        self.keep_aspect_checkbox.toggled.connect(lambda t: self._handle_property_change("keep_aspect", t))

    def set_target(self, element: Optional[ComponentElement]):
        self.target_item = element
        if not element:
            self.clear_target()
            return

        # Block signals to prevent firing while populating
        for widget in self.main_frame.findChildren(QWidget):
            widget.blockSignals(True)

        # Populate common fields
        self.pid_label.setText(element.pid)
        self.template_pid_label.setText(element.template_pid or "N/A")
        self.name_edit.setText(element.name)
        
        self.geometry_field.setTarget(element, "geometry")
        self.color_picker.set_color(element.color)
        self.bg_color_picker.set_color(element.bg_color)
        self.border_color_picker.set_color(element.border_color)
        self.border_width_field.setTarget(element, "border_width")
        
        alignment_text = self.alignment_rev_map.get(element.alignment, "Center")
        self.alignment_combo.setCurrentText(alignment_text)

        # Handle conditional widgets
        self.font_toolbar.setVisible(hasattr(element, 'font'))
        if hasattr(element, 'font'):
            self.font_toolbar.setTarget(element)

        self.keep_aspect_checkbox.setVisible(hasattr(element, 'keep_aspect'))
        if hasattr(element, 'keep_aspect'):
            self.keep_aspect_checkbox.setChecked(element.keep_aspect)
        
        # Handle content widget type
        if isinstance(element, TextElement):
            self.content_text_edit.setText(element.content or "")
            self.content_stack.setCurrentWidget(self.content_text_edit)
        elif isinstance(element, ImageElement):
            self.content_path_edit.setText(element.content or "")
            self.content_stack.setCurrentWidget(self.content_path_edit)
        else:
             self.form_layout.labelForField(self.content_stack).hide()
             self.content_stack.hide()

        # Unblock signals and show the panel
        for widget in self.main_frame.findChildren(QWidget):
            widget.blockSignals(False)
        self.main_frame.setVisible(True)

    def clear_target(self):
        self.target_item = None
        self.main_frame.setVisible(False)

    def _handle_property_change(self, prop_name: str, new_value: Any):
        if not self.target_item:
            return

        old_value = getattr(self.target_item, prop_name)
        
        # For QColor, direct comparison works. For others, it should be fine.
        if old_value != new_value:
            setattr(self.target_item, prop_name, new_value)
            self.property_changed.emit(self.target_item, prop_name, old_value, new_value)

    @Slot(int)
    def _on_alignment_changed(self, index: int):
        if not self.target_item:
            return
        
        text = self.alignment_combo.itemText(index)
        new_value = self.alignment_map.get(text)
        self._handle_property_change("alignment", new_value)

# from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLineEdit, QPushButton, QComboBox,
#                                  QGroupBox, QFormLayout, QCheckBox, QColorDialog, QLabel)
# from PySide6.QtCore import Qt, Signal, QRectF, Slot
# from PySide6.QtGui import QColor, QPalette
# from prototypyside.widgets.unit_field import UnitField
# from prototypyside.views.toolbars.font_toolbar import FontToolbar
# from prototypyside.widgets.color_picker import ColorPickerWidget
# from prototypyside.utils.unit_converter import parse_dimension, to_px
# from prototypyside.utils.unit_str import UnitStr 
# from prototypyside.utils.unit_str_geometry import UnitStrGeometry

# class PropertyPanel(QWidget):
#     property_changed = Signal(tuple)  # (property_name, value)
#     geometry_changed = Signal(UnitStrGeometry, UnitStrGeometry)  # (property_name, value)

#     def __init__(self, settings, parent=None):
#         super().__init__(parent)
#         self.settings = settings
#         self._unit = settings.unit
#         self._dpi = settings.dpi
#         self._main_layout = QVBoxLayout(self)
#         self._main_layout.setAlignment(Qt.AlignTop)
#         self.setLayout(self._main_layout)
#         self._element = None
#         self.debug_count = 1
#         self._build_component_ui()
#         self.settings.unit_changed.connect(self.on_unit_changed)

#     def _clear_layout(self):
#         while self._main_layout.count():
#             item = self._main_layout.takeAt(0)
#             widget = item.widget()
#             if widget:
#                 widget.setParent(None)

#     def refresh(self):
#         """Refresh UI from the current element, if any."""
#         pass
#         # if self._element is not None:
#         #     self._update_ui_from_element()
#         # else:
#         #     self.clear()

#     def clear(self):
#         """Clear and disable all fields in the property panel."""
#         for widget in self.findChildren(QWidget):
#             # Skip QLabel widgets - they should keep their text
#             if isinstance(widget, QLabel):
#                 continue
                
#             if isinstance(widget, UnitField):
#                 widget.setValue(None)
#             elif isinstance(widget, QLineEdit): 
#                 widget.setText("")
#             elif isinstance(widget, QComboBox):
#                 if widget.count() > 0:
#                     widget.setCurrentIndex(0)
#             elif isinstance(widget, QCheckBox):
#                 widget.setChecked(False)
#             elif isinstance(widget, ColorPickerWidget):
#                 widget.set_color(QColor(0, 0, 0, 0))
#             elif hasattr(widget, 'setValue'):
#                 widget.setValue(0)

#             widget.setEnabled(False)

#     # Connect the element_changed signal properly in set_target:
#     def set_target(self, element):
#         """Bind the panel to the selected element, or clear if None."""
#         if self._element is not None:
#             try:
#                 # Disconnect the OLD element's signal from the new _update_ui_from_element slot
#                 self._element.element_changed.disconnect(self._update_ui_from_element)
#             except TypeError:
#                 pass  # Wasn't connected

#         self._element = element

#         if element is not None:
#             # Connect the NEW element's signal to _update_ui_from_element
#             element.element_changed.connect(self._update_ui_from_element)
            
#             # Now, trigger the update manually for the newly selected element
#             # This will call _update_ui_from_element, which properly blocks signals.
#             self._update_ui_from_element() 
            
#             # Enable all children (if you want to enable ALL, even if no data for them)
#             for widget in self.findChildren(QWidget):
#                 widget.setEnabled(True)
#         else:
#             self.clear() # Clears and disables fields if no element is selected


#     def _build_component_ui(self):
#         element_group = QGroupBox("Element Info")
#         element_layout = QFormLayout()

#         self.name_edit = QLineEdit()
#         self.name_edit.editingFinished.connect(
#             lambda: self.emit_property_and_clear(self.name_edit, "name", self.name_edit.text()))


#         element_layout.addRow("Name:", self.name_edit)

#         self.content_edit = QLineEdit()
#         self.content_edit.editingFinished.connect(
#             lambda: self.emit_property_and_clear(self.content_edit, "content", self.content_edit.text()))

#         element_layout.addRow("Content:", self.content_edit)

#         element_group.setLayout(element_layout)
#         self._main_layout.addWidget(element_group)

#         geometry_group = QGroupBox("Geometry")
#         geometry_layout = QFormLayout()

#         self.element_x_field = UnitField(None, self.settings.unit, self.settings.dpi)
#         self.element_y_field = UnitField(None, self.settings.unit, self.settings.dpi)
#         self.element_width_field = UnitField(None, self.settings.unit, self.settings.dpi)
#         self.element_height_field = UnitField(None, self.settings.unit, self.settings.dpi)

#         for field in [self.element_x_field, self.element_y_field, self.element_width_field, self.element_height_field]:
#             field.editingFinishedWithValue.connect(self._on_geometry_changed)

#         geometry_layout.addRow("X:", self.element_x_field)
#         geometry_layout.addRow("Y:", self.element_y_field)
#         geometry_layout.addRow("Width:", self.element_width_field)
#         geometry_layout.addRow("Height:", self.element_height_field)
    
#         geometry_group.setLayout(geometry_layout)
#         self._main_layout.addWidget(geometry_group)

#         appearance_group = QGroupBox("Appearance")
#         appearance_layout = QFormLayout()

#         # --- REPLACED BUTTONS WITH COLOR PICKER WIDGETS ---
#         self.text_color_picker = ColorPickerWidget(QColor(0,0,0)) # Default to black
#         self.bg_color_picker = ColorPickerWidget(QColor(255,255,255,0)) # Default to transparent white
#         self.border_color_picker = ColorPickerWidget(QColor(0,0,0)) # Default to black

#         # Connect signals: color_changed from picker emits property_changed

#         self.text_color_picker.color_changed.connect(
#             lambda color: self.property_changed.emit(("color", color))
#         )
#         self.bg_color_picker.color_changed.connect(
#             lambda color: self.property_changed.emit(("bg_color", color))
#         )
#         self.border_color_picker.color_changed.connect(
#             lambda color: self.property_changed.emit(("border_color", color))
#         )
#         self.border_width_field = UnitField(None, unit=self.settings.unit, dpi=self.settings.dpi)

#         self.border_width_field.editingFinishedWithValue.connect(
#             lambda: self.emit_property_and_clear(self.border_width_field, "border_width", self.border_width_field.text()))

#         self.alignment_combo = QComboBox()
#         self.alignment_map = {
#             "Top Left": Qt.AlignTop | Qt.AlignLeft,
#             "Top Center": Qt.AlignTop | Qt.AlignHCenter,
#             "Top Right": Qt.AlignTop | Qt.AlignRight,
#             "Center Left": Qt.AlignVCenter | Qt.AlignLeft,
#             "Center": Qt.AlignCenter,
#             "Center Right": Qt.AlignVCenter | Qt.AlignRight,
#             "Bottom Left": Qt.AlignBottom | Qt.AlignLeft,
#             "Bottom Center": Qt.AlignBottom | Qt.AlignHCenter,
#             "Bottom Right": Qt.AlignBottom | Qt.AlignRight,
#         }
#         self.reverse_alignment_map = {v: k for k, v in self.alignment_map.items()}
#         self.alignment_combo.addItems(list(self.alignment_map.keys()))
#         self.alignment_combo.currentTextChanged.connect(
#             lambda: self.property_changed.emit(("alignment", self.alignment_map.get(self.alignment_combo.currentText(), Qt.AlignLeft))))

        
#         # Add a label and the color picker widget to the form layout
#         appearance_layout.addRow("Text Color:", self.text_color_picker)
#         appearance_layout.addRow("Background:", self.bg_color_picker)
#         appearance_layout.addRow("Border Color:", self.border_color_picker)
#         appearance_layout.addRow("Border Width:", self.border_width_field)
#         appearance_layout.addRow("Alignment:", self.alignment_combo)

#         appearance_group.setLayout(appearance_layout)
#         self._main_layout.addWidget(appearance_group)

#         self.font_toolbar = FontToolbar()
#         self.font_toolbar.font_changed.connect(
#                 lambda font: self.property_changed.emit(("font", font)))
#         self._main_layout.addWidget(self.font_toolbar)

#         self.aspect_checkbox = QCheckBox("Maintain Aspect Ratio")
#         self.aspect_checkbox.stateChanged.connect(lambda state: self.property_changed.emit(("aspect_ratio", bool(state))))
#         self._main_layout.addWidget(self.aspect_checkbox)

#     def _on_geometry_changed(self):
#         field = self.sender()
#         if field:
#             field.clearFocus()
        
#         # Only emit if we have a valid element
#         if not self._element:
#             return

#         # Get current values
#         pos_x = self.element_x_field.getValue()
#         pos_y = self.element_y_field.getValue()
#         width = self.element_width_field.getValue()
#         height = self.element_height_field.getValue()
        
#         # Create new geometry
#         new_geometry = UnitStrGeometry(width=width, height=height, x=pos_x, y=pos_y)
#         old_geometry = UnitStrGeometry.from_dict(self._element.geometry.dict())

#         print(f"Call to tab to resize and move: {self.debug_count}")
#         self.debug_count += 1
#         self._element.geometry = new_geometry
#         # if new_geometry != self._element.geometry:
#         #     self.geometry_changed.emit(new_geometry, old_geometry)


#     def emit_property_and_clear(self, field, prop_name, value):
#         field.clearFocus()
#         self.property_changed.emit((prop_name, value))


#     def on_unit_changed(self, unit, dpi):
#         unit_fields = [self.element_x_field, self.element_y_field, 
#                 self.element_width_field, self.element_height_field, 
#                 self.border_width_field]
#         for field in unit_fields:
#             field.on_unit_changed(self.settings.unit)

#     @Slot()
#     def _update_ui_from_element(self): # Renamed for clarity
#         # This method is designed to be connected to element.element_changed
#         # and called whenever the element's data changes.
#         if self._element is None:
#             self.clear()
#             return

#         elem_geom = self._element.geometry
#         current_geom = UnitStrGeometry.from_dict(elem_geom.dict())
        
#         # Block signals for ALL relevant input fields before updating
#         # This list should ideally be gathered once, e.g., in __init__
#         fields_to_block = [
#             self.name_edit, self.content_edit,
#             self.element_x_field, self.element_y_field,
#             self.element_width_field, self.element_height_field,
#             self.text_color_picker, self.bg_color_picker, self.border_color_picker,
#             self.border_width_field, self.alignment_combo,
#             self.font_toolbar, self.aspect_checkbox
#         ]
        
#         for field in fields_to_block:
#             if hasattr(field, 'blockSignals'):
#                 field.blockSignals(True)

#         # --- Update fields with element's current data ---
#         # BASIC FIELDS
#         self.name_edit.setText(getattr(self._element, "name", ""))
        
#         if hasattr(self._element, "content"):
#             self.content_edit.setText(self._element.content)
#             self.content_edit.setEnabled(True) # Ensure enabled if it has content
#         else:
#             self.content_edit.setText("")
#             self.content_edit.setEnabled(False)

#         if hasattr(self._element, "geometry"):
#             self.element_x_field.setValue(current_geom.pos_x)
#             self.element_y_field.setValue(current_geom.pos_y)
#             self.element_width_field.setValue(current_geom.width)
#             self.element_height_field.setValue(current_geom.height)
#         else:
#             # Handle elements without geometry (disable fields, clear values)
#             self.element_x_field.setValue(None)
#             self.element_y_field.setValue(None)
#             self.element_width_field.setValue(None)
#             self.element_height_field.setValue(None)
#             self.element_x_field.setEnabled(False)
#             self.element_y_field.setEnabled(False)
#             self.element_width_field.setEnabled(False)
#             self.element_height_field.setEnabled(False)


#         # APPEARANCE (similar pattern as geometry, but for colors/widths/alignment)
#         self.text_color_picker.set_color(getattr(self._element, "color", QColor(0,0,0,0)))
#         self.bg_color_picker.set_color(getattr(self._element, "bg_color", QColor(0,0,0,0)))
#         self.border_color_picker.set_color(getattr(self._element, "border_color", QColor(0,0,0,0)))
        
#         bw = getattr(self._element, "border_width", "1 pt")
#         self.border_width_field.setValue(bw)
        
#         alignment = getattr(self._element, "alignment", None)
#         if alignment is not None and alignment in self.reverse_alignment_map:
#             index = self.alignment_combo.findText(self.reverse_alignment_map[alignment])
#             self.alignment_combo.setCurrentIndex(index)
#         else:
#             index = self.alignment_combo.findText("Center")
#             self.alignment_combo.setCurrentIndex(index)

#         # FONT
#         if hasattr(self._element, "font"):
#             self.font_toolbar.setEnabled(True)
#             self.font_toolbar.set_font(self._element.font)
#         else:
#             self.font_toolbar.setEnabled(False)

#         # ASPECT RATIO
#         self.aspect_checkbox.setChecked(bool(getattr(self._element, "aspect_ratio", False)))


#         # Unblock signals for all fields
#         for field in fields_to_block:
#             if hasattr(field, 'blockSignals'):
#                 field.blockSignals(False)

