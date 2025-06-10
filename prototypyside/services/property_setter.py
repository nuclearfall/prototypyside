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
            self._notify()

    def set_geometry(self, values: list[str]):
        # Ensure values are not empty strings before parsing.
        # Treat empty strings as "0" to avoid ValueError from parse_dimension.
        x_str = values[0] if values[0] else "0"
        y_str = values[1] if values[1] else "0"
        w_str = values[2] if values[2] else "0"
        h_str = values[3] if values[3] else "0"

        # to_px_qrectf and to_px_pos will call parse_dimension internally.
        # By ensuring x_str, y_str, w_str, h_str are "0" instead of "",
        # parse_dimension will receive a valid input.
        rect = to_px_qrectf(x_str, y_str, w_str, h_str, dpi=self.settings.dpi)
        self.target.setRect(rect)
        self.target.setPos(to_px_pos(x_str, y_str, dpi=self.settings.dpi))
        self._notify()

    def set_maintain_aspect(self, aspect: bool):
        if hasattr(self.target, "preserve_aspect_ratio"):
            self.target.preserve_aspect_ratio = aspect
            self._notify()

    def set_border_width(self, value: str):
        if hasattr(self.target, "border_width"):
            self.target.border_width = to_px(value, dpi=settings.dpi)
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

    def set_aspect_ratio(self, aspect: bool):
        if hasattr(self.target, "preserve_aspect_ratio"):
            self.target.preserve_aspect_ratio = aspect
            self._notify()

    def set_content(self, text: str):
        if hasattr(self.target, "content"):
            self.target.content = text
            self._notify()

    def _notify(self):
        if hasattr(self.target, "element_changed"):
            self.target.element_changed.emit()
        if self.scene:
            self.scene.update()
