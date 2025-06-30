# layout_property_panel.py

from PySide6.QtWidgets import QWidget, QFormLayout, QLabel, QTextEdit, QComboBox
from PySide6.QtGui import QPixmap, QImage, QPainter
from PySide6.QtCore import Qt, Signal, QRectF


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

    def display_template(self, template, pixmap=None):
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
                    if hasattr(elem, "content"):
                        text += f"  {getattr(elem, 'content', '')}\n"
            self.details_text.setText(text)
            # self.preview_label = QLabel(self)
            # self.preview_label.setFixedSize(80, 100)  # Or whatever size you want
            # if pixmap:
            #     self.set_template_preview(pixmap)
            #     self.layout().addWidget(self.preview_label)

        else:
            self.name_label.setText("")
            self.details_text.setText("")

 
    # def set_template_preview(self, pixmap: QPixmap):
    #     preview = pixmap.scaled(self.preview_label.size(),
    #                             Qt.KeepAspectRatio,
    #                             Qt.SmoothTransformation)
    #     self.preview_label.setPixmap(preview)

    def clear_values(self):
        # Remove all fields/widgets, or reset to a blank state
        # For example:
        self.details_name.setText("")
        self.details_text.setText("")

        # Or set fields to default/empty values
        self.setTitle("No Selection")

def scene_to_pixmap(scene, width, height):
    image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    # Optionally, set a viewport transform here to fit scene contents
    scene.render(painter, QRectF(0, 0, width, height), scene.sceneRect())
    painter.end()
    return QPixmap.fromImage(image)
