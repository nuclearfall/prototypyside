# layout_property_panel.py

from PySide6.QtWidgets import QWidget, QFormLayout, QLabel, QTextEdit
from PySide6.QtCore import Qt

class LayoutPropertyPanel(QWidget):
    """
    Read-only property panel for showing properties of the selected template.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)
        self.name_label = QLabel(self)
        self.details_text = QTextEdit(self)
        self.details_text.setReadOnly(True)
        layout.addRow("Template Name:", self.name_label)
        layout.addRow("Details:", self.details_text)

    def display_template(self, template):
        """
        Update panel to show template details.
        Expects a ComponentTemplate or similar object.
        """
        if template:
            self.name_label.setText(getattr(template, "name", ""))
            # Gather details: merge info, elements, etc.
            text = ""
            if hasattr(template, "elements"):
                for elem in template.elements:
                    text += f"{getattr(elem, 'name', '')} - {type(elem).__name__}\n"
                    if hasattr(elem, "text"):
                        text += f"  Text: {getattr(elem, 'text', '')}\n"
                    if hasattr(elem, "image_path"):
                        text += f"  Image: {getattr(elem, 'image_path', '')}\n"
            self.details_text.setText(text)
        else:
            self.name_label.setText("")
            self.details_text.setText("")
