# prototypyside/utils/qt_helpers.py

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont
from typing import List, Dict, Any

def qrectf_to_list(rect: QRectF) -> List[float]:
    return [rect.x(), rect.y(), rect.width(), rect.height()]

def list_to_qrectf(data: List[float]) -> QRectF:
    if len(data) == 4:
        return QRectF(data[0], data[1], data[2], data[3])
    raise ValueError("Invalid QRectF data: must be a list of 4 floats.")

def qcolor_to_rgba(color: QColor) -> List[int]:
    return [color.red(), color.green(), color.blue(), color.alpha()]

def rgba_to_qcolor(data: List[int]) -> QColor:
    if len(data) == 4:
        return QColor(data[0], data[1], data[2], data[3])
    raise ValueError("Invalid QColor data: must be a list of 4 integers (RGBA).")

def qfont_to_dict(font: QFont) -> Dict[str, Any]:
    return {
        'family': font.family(),
        'pointSize': font.pointSize() if font.pointSize() != -1 else None,
        'pixelSize': font.pixelSize() if font.pixelSize() != -1 else None,
        'weight': font.weight(),
        'italic': font.italic(),
        'underline': font.underline(),
        'strikeOut': font.strikeOut()
    }

def dict_to_qfont(data: Dict[str, Any]) -> QFont:
    if not isinstance(data, dict):
        return QFont("Arial", 12)  # Safe default if passed a bool or None
    
    font = QFont()
    font.setFamily(data.get('family', "Arial"))

    if data.get('pixelSize') is not None:
        font.setPixelSize(data['pixelSize'])
    elif data.get('pointSize') is not None:
        font.setPointSize(data['pointSize'])

    if 'weight' in data:
        try:
            font.setWeight(QFont.Weight(data['weight']))  # ✅ Cast to enum
        except (ValueError, TypeError):
            font.setWeight(QFont.Weight.Normal)  # Fallback to Normal

    font.setItalic(data.get('italic', False))
    font.setUnderline(data.get('underline', False))
    font.setStrikeOut(data.get('strikeOut', False))
    return font


def qtalignment_to_str(alignment: Qt.AlignmentFlag) -> str:
    if alignment == Qt.AlignLeft | Qt.AlignTop: return "LeftTop"
    if alignment == Qt.AlignLeft | Qt.AlignVCenter: return "LeftCenter"
    if alignment == Qt.AlignLeft | Qt.AlignBottom: return "LeftBottom"
    if alignment == Qt.AlignCenter | Qt.AlignTop: return "CenterTop"
    if alignment == Qt.AlignCenter: return "Center"
    if alignment == Qt.AlignCenter | Qt.AlignBottom: return "CenterBottom"
    if alignment == Qt.AlignRight | Qt.AlignTop: return "RightTop"
    if alignment == Qt.AlignRight | Qt.AlignVCenter: return "RightCenter"
    if alignment == Qt.AlignRight | Qt.AlignBottom: return "RightBottom"
    return "Center"

def str_to_qtalignment(s: str) -> Qt.AlignmentFlag:
    if s == "LeftTop": return Qt.AlignLeft | Qt.AlignTop
    if s == "LeftCenter": return Qt.AlignLeft | Qt.AlignVCenter
    if s == "LeftBottom": return Qt.AlignLeft | Qt.AlignBottom
    if s == "CenterTop": return Qt.AlignCenter | Qt.AlignTop
    if s == "Center": return Qt.AlignCenter
    if s == "CenterBottom": return Qt.AlignCenter | Qt.AlignBottom
    if s == "RightTop": return Qt.AlignRight | Qt.AlignTop
    if s == "RightCenter": return Qt.AlignRight | Qt.AlignVCenter
    if s == "RightBottom": return Qt.AlignRight | Qt.AlignBottom
    return Qt.AlignCenter