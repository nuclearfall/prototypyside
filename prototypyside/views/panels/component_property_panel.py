# file: property_pancomp.py

from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLabel, QLineEdit, QComboBox, QCheckBox,
    QVBoxLayout, QFrame, QTextEdit, QPushButton, QFileDialog, QColorDialog, QStackedWidget, QTextEdit)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont, QTextOption, QKeyEvent
from typing import Optional, Any, TYPE_CHECKING

# Assuming these modules are in the same directory or accessible via python path
from prototypyside.services.proto_class import ProtoClass

from prototypyside.widgets.color_picker import ColorPickerWidget
if TYPE_CHECKING:
    from prototypyside.models.component_template import ComponentTemplate


class FocusLineEdit(QLineEdit):
    editingFinishedWithValue = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.returnPressed.connect(self.clearFocus)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.editingFinishedWithValue.emit(self.text())

class FocusTextEdit(QTextEdit):
    """
    A custom QTextEdit widget with word wrap that emits a signal on losing focus.

    The signal `editingFinished` carries the target_comp, the content key, the new
    text value, and the old text value.
    """
    editingFinished = Signal(object, str, object, object)

    def __init__(self, layout, target_comp, content_key="content", parent=None):
        super().__init__(parent)
        self.setWordWrapMode(QTextOption.WordWrap)
        self._content_key = content_key
        self._target_comp = None
        self._original_value = None
        if target_comp:
            self._target_comp = target_comp
            self._original_value = getattr(target_comp, content_key, "")
            self.setText(self._original_value)

    def focusOutEvent(self, event):
        """
        Overrides the focusOutEvent to emit a signal with the data.
        """
        new_value = self.toPlainText()
        if new_value != self._original_value:
            self.editingFinished.emit(self._target_comp, self._content_key, new_value, self._original_value)
            print(f"LOSE_FOCUS_TEXT_EDIT {self._target_comp.pid}, {new_value} from {self._original_value}")
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

    def setTarget(self, target_comp, content_key="content"):
        """
        Sets the target comp and content key for the widget.
        """
        self._target_comp = target_comp
        self._content_key = content_key
        self._original_value = getattr(target_comp, content_key, "")
        self.setText(self._original_value)


# --- Main Property Panel Widget ---

class ComponentPropertyPanel(QWidget):
    """
    A panel to display and edit properties of the current ComponentTemplate.
    """
    # Emits (target_object, property_name, old_value, new_value)
    property_changed = Signal(object, str, object, object)

    def __init__(self, display_unit:str, comp:ProtoClass.CT, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.target_comp = comp
        self._display_unit = display_unit
        self.undo_stack = getattr(parent, "undo_stack", None)
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
        self.name_edit = FocusLineEdit()

        # Content widgets in a stacked layout
        self.bg_image_button = QPushButton("Select Image...") # For image path
        self.bg_image_button.setMaximumHeight(32)

        self.width_field = ProtoClass.USField()
        self.bg_color_picker = ColorPickerWidget()
        self.border_color_picker = ColorPickerWidget()
        self.border_width_field = ProtoClass.USField(property_name="border_width", display_unit=display_unit)
        
        # Conditional widgets
        self.keep_aspect_checkbox = QCheckBox("Keep Aspect Ratio")

        # Add widgets to layout
        self.form_layout.addRow("PID:", self.pid_label)
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
        self.name_edit.editingFinishedWithValue.connect(lambda value: self._handle_property_change("name", value))
        self.content_text_edit.editingFinished.connect(self.property_changed.emit)
        self.bg_image_button.clicked.connect(self._choose_image_path)
        self.width_field.valueChanged.connect(self.property_changed.emit)
        self.height_field.valueChanged.connect(self.property_changed.emit)
        self.color_picker.color_changed.connect(lambda c: self._handle_property_change("color", c))
        self.bg_color_picker.color_changed.connect(lambda c: self._handle_property_change("bg_color", c))
        self.border_color_picker.color_changed.connect(lambda c: self._handle_property_change("border_color", c))
        self.border_width_field.valueChanged.connect(self.property_changed.emit)
        self.alignment_combo.currentIndexChanged.connect(self._on_alignment_changed)
        self.font_toolbar.font_changed.connect(self.property_changed.emit)
        self.keep_aspect_checkbox.toggled.connect(lambda t: self._handle_property_change("keep_aspect", t))

    def set_target(self, comp: Optional[ProtoClass.CE]):
        self.target_comp = comp
        if not comp:
            self.clear_target()
            return
        # Block signals to prevent firing while populating
        for widget in self.main_frame.findChildren(QWidget):
            widget.blockSignals(True)

        # Populate common fields
        self.pid_labcomp.setText(comp.pid)
        self.name_edit.setText(comp.name)
        self.width_field.setTarget(comp, "width", display_unit=self._display_unit)
        self.height_field.setTarget(comp, "height", display_unit=self._display_unit)
        self.bg_color_picker.set_color(comp.bg_color)
        self.border_color_picker.set_color(comp.border_color)
        self.border_width_field.setTarget(comp, "border_width", display_unit=self._display_unit)

        # Unblock signals and show the panel
        for widget in self.main_frame.findChildren(QWidget):
            widget.blockSignals(False)
        # self.main_frame.setVisible(True)

    def clear_target(self):
        self.target_comp = None

    @Slot(str)
    def on_unit_change(self, display_unit: str):
        """
        Called when the user (or the containing Tab) wants
        to switch display units (e.g. "px" → "in" → "cm").
        This will re-target the two ProtoClass.USFields so they
        re-fetch their model values and reformat in the new unit.
        """
        self._display_unit = display_unit

        # if nothing is selected → nothing to do
        if not self.target_comp:
            return

        # re-bind both unit-aware fields so they redraw
        self.width_field.setTarget(
            self.target_comp,
            "width",
            display_unit=self._display_unit
        )
        self.height_field.setTarget(
            self.target_comp,
            "height",
            display_unit=self._display_unit
        )
        self.bleed_field.setTarget(
            self.target_comp,
            "bleed",
            display_unit=self._display_unit
        )
        self.corner_radius_field.setTarget(
            self.target_comp,
            "corner_radius",
            display_unit=self._display_unit
        )
        self.border_width_field.setTarget(
            self.target_comp,
            "border_width",
            display_unit=self._display_unit
        )


    def _populate_fields(self):
        """Fill every widget from self.target_comp’s current state."""
        comp = self.target_comp
        self.pid_labcomp.setText(comp.pid)
        self.name_edit.setText(comp.name)

        # geometry / colors / border
        self.width_field.setTarget(comp, "width", display_unit=self._display_unit)
        self.height_field.setTarget(comp, "height", display_unit=self._display_unit)
        self.bleed_field.setTarget(comp, "bleed", display_unit=self._display_unit)
        self.bg_color_picker.set_color(comp.bg_color)
        self.border_color_picker.set_color(comp.border_color)
        self.corner_radius_field.setTarget(comp, "corner_radius", display_unit=self._display_unit)
        self.border_width_field.setTarget(comp, "border_width", display_unit=self._display_unit)



    @Slot()
    def refresh(self):
        """Re-populate the panel from the current target_comp."""
        if not self.target_comp:
            return
        # re-use the exact same logic (we know signals are blocked in set_target)
        self.set_target(self.target_comp)

    def _handle_property_change(self, prop_name: str, new_value: Any):
        if not self.target_comp:
            return

        old_value = getattr(self.target_comp, prop_name)
        
        # For QColor, direct comparison works. For others, it should be fine.
        if old_value != new_value:
            if prop_name == "font" or prop_name ==  "geometry":
                self.text_edit.setCurrentFont(new_value)
            print(f"[PROP PANEL] Prop={prop_name}, old={old_value}, new={new_value}, equal={old_value == new_value}")
            self.property_changed.emit(self.target_comp, prop_name, new_value, old_value)
 
    @Slot()
    def _choose_image_path(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select File", "", "Images (*.png *.jpg *.bmp *.gif);;SVG Files (*.svg)"
        )
        if file_path:
            old_value = self.target_comp.content
            new_value = file_path
            if old_value != new_value:
                self.property_changed.emit(self.target_comp, "background_image", new_value, old_value)