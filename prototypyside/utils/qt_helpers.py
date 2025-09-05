# prototypyside/utils/qt_helpers.py
from __future__ import annotations
from collections import deque
import importlib

from typing import List, Tuple, Iterable, Type, Union, Dict, Any, Optional

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from prototypyside.services.proto_class import ProtoClass

def _resolve_types(
    specs: Optional[Iterable[object]],
    defaults: Iterable[str],
) -> Tuple[Tuple[type, ...], Tuple[str, ...]]:
    """
    Normalize an iterable of specs (types or strings) into:
      - a tuple of resolved types
      - a tuple of class names (for name-based fallback matching)
    """
    types: List[type] = []
    names: List[str] = []

    # helper to attempt import from dotted path
    def _import_dotted(path: str) -> Optional[type]:
        try:
            if "." not in path:
                return None
            mod_path, _, cls_name = path.rpartition(".")
            mod = importlib.import_module(mod_path)
            cls = getattr(mod, cls_name, None)
            return cls if isinstance(cls, type) else None
        except Exception:
            return None

    specs = list(specs) if specs is not None else []
    # If nothing provided, try all defaults
    if not specs:
        specs = list(defaults)

    # known modules to probe for short names
    known_modules = (
        "prototypyside.widgets.unit_str_field",
        "prototypyside.widgets.unit_strings_field",
        "prototypyside.widgets.unit_str_geometry_field",
    )

    for spec in specs:
        if isinstance(spec, type):
            types.append(spec)
            names.append(spec.__name__)
            continue
        if isinstance(spec, str):
            # First try dotted import
            t = _import_dotted(spec)
            if t is None:
                # Try known modules for short names
                for mod_name in known_modules:
                    try:
                        mod = importlib.import_module(mod_name)
                        maybe = getattr(mod, spec, None)
                        if isinstance(maybe, type):
                            t = maybe
                            break
                    except Exception:
                        pass
            if isinstance(t, type):
                types.append(t)
                names.append(t.__name__)
            else:
                # keep short name for fallback name-based match
                names.append(spec)
    # dedupe while preserving order
    seen = set()
    types = [t for t in types if not (t in seen or seen.add(t))]
    seen.clear()
    names = [n for n in names if not (n in seen or seen.add(n))]
    return tuple(types), tuple(names)

def find_unit_str_like_fields(
    root: QWidget,
    max_depth: int = 2,
    want_types: Optional[Tuple[Type[QWidget], ...]] = None,
    stop_at: Optional[Tuple[Type[QWidget], ...]] = None,
) -> List[QWidget]:
    """
    Breadth-first search for UnitStr-like widgets below `root` up to `max_depth`.

    Default behavior:
      - Collects UnitStrField, UnitStringsField, UnitStrGeometryField.
      - Includes container widgets (UnitStringsField / UnitStrGeometryField) in results,
        but does NOT descend into them.
    """
    default_want = (
        "prototypyside.widgets.unit_str_field.UnitStrField",
        "prototypyside.widgets.unit_strings_field.UnitStringsField",
        "prototypyside.widgets.unit_str_geometry_field.UnitStrGeometryField",
    )
    default_stop = (
        "prototypyside.widgets.unit_strings_field.UnitStringsField",
        "prototypyside.widgets.unit_str_geometry_field.UnitStrGeometryField",
    )

    want_types_resolved, want_names = _resolve_types(want_types, default_want)
    stop_types_resolved, stop_names = _resolve_types(stop_at, default_stop)

    results: List[QWidget] = []
    seen_ids = set()
    q = deque([(root, 0)])

    while q:
        widget, depth = q.popleft()

        # Collect if type matches or name matches (fallback)
        wtype = type(widget)
        wname = wtype.__name__
        if (want_types_resolved and isinstance(widget, want_types_resolved)) or (wname in want_names):
            wid = id(widget)
            if wid not in seen_ids:
                seen_ids.add(wid)
                results.append(widget)

        # Stop conditions
        if depth >= max_depth:
            continue
        if (stop_types_resolved and isinstance(widget, stop_types_resolved)) or (wname in stop_names):
            continue  # do not descend into containers by default

        # Recurse into direct QWidget children
        for child in widget.findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
            q.append((child, depth + 1))

    return results


def debug_print_tree(root: QWidget, max_depth=4):
    from collections import deque
    q = deque([(root, 0)])
    while q:
        w, d = q.popleft()
        print("  " * d + f"{d}: {type(w).__name__} | objectName={w.objectName()!r}")
        if d >= max_depth:
            continue
        for c in w.findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
            q.append((c, d + 1))

def make_point_font(f: QFont, dpi: float, default_pt: float = 12.0) -> QFont:
    """Return a *point-sized* copy of f. If f was pixel-locked, convert px->pt using passed dpi."""
    g = QFont(f)
    ps = g.pointSizeF()
    if ps is None or ps <= 0:
        px = g.pixelSize()
        if px and px > 0 and dpi and dpi > 0:
            ps = float(px) * 72.0 / float(dpi)
        else:
            ps = float(default_pt)
    # ensure point-sized & NOT pixel-locked
    g.setPixelSize(0)
    g.setPointSizeF(ps)
    return g
    
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