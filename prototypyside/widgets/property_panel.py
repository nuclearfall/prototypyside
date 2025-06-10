from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLineEdit, QPushButton, QComboBox,
                                 QGroupBox, QFormLayout, QCheckBox, QColorDialog)
from PySide6.QtCore import Qt, Signal, QRectF
from prototypyside.widgets.unit_field import UnitField
from prototypyside.widgets.font_toolbar import FontToolbar

class PropertyPanel(QWidget):
    property_changed = Signal(tuple)  # (property_name, value)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setAlignment(Qt.AlignTop)
        self.setLayout(self._main_layout)
        self._element = None
        self._build_component_ui()

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
            if isinstance(widget, UnitField):
                # UnitField correctly handles None to clear and disable itself
                widget.setValue(None)
            elif hasattr(widget, 'setValue'):
                # For other widgets with setValue (e.g., QSpinBox, QSlider),
                # assume they take an integer and set to 0 as a default.
                # If you have specific non-numeric widgets with setValue,
                # you might need to handle them differently or ensure 0 is safe.
                widget.setValue(0)
            elif hasattr(widget, 'setText'):
                # For QLineEdit and similar text-based widgets
                widget.setText("")
            
            # Disable all widgets after clearing/setting default values
            widget.setEnabled(False)
            
        self._element = None

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
        self.name_edit.editingFinished.connect(lambda: self.property_changed.emit(("name", self.name_edit.text())))
        element_layout.addRow("Name:", self.name_edit)

        self.content_edit = QLineEdit()
        self.content_edit.editingFinished.connect(lambda: self.property_changed.emit(("content", self.content_edit.text())))
        element_layout.addRow("Content:", self.content_edit)

        element_group.setLayout(element_layout)
        self._main_layout.addWidget(element_group)

        geometry_group = QGroupBox("Geometry")
        geometry_layout = QFormLayout()

        self.element_x_field = UnitField(None, self.settings.unit)
        self.element_y_field = UnitField(None, self.settings.unit)
        self.element_width_field = UnitField(None, self.settings.unit)
        self.element_height_field = UnitField(None, self.settings.unit)

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

        self.color_btn = QPushButton("Text Color")
        self.bg_color_btn = QPushButton("Background Color")
        self.border_color_btn = QPushButton("Border Color")
        self.border_width_field = UnitField(None, self.settings.unit)
        self.border_width_field.editingFinished.connect(lambda: self.property_changed.emit(("border_width", self.border_width_field.text())))

        self.color_btn.clicked.connect(self._on_color_btn_clicked)
        self.bg_color_btn.clicked.connect(self._on_bg_color_btn_clicked)
        self.border_color_btn.clicked.connect(self._on_border_color_btn_clicked)

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
                lambda text: self.property_changed.emit(
                        ("alignment", self.alignment_map.get(text)))
        )

        appearance_layout.addRow(self.color_btn)
        appearance_layout.addRow(self.bg_color_btn)
        appearance_layout.addRow(self.border_color_btn)
        appearance_layout.addRow("Border Width:", self.border_width_field)
        appearance_layout.addRow("Alignment:", self.alignment_combo)

        appearance_group.setLayout(appearance_layout)
        self._main_layout.addWidget(appearance_group)

        self.font_toolbar = FontToolbar()
        self.font_toolbar.property_changed.connect(lambda font: self.property_changed.emit(("font", font)))
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
        values = [
            self.element_x_field.text(),
            self.element_y_field.text(),
            self.element_width_field.text(),
            self.element_height_field.text()
        ]
        self.property_changed.emit(("geometry", values))

    def update_panel_from_element(self):
        """Populate all property panel fields from the current element."""
        element = self._element
        if element is None:
            self.clear()
            return

        # Enable all controls
        self.name_edit.setEnabled(True)
        self.content_edit.setEnabled(True)
        self.element_x_field.setEnabled(True)
        self.element_y_field.setEnabled(True)
        self.element_width_field.setEnabled(True)
        self.element_height_field.setEnabled(True)
        self.color_btn.setEnabled(True)
        self.bg_color_btn.setEnabled(True)
        self.border_color_btn.setEnabled(True)
        self.border_width_field.setEnabled(True)
        self.alignment_combo.setEnabled(True)
        self.font_toolbar.setEnabled(True)
        self.aspect_checkbox.setEnabled(True)

        """Populate all property panel fields from the current element."""
        element = self._element
        if element is None:
            self.clear()
            return

        # Enable all controls
        for widget in self.findChildren(QWidget):
            widget.setEnabled(True)

        # --- BASIC FIELDS ---
        self.name_edit.setText(getattr(element, "name", ""))
        
        # Content
        if hasattr(element, "text"):
            self.content_edit.setText(element.text)
        elif hasattr(element, "content"):
            self.content_edit.setText(element.content)
        else:
            self.content_edit.setText("")

        # --- GEOMETRY ---
        pos = element.pos()
        rect = getattr(element, "_rect", QRectF())
        
        self.element_x_field.setValue(pos.x())
        self.element_y_field.setValue(pos.y())
        self.element_width_field.setValue(rect.width())
        self.element_height_field.setValue(rect.height())

        # --- APPEARANCE ---
        # Colors
        if hasattr(element, "color"):
            color = element.color
            self.color_btn.setStyleSheet(f"background-color: {color.name()}")
            self.color_btn.setProperty("color", color)
        else:
            self.color_btn.setStyleSheet("")
            self.color_btn.setProperty("color", None)

        if hasattr(element, "bg_color"):
            bg_color = element.bg_color
            self.bg_color_btn.setStyleSheet(f"background-color: {bg_color.name()}")
            self.bg_color_btn.setProperty("color", bg_color)
        else:
            self.bg_color_btn.setStyleSheet("")
            self.bg_color_btn.setProperty("color", None)

        if hasattr(element, "border_color"):
            border_color = element.border_color
            self.border_color_btn.setStyleSheet(f"background-color: {border_color.name()}")
            self.border_color_btn.setProperty("color", border_color)
        else:
            self.border_color_btn.setStyleSheet("")
            self.border_color_btn.setProperty("color", None)

        # Border width
        self.border_width_field.setValue(getattr(element, "border_width", 0))

        # --- ALIGNMENT ---
        alignment = getattr(element, "alignment", None)
        if alignment and alignment in self.reverse_alignment_map:
            index = self.alignment_combo.findText(self.reverse_alignment_map[alignment])
            self.alignment_combo.setCurrentIndex(index)
        else:
            # Default to "Center"
            index = self.alignment_combo.findText("Center")
            self.alignment_combo.setCurrentIndex(index)

        # --- FONT ---
        if hasattr(element, "font"):
            self.font_toolbar.set_font(element.font)
            self.font_toolbar.setEnabled(True)
        else:
            self.font_toolbar.setEnabled(False)

        # --- ASPECT RATIO ---
        if hasattr(element, "aspect_ratio"):
            self.aspect_checkbox.setChecked(bool(element.aspect_ratio))
        else:
            self.aspect_checkbox.setChecked(False)

    def _choose_color(self, initial="#000000") -> str:
        color = QColorDialog.getColor()
        return color.name() if color.isValid() else initial

    def _on_color_btn_clicked(self):
        self.property_changed.emit(("color", self._choose_color()))

    def _on_bg_color_btn_clicked(self):
        self.property_changed.emit(("bg_color", self._choose_color()))

    def _on_border_color_btn_clicked(self):
        self.property_changed.emit(("border_color", self._choose_color()))
