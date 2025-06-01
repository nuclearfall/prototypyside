# style_serialization_helpers.py
from PySide6.QtGui import QColor, QFont

from prototypyside.utils.qt_helpers import (
    qfont_to_dict, dict_to_qfont,
    qcolor_to_rgba, rgba_to_qcolor,
    qtalignment_to_str, str_to_qtalignment,
)
from prototypyside.utils.unit_converter import format_dimension, parse_dimension
from PySide6.QtCore import Qt

def save_style(style: dict, dpi: int = 72) -> dict:
    result = {}
    for key, value in style.items():
        if key == "font" and isinstance(value, QFont):
            result[key] = qfont_to_dict(value)
        elif key in {"color", "bg_color", "border_color"} and isinstance(value, QColor):
            result[key] = qcolor_to_rgba(value)
        elif key == "alignment" and isinstance(value, Qt.Alignment):
            result[key] = qtalignment_to_str(value)
        else:
            result[key] = value
    return result


def load_style(style: dict, dpi: int = 72) -> dict:
    result = {}
    for key, value in style.items():
        if key == "font" and isinstance(value, dict):
            result[key] = dict_to_qfont(value)
        elif key in {"color", "bg_color", "border_color"} and isinstance(value, (list, tuple)):
            result[key] = rgba_to_qcolor(value)
        elif key == "alignment" and isinstance(value, str):
            result[key] = str_to_qtalignment(value)
        elif key == "maintain_aspect":
            result[key] = bool(value)
        else:
            result[key] = value
    return result

