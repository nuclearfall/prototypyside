# file: property_panel.py

from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLabel, QLineEdit, QComboBox, QCheckBox,
    QVBoxLayout, QFrame, QTextEdit, QPushButton, QFileDialog, QColorDialog, QStackedWidget, QTextEdit)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont, QTextOption, QKeyEvent
from typing import Optional, Any

# Assuming these modules are in the same directory or accessible via python path
from prototypyside.widgets.unit_field import UnitField, UnitStrGeometryField
from prototypyside.utils.unit_str_geometry import UnitStrGeometry
from prototypyside.models.component_elements import ComponentElement, TextElement, ImageElement
from prototypyside.views.toolbars.font_toolbar import FontToolbar
from prototypyside.widgets.color_picker import ColorPickerWidget



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

    The signal `editingFinished` carries the target_item, the content key, the new
    text value, and the old text value.
    """
    editingFinished = Signal(object, str, object, object)

    def __init__(self, target_item=None, content_key="content", parent=None):
        super().__init__(parent)
        self.setWordWrapMode(QTextOption.WordWrap)
        self._content_key = content_key
        self._target_item = None
        self._original_value = None
        if target_item:
            self._target_item = target_item
            self._original_value = getattr(target_item, content_key, "")
            self.setText(self._original_value)

    def focusOutEvent(self, event):
        """
        Overrides the focusOutEvent to emit a signal with the data.
        """
        new_value = self.toPlainText()
        if new_value != self._original_value:
            self.editingFinished.emit(self._target_item, self._content_key, new_value, self._original_value)
            print(f"LOSE_FOCUS_TEXT_EDIT {self._target_item.pid}, {new_value} from {self._original_value}")
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

    def __init__(self, display_unit:str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.target_item: Optional[ComponentElement] = None
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
        self.template_pid_label = QLabel()
        self.name_edit = FocusLineEdit()

        # Content widgets in a stacked layout
        self.content_stack = QStackedWidget()
        self.content_text_edit = FocusTextEdit()
        self.content_path_button = QPushButton("Select Image...") # For image path
        self.content_stack.addWidget(self.content_text_edit)
        self.content_stack.addWidget(self.content_path_button)

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
        self.content_text_edit.editingFinished.connect(self.property_changed.emit)
        self.content_path_button.clicked.connect(self._choose_image_path)
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
        self.content_text_edit.setTarget(element, "content")
        self.geometry_field.setTarget(element, "geometry", display_unit=self._display_unit)
        self.color_picker.set_color(element.color)
        self.bg_color_picker.set_color(element.bg_color)
        self.border_color_picker.set_color(element.border_color)
        self.border_width_field.setTarget(element, "border_width", display_unit=self._display_unit)
        
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
            self.content_stack.setCurrentWidget(self.content_path_button)
        else:
             self.form_layout.labelForField(self.content_stack).hide()
             self.content_stack.hide()

        # Unblock signals and show the panel
        for widget in self.main_frame.findChildren(QWidget):
            widget.blockSignals(False)
        # self.main_frame.setVisible(True)

    def clear_target(self):
        self.target_item = None

    @Slot(str)
    def on_unit_change(self, display_unit: str):
        """
        Called when the user (or the containing Tab) wants
        to switch display units (e.g. "px" → "in" → "cm").
        This will re-target the two UnitFields so they
        re-fetch their model values and reformat in the new unit.
        """
        self._display_unit = display_unit

        # if nothing is selected → nothing to do
        if not self.target_item:
            return

        # re-bind both unit-aware fields so they redraw
        self.geometry_field.setTarget(
            self.target_item,
            "geometry",
            display_unit=self._display_unit
        )
        self.border_width_field.setTarget(
            self.target_item,
            "border_width",
            display_unit=self._display_unit
        )

    # def clear_target(self):
    #     # Disconnect change signal
    #     if self.target_item and self._element_changed_conn:
    #         try:
    #             self.target_item.element_changed.disconnect(self.refresh)
    #         except (AttributeError, TypeError):
    #             pass
    #     self._element_changed_conn = False

    #     self.target_item = None
    #     # Hide or clear your widgets as before…
    #     # e.g. self.main_frame.setVisible(False)

    def _populate_fields(self):
        """Fill every widget from self.target_item’s current state."""
        el = self.target_item
        self.pid_label.setText(el.pid)
        self.template_pid_label.setText(el.template_pid or "N/A")
        self.name_edit.setText(el.name)

        # geometry / colors / border
        self.geometry_field.setTarget(el, "geometry", display_unit=self._display_unit)
        self.color_picker.set_color(el.color)
        self.bg_color_picker.set_color(el.bg_color)
        self.border_color_picker.set_color(el.border_color)
        self.border_width_field.setTarget(el, "border_width", display_unit=self._display_unit)

        # alignment
        text = self.alignment_rev_map.get(el.alignment, "Center")
        self.alignment_combo.setCurrentText(text)

        # font toolbar
        self.font_toolbar.setVisible(hasattr(el, "font"))
        if hasattr(el, "font"):
            self.font_toolbar.setTarget(el)

        # aspect checkbox
        self.keep_aspect_checkbox.setVisible(hasattr(el, "keep_aspect"))
        if hasattr(el, "keep_aspect"):
            self.keep_aspect_checkbox.setChecked(el.keep_aspect)

        # content stack
        if isinstance(el, TextElement):
            self.content_stack.setCurrentWidget(self.content_text_edit)
            self.content_text_edit.setTarget(el, "content")
            self.content_text_edit.setText(el.content or "")
        elif isinstance(el, ImageElement):
            self.content_stack.setCurrentWidget(self.content_path_button)
        else:
            self.form_layout.labelForField(self.content_stack).hide()
            self.content_stack.hide()

    @Slot()
    def refresh(self):
        """Re-populate the panel from the current target_item."""
        if not self.target_item:
            return
        # re-use the exact same logic (we know signals are blocked in set_target)
        self.set_target(self.target_item)

    def _handle_property_change(self, prop_name: str, new_value: Any):
        if not self.target_item:
            return

        old_value = getattr(self.target_item, prop_name)
        
        # For QColor, direct comparison works. For others, it should be fine.
        if old_value != new_value:
            if prop_name == "font" or prop_name ==  "geometry":
                self.text_edit.setCurrentFont(new_value)
            print(f"[PROP PANEL] Prop={prop_name}, old={old_value}, new={new_value}, equal={old_value == new_value}")
            self.property_changed.emit(self.target_item, prop_name, new_value, old_value)
        self.sender().clearFocus()
 
    @Slot()
    def _choose_image_path(self):
        if not isinstance(self.target_item, ImageElement):
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if file_path:
            old_value = self.target_item.content
            new_value = file_path
            if old_value != new_value:
                self.property_changed.emit(self.target_item, "content", new_value, old_value)


    @Slot(int)
    def _on_alignment_changed(self, index: int):
        if not self.target_item:
            return
        
        text = self.alignment_combo.itemText(index)
        new_value = self.alignment_map.get(text)
        self._handle_property_change("alignment", new_value)