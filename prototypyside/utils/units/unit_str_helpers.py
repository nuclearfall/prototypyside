from PySide6.QtCore import QRectF, QPointF
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.units.unit_str import UnitStr
# import re
# from typing import Optional, Union, Tuple
# from decimal import Decimal
# from PySide6.QtCore import QRectF, QPointF
# from prototypyside.utils.units.unit_str import UnitStr
# from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry

# Number = Union[int, float, str, Decimal, UnitStr]

# from PySide6.QtCore import QPointF, QRectF


def geometry_with_px_rect(
    base: UnitStrGeometry,
    px_rect: QRectF,
    dpi: int
) -> UnitStrGeometry:
    """
    Return a new UnitStrGeometry whose rect (x,y,width,height)
    comes from px_rect converted into inches (via from_px),
    preserving base.dpi and the original x/y position.
    """
    dpi = dpi

    width  = UnitStr(px_rect.width(), unit="px", dpi=dpi)
    height = UnitStr(px_rect.height(), unit="px", dpi=dpi)
    rect_x = UnitStr(0, dpi=dpi)
    rect_y = UnitStr(0, dpi=dpi)

    # keep the original logical position
    x = base.x
    y = base.y

    return UnitStrGeometry(
        width=width,
        height=height,
        rect_x=rect_x,
        rect_y=rect_y,
        x=x,
        y=y,
        dpi=dpi,
    )


def geometry_with_px_pos(
    base: UnitStrGeometry,
    px_pos: QPointF,
    dpi: int
) -> UnitStrGeometry:
    """
    Return a new UnitStrGeometry whose position (x,y)
    comes from px_pos converted into inches (via from_px),
    preserving base.dpi and the original size/rect.
    """
    dpi = dpi

    x = UnitStr(px_pos.x(), "px", dpi=dpi)
    y = UnitStr(px_pos.y(), "px", dpi=dpi)
    # units are stored interally as inches. 
    return UnitStrGeometry(
        width=base.width,
        height=base.height,
        rect_x=base.rect_x,
        rect_y=base.rect_y,
        x=x,
        y=y,
        dpi=dpi,
    )
