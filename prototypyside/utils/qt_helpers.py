# prototypyside/utils/qt_helpers.py

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter
from typing import List, Dict, Any
from PySide6.QtGui import QPainter

def resolve_painted_font(base_font: QFont, text_dpi: float) -> QFont:
    """
    Returns a copy of base_font scaled to pixels for the target text_dpi.
    base_font is expected to be point-sized (preferred).
    """
    f = QFont(base_font)  # copy

    # If someone set a pixel size upstream, normalize it back to pt for consistency
    if f.pixelSize() > 0:
        px = f.pixelSize()
        # Convert to pt using the *current* text_dpi as reference
        pt = (px * 72.0) / max(1.0, text_dpi)
        f.setPixelSize(-1)
        f.setPointSizeF(pt if pt > 0 else 12.0)

    # Ensure we have a valid point size
    pt = f.pointSizeF()
    if pt <= 0:
        pt = 12.0
        f.setPointSizeF(pt)

    # Now scale to pixels for painting on this device
    target_px = pt * (text_dpi / 72.0)
    # QFont expects int pixel sizes; rounding yields stable line-heights
    f.setPixelSize(int(round(target_px)))
    return f

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

def qfont_from_string(s: str) -> QFont:
    f = QFont()
    f.fromString(s)
    return f
    
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