from PySide6.QtCore import QRectF, QPointF

from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry

def ustr_to_px(unit_str: "UnitStr", dpi: int | float | None = None) -> float:
    """
    Return the pixel value for `unit_str` at the requested DPI.

    If `dpi` is None, uses the UnitStr's own working DPI.
    """
    effective_dpi = unit_str.dpi if dpi is None else int(dpi)
    return unit_str.to(self.unit, dpi=effective_dpi)


def geometry_with_px_rect(
    base: UnitStrGeometry,
    px_rect: QRectF,
    dpi: int = 300
) -> UnitStrGeometry:
    """
    Return a new UnitStrGeometry whose rect (x,y,width,height)
    comes from px_rect converted into inches (via from_px),
    preserving base.dpi and the original x/y position.
    """

    width  = UnitStr(px_rect.width(), unit="px", dpi=dpi)
    height = UnitStr(px_rect.height(), unit="px", dpi=dpi)
    rect_x = UnitStr(0, dpi=dpi)
    rect_y = UnitStr(0, dpi=dpi)

    # keep the original logical position
    x = base.pos_x
    y = base.pos_y

    return UnitStrGeometry(
        width=width,
        height=height,
        rect_x=rect_x,
        rect_y=rect_y,
        x=base.pos_x,
        y=base.pos_y,
        dpi=dpi,
    )

def geometry_with_px_pos(
    base: UnitStrGeometry,
    px_pos: QPointF,
    dpi: int = 300
) -> UnitStrGeometry:
    """
    Return a new UnitStrGeometry whose position (x,y)
    comes from px_pos converted into inches (via from_px),
    preserving base.dpi and the original size/rect.
    """
    x = UnitStr(px_pos.x(), unit="px", dpi=dpi)
    y = UnitStr(px_pos.y(), unit="px", dpi=dpi)
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
