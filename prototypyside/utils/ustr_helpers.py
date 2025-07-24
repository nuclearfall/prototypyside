# ustr_helpers.py
import re
from typing import Optional, Union, Tuple
from decimal import Decimal
from PySide6.QtCore import QRectF, QPointF
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry

Number = Union[int, float, str, Decimal, UnitStr]

from PySide6.QtCore import QPointF, QRectF
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry


UNIT_RE = re.compile(r"^\s*(-?[0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]+)?\s*$")


UNIT_RE = re.compile(r"^\s*([+-]?\d+(?:\.\d+)?)\s*([a-zA-Z]+)?\s*$")

def get_unit(
    value: Union[UnitStr, UnitStrGeometry, str]
) -> str | None:
    """
    Extract the unit suffix from a string like "12.5in" or return
    value.unit if given a UnitStr or UnitStrGeometry.
    Returns None if no unit was present on the string.
    """
    # 1) handle raw strings
    if isinstance(value, str):
        text = value.strip()
        m = UNIT_RE.fullmatch(text)
        if not m:
            raise ValueError(f"Invalid dimension string: {value!r}")
        _, unit_from_str = m.groups()
        return unit_from_str  # may be None if the user omitted it

    # 2) handle our two custom types
    elif isinstance(value, (UnitStr, UnitStrGeometry)):
        return value.unit

    # 3) anything else is an immediate error
    else:
        raise ValueError(
            f"get_unit() expected str, UnitStr or UnitStrGeometry, not {type(value)}"
        )

def geometry_with_px_pos(
    geometry: UnitStrGeometry,
    px_pos: QPointF
) -> UnitStrGeometry:
    """
    Return a UnitStrGeometry with the same size/rect but a new position
    taken from px_pos (pixels), converted to inches at geometry.dpi.
    """
    # Convert pixel position → inches
    new_pos_x = UnitStr.from_px(px_pos.x(), dpi=geometry.dpi)
    new_pos_y = UnitStr.from_px(px_pos.y(), dpi=geometry.dpi)

    # Preserve width/height/rect (already UnitStr at geometry.dpi)
    return UnitStrGeometry(
        width=   geometry.width,
        height=  geometry.height,
        rect_x=  geometry.rect_x,
        rect_y=  geometry.rect_y,
        x=       new_pos_x,
        y=       new_pos_y,
        unit=    "in",
        dpi=     geometry.dpi
    )


def geometry_with_px_rect(
    geometry: UnitStrGeometry,
    px_rect: QRectF
) -> UnitStrGeometry:
    """
    Return a UnitStrGeometry with the same position but a new local rect
    taken from px_rect (pixels), converted to inches at geometry.dpi.
    """
    # Convert pixel‐space rect → inches
    new_rect_x = UnitStr.from_px(px_rect.x(),      dpi=geometry.dpi)
    new_rect_y = UnitStr.from_px(px_rect.y(),      dpi=geometry.dpi)
    new_width  = UnitStr.from_px(px_rect.width(),  dpi=geometry.dpi)
    new_height = UnitStr.from_px(px_rect.height(), dpi=geometry.dpi)

    # Preserve scene position (UnitStr at geometry.dpi)
    return UnitStrGeometry(
        width=   new_width,
        height=  new_height,
        rect_x=  new_rect_x,
        rect_y=  new_rect_y,
        x=       geometry.pos_x,
        y=       geometry.pos_y,
        unit=    "in",
        dpi=     geometry.dpi
    )

# reuse your existing UnitStr → DPM converter
def convert_unitstr_to_dpm(ustr: UnitStr, dpi: int) -> float:
    METERS_PER_INCH = Decimal("0.0254")
    INCHES_PER_METER = Decimal(1) / METERS_PER_INCH
    dpm_resolution = Decimal(dpi) * INCHES_PER_METER
    length_in_meters = ustr.value * METERS_PER_INCH
    return float(length_in_meters * dpm_resolution)

def convert_ustrgeom_to_dpm(
    ustrgeom: UnitStrGeometry,
    dpi: int
) -> Tuple[QRectF, QPointF]:
    """
    Convert a UnitStrGeometry’s local rect and scene pos into
    dot‐counts (at dots‐per‐meter) for any given DPI.

    Args:
      ustrgeom: your UnitStrGeometry (internally storing all
                coords & sizes as UnitStr in inches).
      dpi:      the “render” DPI you want to convert against.

    Returns:
      rect_dpm: QRectF(x_dots, y_dots, width_dots, height_dots)
      pos_dpm:  QPointF(x_dots, y_dots)
    """
    # grab the raw UnitStr fields (all in inches internally)
    ux = ustrgeom._rect_x
    uy = ustrgeom._rect_y
    uw = ustrgeom._w
    uh = ustrgeom._h
    px = ustrgeom._pos_x
    py = ustrgeom._pos_y

    # convert each to “dots”
    x_dots      = convert_unitstr_to_dpm(ux, dpi)
    y_dots      = convert_unitstr_to_dpm(uy, dpi)
    w_dots      = convert_unitstr_to_dpm(uw, dpi)
    h_dots      = convert_unitstr_to_dpm(uh, dpi)
    pos_x_dots  = convert_unitstr_to_dpm(px, dpi)
    pos_y_dots  = convert_unitstr_to_dpm(py, dpi)

    rect_dpm = QRectF(x_dots, y_dots, w_dots, h_dots)
    pos_dpm  = QPointF(pos_x_dots, pos_y_dots)
    return rect_dpm, pos_dpm