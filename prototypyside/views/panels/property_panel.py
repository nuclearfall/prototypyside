from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLineEdit, QPushButton, QComboBox,
                                 QGroupBox, QFormLayout, QCheckBox, QColorDialog, QLabel)
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QColor, QPalette
from prototypyside.widgets.unit_field import UnitField
from prototypyside.widgets.font_toolbar import FontToolbar
from prototypyside.widgets.color_picker import ColorPickerWidget
from prototypyside.utils.unit_converter import parse_dimension, to_px
from prototypyside.utils.unit_str import UnitStr 

class PropertyPanel(QWidget):
    property_changed = Signal(tuple)  # (property_name, value)
    geometry_changed = Signal(tuple)  # (property_name, value)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setAlignment(Qt.AlignTop)
        self.setLayout(self._main_layout)
        self._element = None
        self._build_component_ui()
        self.settings.unit_changed.connect(self.on_unit_changed)

    def _clear_layout(self):
        while self._main_layout.count():
            item = self._main_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

    def refresh(self):
        """Refresh UI from the current element, if any."""
        if self._element is not None:
            self.update_panel_from_element()
        else:
            self.clear()

    def clear(self):
        """Clear and disable all fields in the property panel."""
        for widget in self.findChildren(QWidget):
            # Skip QLabel widgets - they should keep their text
            if isinstance(widget, QLabel):
                continue
                
            if isinstance(widget, UnitField):
                widget.setValue(None)
            elif isinstance(widget, QLineEdit): 
                widget.setText("")
            elif isinstance(widget, QComboBox):
                if widget.count() > 0:
                    widget.setCurrentIndex(0)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(False)
            elif isinstance(widget, ColorPickerWidget):
                widget.set_color(QColor(0, 0, 0, 0))
            elif hasattr(widget, 'setValue'):
                widget.setValue(0)

            widget.setEnabled(False)

    def set_target(self, element):
        """Bind the panel to the selected element, or clear if None."""
        if self._element is not None:
            try:
                self._element.element_changed.disconnect(self.update_panel_from_element)
            except TypeError:
                pass  # Wasn't connected

        self._element = element

        if element is not None:
            # Enable fields and set values from element
            self.update_panel_from_element()
            # No need to iterate and enable all, update_panel_from_element will enable relevant ones
            # Or you can do it here if you want to enable *all* children regardless of data presence
            for widget in self.findChildren(QWidget):
                widget.setEnabled(True)
            element.element_changed.connect(self.update_panel_from_element)
        else:
            self.clear()

    def set_mode(self, mode="component"):
        self._clear_layout()
        if mode == "component":
            self._build_component_ui()
        elif mode == "layout":
            self._build_layout_ui()

    def _build_component_ui(self):
        element_group = QGroupBox("Element Info")
        element_layout = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(
            lambda: self.emit_property_and_clear(self.name_edit, "name", self.name_edit.text()))


        element_layout.addRow("Name:", self.name_edit)

        self.content_edit = QLineEdit()
        self.content_edit.editingFinished.connect(
            lambda: self.emit_property_and_clear(self.content_edit, "content", self.content_edit.text()))

        element_layout.addRow("Content:", self.content_edit)

        element_group.setLayout(element_layout)
        self._main_layout.addWidget(element_group)

        geometry_group = QGroupBox("Geometry")
        geometry_layout = QFormLayout()

        self.element_x_field = UnitField(None, self.settings.unit, self.settings.dpi)
        self.element_y_field = UnitField(None, self.settings.unit, self.settings.dpi)
        self.element_width_field = UnitField(None, self.settings.unit, self.settings.dpi)
        self.element_height_field = UnitField(None, self.settings.unit, self.settings.dpi)

        for field in [self.element_x_field, self.element_y_field, self.element_width_field, self.element_height_field]:
            field.editingFinished.connect(self._on_geometry_changed)

        geometry_layout.addRow("X:", self.element_x_field)
        geometry_layout.addRow("Y:", self.element_y_field)
        geometry_layout.addRow("Width:", self.element_width_field)
        geometry_layout.addRow("Height:", self.element_height_field)

        geometry_group.setLayout(geometry_layout)
        self._main_layout.addWidget(geometry_group)

        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout()

        # --- REPLACED BUTTONS WITH COLOR PICKER WIDGETS ---
        self.text_color_picker = ColorPickerWidget(QColor(0,0,0)) # Default to black
        self.bg_color_picker = ColorPickerWidget(QColor(255,255,255,0)) # Default to transparent white
        self.border_color_picker = ColorPickerWidget(QColor(0,0,0)) # Default to black

        # Connect signals: color_changed from picker emits property_changed

        self.text_color_picker.color_changed.connect(
            lambda color: self.property_changed.emit(("color", color))
        )
        self.bg_color_picker.color_changed.connect(
            lambda color: self.property_changed.emit(("bg_color", color))
        )
        self.border_color_picker.color_changed.connect(
            lambda color: self.property_changed.emit(("border_color", color))
        )
        self.border_width_field = UnitField(None, self.settings.unit, self.settings.dpi)

        self.border_width_field.editingFinished.connect(
            lambda: self.emit_property_and_clear(self.border_width_field, "border_width", self.border_width_field.text()))

        self.alignment_combo = QComboBox()
        self.alignment_map = {
            "Top Left": Qt.AlignTop | Qt.AlignLeft,
            "Top Center": Qt.AlignTop | Qt.AlignHCenter,
            "Top Right": Qt.AlignTop | Qt.AlignRight,
            "Center Left": Qt.AlignVCenter | Qt.AlignLeft,
            "Center": Qt.AlignCenter,
            "Center Right": Qt.AlignVCenter | Qt.AlignRight,
            "Bottom Left": Qt.AlignBottom | Qt.AlignLeft,
            "Bottom Center": Qt.AlignBottom | Qt.AlignHCenter,
            "Bottom Right": Qt.AlignBottom | Qt.AlignRight,
        }
        self.reverse_alignment_map = {v: k for k, v in self.alignment_map.items()}
        self.alignment_combo.addItems(list(self.alignment_map.keys()))
        self.alignment_combo.currentTextChanged.connect(
            lambda: self.property_changed.emit(("alignment", self.alignment_map.get(self.alignment_combo.currentText(), Qt.AlignLeft))))

        
        # Add a label and the color picker widget to the form layout
        appearance_layout.addRow("Text Color:", self.text_color_picker)
        appearance_layout.addRow("Background:", self.bg_color_picker)
        appearance_layout.addRow("Border Color:", self.border_color_picker)
        appearance_layout.addRow("Border Width:", self.border_width_field)
        appearance_layout.addRow("Alignment:", self.alignment_combo)

        appearance_group.setLayout(appearance_layout)
        self._main_layout.addWidget(appearance_group)

        self.font_toolbar = FontToolbar()
        self.font_toolbar.font_changed.connect(
                lambda font: self.property_changed.emit(("font", font)))
        self._main_layout.addWidget(self.font_toolbar)

        self.aspect_checkbox = QCheckBox("Maintain Aspect Ratio")
        self.aspect_checkbox.stateChanged.connect(lambda state: self.property_changed.emit(("aspect_ratio", bool(state))))
        self._main_layout.addWidget(self.aspect_checkbox)

    def _build_layout_ui(self):
        placeholder = QGroupBox("Layout Builder Mode (Placeholder)")
        layout = QVBoxLayout()
        layout.addWidget(QPushButton("Layout-specific control"))
        placeholder.setLayout(layout)
        self._main_layout.addWidget(placeholder)

    def _on_geometry_changed(self):
        field = self.sender()
        if field:
            field.clearFocus()
        # All fields return a UnitStr or None
        values = [
            self.element_x_field.getValue(),
            self.element_y_field.getValue(),
            self.element_width_field.getValue(),
            self.element_height_field.getValue()
        ]
        self.geometry_changed.emit(("geometry", values))

    # def _on_geometry_changed(self):
    #     field = self.sender()
    #     if field:
    #         field.clearFocus()

    #     values = [
    #         self.element_x_field.text(),
    #         self.element_y_field.text(),
    #         self.element_width_field.text(),
    #         self.element_height_field.text()
    #     ]
    #     self.geometry_changed.emit(("geometry", values))

    def emit_property_and_clear(self, field, prop_name, value):
        field.clearFocus()
        self.property_changed.emit((prop_name, value))

    def update_panel_from_element(self):
        element = self._element
        if element is None:
            self.clear()
            return

        # Enable all controls
        for widget in self.findChildren(QWidget):
            widget.setEnabled(True)

        # --- BASIC FIELDS ---
        self.name_edit.blockSignals(True)
        self.name_edit.setText(getattr(element, "name", ""))
        self.name_edit.blockSignals(False)

        # Content
        self.content_edit.blockSignals(True)
        if hasattr(element, "text"):
            self.content_edit.setText(element.content)
        else:
            self.content_edit.setText("")
            self.content_edit.setEnabled(False)
        self.content_edit.blockSignals(False)

        # --- GEOMETRY ---
        # Assume element has _x, _y, _width, _height as UnitStr
        self.element_x_field.blockSignals(True)
        self.element_y_field.blockSignals(True)
        self.element_width_field.blockSignals(True)
        self.element_height_field.blockSignals(True)

        # Always pass UnitStr to the field
        if hasattr(element, "_x"):
            self.element_x_field.setValue(element._x)
        if hasattr(element, "_y"):
            self.element_y_field.setValue(element._y)
        if hasattr(element, "_width"):
            self.element_width_field.setValue(element._width)
        if hasattr(element, "_height"):
            self.element_height_field.setValue(element._height)

        self.element_x_field.blockSignals(False)
        self.element_y_field.blockSignals(False)
        self.element_width_field.blockSignals(False)
        self.element_height_field.blockSignals(False)

        # --- APPEARANCE ---
        self.text_color_picker.blockSignals(True)
        if hasattr(element, "color") and element.color is not None:
            self.text_color_picker.set_color(QColor(element.color))
        else:
            self.text_color_picker.set_color(QColor(0,0,0,0))
        self.text_color_picker.blockSignals(False)

        self.bg_color_picker.blockSignals(True)
        if hasattr(element, "bg_color") and element.bg_color is not None:
            self.bg_color_picker.set_color(QColor(element.bg_color))
        else:
            self.bg_color_picker.set_color(QColor(0,0,0,0))
        self.bg_color_picker.blockSignals(False)

        self.border_color_picker.blockSignals(True)
        if hasattr(element, "border_color") and element.border_color is not None:
            self.border_color_picker.set_color(QColor(element.border_color))
        else:
            self.border_color_picker.set_color(QColor(0,0,0,0))
        self.border_color_picker.blockSignals(False)

        # Border width (store as UnitStr, e.g. "1 pt", "0.5 mm")
        self.border_width_field.blockSignals(True)
        if hasattr(element, "border_width"):
            bw = getattr(element, "border_width", "1 pt")
            # If already UnitStr, use as-is. If string, convert.
            if isinstance(bw, UnitStr):
                self.border_width_field.setValue(bw)
            else:
                self.border_width_field.setValue(UnitStr(str(bw), unit=self.settings.unit, dpi=self.settings.dpi))
        self.border_width_field.blockSignals(False)

        # --- ALIGNMENT ---
        self.alignment_combo.blockSignals(True)
        alignment = getattr(element, "alignment", None)
        if alignment is not None and alignment in self.reverse_alignment_map:
            index = self.alignment_combo.findText(self.reverse_alignment_map[alignment])
            self.alignment_combo.setCurrentIndex(index)
        else:
            index = self.alignment_combo.findText("Center")
            self.alignment_combo.setCurrentIndex(index)
        self.alignment_combo.blockSignals(False)

        # --- FONT ---
        self.font_toolbar.blockSignals(True)
        if hasattr(element, "font"):
            self.font_toolbar.setEnabled(True)
            self.font_toolbar.set_font(element.font)
        else:
            self.font_toolbar.setEnabled(False)
        self.font_toolbar.blockSignals(False)

        # --- ASPECT RATIO ---
        self.aspect_checkbox.blockSignals(True)
        if hasattr(element, "aspect_ratio"):
            self.aspect_checkbox.setChecked(bool(element.aspect_ratio))
        else:
            self.aspect_checkbox.setChecked(False)
        self.aspect_checkbox.blockSignals(False)

    def on_unit_changed(self):
        unit_fields = [self.element_x_field, self.element_y_field, 
                self.element_width_field, self.element_height_field, 
                self.border_width_field]
        for field in unit_fields:
            field.on_unit_changed(self.settings.unit)

    # def update_panel_from_element(self):
    #     element = self._element
    #     if element is None:
    #         self.clear()
    #         return

    #     # Enable all controls
    #     for widget in self.findChildren(QWidget):
    #         widget.setEnabled(True)

    #     # --- BASIC FIELDS ---
    #     self.name_edit.blockSignals(True)
    #     self.name_edit.setText(getattr(element, "name", ""))
    #     self.name_edit.blockSignals(False)
        
    #     # Content
    #     self.content_edit.blockSignals(True)
    #     if hasattr(element, "text"):
    #         self.content_edit.setText(element.content)
    #     else:
    #         self.content_edit.setText("")
    #         self.content_edit.setEnabled(False)
    #     self.content_edit.blockSignals(False)

    #     # --- GEOMETRY ---
    #     self.element_x_field.blockSignals(True)
    #     self.element_y_field.blockSignals(True)
    #     self.element_width_field.blockSignals(True)
    #     self.element_height_field.blockSignals(True)
    #     pos = element.pos()
    #     rect = getattr(element, "_rect", QRectF())
    #     self.element_x_field.setValue(pos.x())
    #     self.element_y_field.setValue(pos.y())
    #     self.element_width_field.setValue(rect.width())
    #     self.element_height_field.setValue(rect.height())
    #     self.element_x_field.blockSignals(False)
    #     self.element_y_field.blockSignals(False)
    #     self.element_width_field.blockSignals(False)
    #     self.element_height_field.blockSignals(False)

    #     # --- APPEARANCE ---
    #     self.text_color_picker.blockSignals(True)
    #     if hasattr(element, "color") and element.color is not None:
    #         self.text_color_picker.set_color(QColor(element.color))
    #     else:
    #         self.text_color_picker.set_color(QColor(0,0,0,0))
    #     self.text_color_picker.blockSignals(False)

    #     self.bg_color_picker.blockSignals(True)
    #     if hasattr(element, "bg_color") and element.bg_color is not None:
    #         self.bg_color_picker.set_color(QColor(element.bg_color))
    #     else:
    #         self.bg_color_picker.set_color(QColor(0,0,0,0))
    #     self.bg_color_picker.blockSignals(False)

    #     self.border_color_picker.blockSignals(True)
    #     if hasattr(element, "border_color") and element.border_color is not None:
    #         self.border_color_picker.set_color(QColor(element.border_color))
    #     else:
    #         self.border_color_picker.set_color(QColor(0,0,0,0))
    #     self.border_color_picker.blockSignals(False)

    #     # Border width
    #     self.border_width_field.blockSignals(True)
    #     self.border_width_field.setValue(to_px(getattr(element, "border_width", "1 px")))
    #     self.border_width_field.blockSignals(False)

    #     # --- ALIGNMENT ---
    #     self.alignment_combo.blockSignals(True)
    #     alignment = getattr(element, "alignment", None)
    #     if alignment is not None and alignment in self.reverse_alignment_map:
    #         index = self.alignment_combo.findText(self.reverse_alignment_map[alignment])
    #         self.alignment_combo.setCurrentIndex(index)
    #     else:
    #         index = self.alignment_combo.findText("Center")
    #         self.alignment_combo.setCurrentIndex(index)
    #     self.alignment_combo.blockSignals(False)

    #     # --- FONT ---
    #     self.font_toolbar.blockSignals(True)
    #     if hasattr(element, "font"):
    #         self.font_toolbar.setEnabled(True)
    #         self.font_toolbar.set_font(element.font)
    #     else:
    #         self.font_toolbar.setEnabled(False)
    #     self.font_toolbar.blockSignals(False)

    #     # --- ASPECT RATIO ---
    #     self.aspect_checkbox.blockSignals(True)
    #     if hasattr(element, "aspect_ratio"):
    #         self.aspect_checkbox.setChecked(bool(element.aspect_ratio))
    #     else:
    #         self.aspect_checkbox.setChecked(False)
    #     self.aspect_checkbox.blockSignals(False)

