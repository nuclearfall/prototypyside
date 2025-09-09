# template_shape_factory.py
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPainterPath


import math

# ——— Template Shape Factory ———
class ShapeFactory:
    """
    Factory for generating QPainterPath shapes from a bounding QRectF.
    """
    @staticmethod
    def rect(rect: QRectF, extra=None) -> QPainterPath:
        path = QPainterPath()
        path.addRect(rect)
        return path

    @staticmethod
    def rounded_rect(rect: QRectF, radius: float) -> QPainterPath:
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)  # x & y
        return path

    @staticmethod
    def circle(rect: QRectF, extra=None) -> QPainterPath:
        path = QPainterPath()
        center = rect.center()
        radius = min(rect.width(), rect.height()) / 2.0
        path.addEllipse(center, radius, radius)
        return path

    @staticmethod
    def polygon(rect: QRectF, sides: int=4) -> QPainterPath:
        path = QPainterPath()
        cx = rect.center().x()
        cy = rect.center().y()
        r = min(rect.width(), rect.height()) / 2.0
        for i in range(sides):
            angle = math.radians(360.0 * i / sides - 90)
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.closeSubpath()
        return path

    def octagon(rect: QRectF) -> QPainterPath:
        return ShapeFactory.polygon(rect, 8)

    def pentagon(rect: QRectF) -> QPainterPath:
        return ShapeFactory.polygon(rect, 5)

    def diamond(rect: QRectF) -> QPainterPath:
        return ShapeFactory.polygon(rect, 4)
            
    def hexagon(rect: QRectF, extra=None) -> QPainterPath:
        return ShapeFactory.polygon(rect, 6)