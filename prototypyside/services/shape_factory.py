# template_shape_factory.py
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPainterPath

from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry


import math

# ——— Template Shape Factory ———
class ShapeFactory:
    """
    Factory for generating QPainterPath shapes from a bounding QRectF.
    """
    @staticmethod
    def rect(_ugeom: UnitStrGeometry, extra=None, unit="px") -> QPainterPath:
        _rect = _ugeom.to(unit, dpi=_ugeom.dpi).rect
        path = QPainterPath()
        path.addRect(_rect)
        return path

    @staticmethod
    def rounded_rect(_ugeom: UnitStrGeometry, extra=None, unit="px") -> QPainterPath:
        _rect = _ugeom.to(unit, dpi=_ugeom.dpi).rect
        radius = extra.to(unit, dpi=_ugeom.dpi)
        path = QPainterPath()
        if extra != None:
            path.addRoundedRect(_rect, radius, radius)  # x & y
        else:
            path.addRect(_rect) 
        return path

    @staticmethod
    def oval(_ugeom: UnitStrGeometry, extra=None, unit="px") -> QPainterPath:
        _rect = _ugeom.to(unit, dpi=_ugeom.dpi).rect
        path = QPainterPath()
        center = _rect.center()
        rx = _rect.width() / 2.0   # horizontal radius
        ry = _rect.height() / 2.0  # vertical radius
        path.addEllipse(center, rx, ry)
        return path

    @staticmethod
    # will default to a triangular polygon if extra (sides) is not given.
    def polygon(_ugeom: UnitStrGeometry, extra=3, unit="px") -> QPainterPath:
        _rect = _ugeom.to(unit, dpi=_ugeom.dpi).rect
        path = QPainterPath()
        cx = _rect.center().x()
        cy = _rect.center().y()

        # Separate radii for width and height
        rx = _rect.width() / 2.0
        ry = _rect.height() / 2.0

        for i in range(extra):
            angle = math.radians(360.0 * i / extra - 90)
            x = cx + rx * math.cos(angle)
            y = cy + ry * math.sin(angle)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        path.closeSubpath()
        return path

    def octagon(_ugeom: UnitStrGeometry, extra=None, unit="px") -> QPainterPath:
        _rect = _ugeom.to(unit, dpi=_ugeom.dpi).rect
        return ShapeFactory.polygon(_rect, 8)

    def diamond(_ugeom: UnitStrGeometry, extra=None, unit="px") -> QPainterPath:
        _rect = _ugeom.to(unit, dpi=_ugeom.dpi).rect
        return ShapeFactory.polygon(_rect, 4)

    def triangle(_ugeom: UnitStrGeometry, extra=3, unit="px"):
        _rect = _ugeom.to(unit, dpi=_ugeom.dpi).rect
        return ShapeFactory.polygon(_rect, 3)
            
    def hexagon(_ugeom: UnitStrGeometry, extra=None, unit="px") -> QPainterPath:
        _rect = _ugeom.to(unit, dpi=_ugeom.dpi).rect
        return ShapeFactory.polygon(rect, 6)