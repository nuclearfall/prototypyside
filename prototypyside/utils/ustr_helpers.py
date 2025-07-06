# ustr_helpers.py
from typing import Optional, Union
from decimal import Decimal
from PySide6.QtCore import QRectF, QPointF
from prototypyside.utils.unit_str import UnitStr
from prototypyside.utils.unit_str_geometry import UnitStrGeometry

Number = Union[int, float, str, Decimal, UnitStr]


def with_pos(
    geom: UnitStrGeometry,
    pos: Optional[QPointF] = None,
    *,
    x: Number | None = None,
    y: Number | None = None
) -> UnitStrGeometry:
    """
    Returns a new UnitStrGeometry with the same rectangular properties as `geom`,
    but with its scene-position set to `pos` (or to x, y).

    The new position values are interpreted as pixels if they are numbers.
    """
    if pos is not None and (x is not None or y is not None):
        raise ValueError("Provide either 'pos' or 'x' and 'y', not both.")

    new_x = pos.x() if pos is not None else x
    new_y = pos.y() if pos is not None else y

    if new_x is None or new_y is None:
        raise ValueError("Either 'pos' or both 'x' and 'y' must be provided.")

    return UnitStrGeometry(
        # Preserve original rect components by passing the UnitStr objects
        rect_x=0,
        rect_y=0,
        width=geom.width,
        height=geom.height,
        # Set the new position
        x=new_x,
        y=new_y,
        # Preserve settings
        dpi=geom.dpi,
        unit=geom.unit
    )

def with_rect(
    geom: UnitStrGeometry,
    rect: QRectF
) -> UnitStrGeometry:
    """
    Returns a new UnitStrGeometry with the same position as `geom`,
    but with its local rect (rect_x, rect_y, width, height) replaced by `rect`.

    The values in the new QRectF are interpreted as pixels.
    """
    rect = QRectF(0, 0, rect.width(), rect.height())
    return UnitStrGeometry(
        # Preserve original position by passing the UnitStr objects
        x=geom.pos_x,
        y=geom.pos_y,
        # Set the new rect from the QRectF (values treated as pixels)
        rect=rect,
        # Preserve settings
        dpi=geom.dpi,
        unit=geom.unit
    )