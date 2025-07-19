from PySide6.QtCore import QRectF, QPointF
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.units.unit_str import UnitStr

def geometry_with_px_rect(
    base: UnitStrGeometry,
    px_rect: QRectF,
) -> UnitStrGeometry:
    """
    Return a new UnitStrGeometry whose rect (x,y,width,height)
    comes from px_rect converted into inches (via from_px),
    preserving base.dpi and the original x/y position.
    """
    dpi = base.dpi

    width  = UnitStr.from_px(px_rect.width(),  dpi=dpi)
    height = UnitStr.from_px(px_rect.height(), dpi=dpi)
    rect_x = UnitStr.from_px(px_rect.x(),      dpi=dpi)
    rect_y = UnitStr.from_px(px_rect.y(),      dpi=dpi)

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
) -> UnitStrGeometry:
    """
    Return a new UnitStrGeometry whose position (x,y)
    comes from px_pos converted into inches (via from_px),
    preserving base.dpi and the original size/rect.
    """
    dpi = base.dpi

    x = UnitStr.from_px(px_pos.x(), dpi=dpi)
    y = UnitStr.from_px(px_pos.y(), dpi=dpi)
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
