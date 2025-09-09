# layout_property_panel.py

from PySide6.QtWidgets import QWidget, QFormLayout, QLabel, QTextEdit, QComboBox
from PySide6.QtGui import QPixmap, QImage, QPainter
from PySide6.QtCore import Qt, Signal, QRectF

from prototypyside.widgets.unit_str_geometry_field import UnitStrGeometryField


class LayoutPropertyPanel(QWidget):
    """
    Read-only property panel for showing properties of the selected template.
    """
    def __init__(self, 
        tab,
        target=None, 
        parent=None):
        super().__init__(parent)
        self.tab = tab
        self.layout = tab.template
        
    #     self.name_label = QLabel(self)
    #     self.name_label = QLabel(self)
    #     self.geom_props_fields = UnitStrGeometryField(
    #         target_item=self.layout,
    #         property_name="geometry",
    #         display_unit=self.tab.main_window.settings.unit,
    #         labels=["Width", "Height"]
    #     )
    #     self.whitespace_fields = UnitStringsField(
    #         target=self.layout,
    #         property_name="margins",
    #         labels=["Top", "Bottom", "Left", "Right", "Horizontal", "Vertical"],
    #         display_unit=self.tab.main_window.settings.unit)
    #     self.name_label.setText(self.layout.name)
    #     layout.addRow("Name:", self.name_label)
    #     layout.addRow("Page Size:", self.geom_props_fields)


    #     self.geom_props_fields.setEnabled(False)

    #     self.comp_props = {
    #         {"name", self.name_label}
    #         {"dimensions", self.geom_props_fields}
    #     }
    #     self.connect()

    # def update(self, template):
    #     """
    #     Update panel to show template details.
    #     Expects a ComponentTemplate or similar object.
    #     """
    #     self.name_label.setText(self.layout.name)
    #     self.geom_props_fields.set_target(
    #         target_item=None, 
    #         property_name="geometry"
    #     )
    #         return
    #     self.name_label.setText(template.name)
    #     self.geom_props_fields.set_target(
    #             target_item=template,
    #             property_name="geometry",
    #             unit=self.tab.main_window.settings.unit
    #     )
    #     self.whitespace_fields.set_target(
    #         target_item=self.layout,
    #         property_name="whitspace",
    #         display_unit=self.tab.main_window.settings.unit)

    # def update():
    #     selected = self.tab.selected_item if self.tab.selected_item else None
    #     self.set_target(selected)

    # def set_target(self, component)
    #     self.target = component
    #     self.display_template()

    # def set_auto_fill(self):
    #     # keep the checkbox/field in sync with the current model value
    #     self.bleed_checkbox.blockSignals(True)
    #     self.bleed_checkbox.setChecked(bool(getattr(self.target, "autofill", False)))
    #     self.bleed_checkbox.blockSignals(False)

    #     self.bleed_field.setEnabled(self.bleed_checkbox.isChecked())

    # def on_property_changed():


    # def clear_values(self):
    #     # Remove all fields/widgets, or reset to a blank state
    #     # For example:
    #     self.details_name.setText("")
    #     self.details_text.setText("")

    #     # Or set fields to default/empty values
    #     self.setTitle("No Selection")
