from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QColor

from prototypyside.utils.unit_converter import to_px, to_px_pos, to_px_qrectf

class PropertySetter:
    def __init__(self, target, settings, scene=None):
        self.target = target
        self.settings = settings
        self.scene = scene

    def set_name(self, name: str):
        if hasattr(self.target, "name"):
            self.target.name = name
            print(f"Attempting to set 'name' to {name}")
            self._notify()

    def set_border_width(self, value: str):
        if hasattr(self.target, "border_width"):
            # Pass the string value directly. GameComponentElement.paint will parse it.
            self.target.border_width = value
            self._notify()

    def set_font(self, font: QFont):
        if hasattr(self.target, "font"):
            self.target.font = font
            self._notify()

    def set_alignment(self, alignment):
        if hasattr(self.target, "alignment"):
            self.target.alignment = alignment
            self._notify()

    def set_color(self, color_str):
        from PySide6.QtGui import QColor
        if hasattr(self.target, "color"):
            self.target.color = QColor(color_str)
            self._notify()

    def set_bg_color(self, color_str):
        if hasattr(self.target, "bg_color"):
            self.target.bg_color = QColor(color_str)
            self._notify()

    def set_border_color(self, color_str):
        if hasattr(self.target, "border_color"):
            self.target.border_color = QColor(color_str)
            self._notify()

    def set_keep_aspect(self, aspect: bool):
        if hasattr(self.target, "keep_aspect"):
            self.target.keep_aspect = aspect
            self._notify()

    def set_content(self, text: str):
        if hasattr(self.target, "text"):
            self.target.content = text
            self._notify()

    def _notify(self):
        if hasattr(self.target, "element_changed"):
            self.target.element_changed.emit()
        if self.scene:
            self.scene.update()
