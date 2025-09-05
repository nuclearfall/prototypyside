# overset_plus_item.py
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject
from PySide6.QtCore import Qt, QObject, QRectF, QPointF, QSize, Signal, QEvent
from PySide6.QtGui import (
    QColor,
    QFont,
    QPen,
    QBrush,
    QTextDocument,
    QTextOption,
    QPainter,
    QPixmap,
    QPalette,
    QAbstractTextDocumentLayout,
    QTextCursor,
    QTextBlockFormat,
    QPainterPath,
    QKeyEvent
)

class OversetPlusItem(QGraphicsObject):
    """
    Bottom-right overset badge like InDesign. Vector-drawn; clickable.
    Parent in local coords under the TextElement, so it moves with the frame.
    """
    clicked = Signal()

    def __init__(self, *, size: float = 14.0, padding: float = 2.0, parent=None):
        super().__init__(parent)
        self._size = 14.0
        self._radius = 3.0
        self._padding = 0.0
        self._fg = QColor(0, 0, 0)
        self._bg = QColor(255, 255, 255, 220)
        self.force_vector = True  # ensure vector path is used
        # Interaction: accept mouse, float above transforms, and be easily clickable
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFlag(QGraphicsObject.ItemIgnoresTransformations, True)
        self.setFlag(QGraphicsObject.ItemIsSelectable, False)
        self.setFlag(QGraphicsObject.ItemIsMovable, False)

    @property
    def is_collapse_mode(self) -> bool:
        return self._is_collapse_mode

    @is_collapse_mode.setter
    def is_collapse_mode(self, value: bool):
        if self._is_collapse_mode != value:
            self._is_collapse_mode = value
            self.update() # Redraw when state changes

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._size, self._size)


    # overset_plus_item.py

    def paint(self, painter: QPainter, option, widget=None):
        s = self._size
        r = self._radius

        # InDesign-style UI blue (match inline fallback)
        ui_blue = QColor(0, 175, 236)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Transparent box; blue stroke
        painter.setBrush(Qt.NoBrush)
        pen = QPen(ui_blue)
        pen.setWidthF(1.25)
        pen.setCosmetic(True)
        painter.setPen(pen)

        # Rounded box
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, s, s), r, r)
        painter.drawPath(path)

        # Vector plus in the same blue
        cx = s * 0.5
        cy = s * 0.5
        half = s * 0.28
        painter.drawLine(QPointF(cx - half, cy), QPointF(cx + half, cy))  # horizontal
        painter.drawLine(QPointF(cx, cy - half), QPointF(cx, cy + half))  # vertical

        painter.restore()

    def anchor_to_frame(self, frame_local_rect: QRectF) -> None:
        s = self._size
        pad = self._padding
        x = frame_local_rect.right() - s - pad
        y = frame_local_rect.bottom() - s - pad
        self.setPos(x, y)

    # Make sure we actually emit a click and swallow the event so it doesn't reach handles
    def mousePressEvent(self, ev):
        ev.accept()

    def mouseReleaseEvent(self, ev):
        if self.shape().contains(ev.position()):
            self.clicked.emit()
        ev.accept()

# from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject
# from PySide6.QtCore import Qt, QObject, QRectF, QPointF, QSize, Signal, QEvent
# from PySide6.QtGui import (
#     QColor,
#     QFont,
#     QPen,
#     QBrush,
#     QTextDocument,
#     QTextOption,
#     QPainter,
#     QPixmap,
#     QPalette,
#     QAbstractTextDocumentLayout,
#     QTextCursor, 
#     QTextBlockFormat,
#     QPainterPath,
#     QKeyEvent
# )
# class OversetPlusItem(QGraphicsObject):
#     """
#     Bottom-right overset badge like InDesign. Vector-drawn; clickable.
#     Parent in local coords under the TextElement, so it moves with the frame.
#     """
#     clicked = Signal()  # emitted on left-click

#     def __init__(self, *, size: float = 14.0, padding: float = 2.0, parent=None):
#         super().__init__(parent)
#         self._size = float(size)
#         self._padding = float(padding)
#         self.setAcceptedMouseButtons(Qt.LeftButton)
#         self.setAcceptHoverEvents(True)
#         self.setCursor(Qt.PointingHandCursor)
#         self.setFlag(QGraphicsObject.ItemIgnoresParentOpacity, True)

#     def boundingRect(self) -> QRectF:
#         # Local coords of this small badge
#         return QRectF(0, 0, self._size, self._size)

#     def paint(self, p: QPainter, opt, widget=None) -> None:
#         s = self._size
#         r = s * 0.22

#         # red rounded square
#         p.save()
#         p.setRenderHint(QPainter.Antialiasing, True)
#         p.setPen(Qt.NoPen)
#         p.setBrush(QBrush(QColor(237, 28, 36)))
#         rect = self.boundingRect()
#         path = QPainterPath()
#         path.addRoundedRect(rect, r, r)
#         p.drawPath(path)

#         # white plus
#         pen = QPen(Qt.white)
#         pen.setCapStyle(Qt.RoundCap)
#         pen.setWidthF(max(1.0, s * 0.15))
#         p.setPen(pen)
#         cx = rect.center().x()
#         cy = rect.center().y()
#         arm = s * 0.28
#         p.drawLine(QPointF(cx - arm, cy), QPointF(cx + arm, cy))
#         p.drawLine(QPointF(cx, cy - arm), QPointF(cx, cy + arm))
#         p.restore()

#     # Positioning API ---------------------------------------------------------
#     def anchor_to_frame(self, frame_local_rect: QRectF) -> None:
#         """
#         Position our top-left so the badge sits inside the frame's bottom-right,
#         with padding.
#         """
#         s = self._size
#         pad = self._padding
#         x = frame_local_rect.right() - s - pad
#         y = frame_local_rect.bottom() - s - pad
#         # NOTE: position is in parent's LOCAL coordinates
#         self.setPos(x, y)

#     # Interaction -------------------------------------------------------------
#     def mousePressEvent(self, ev) -> None:
#         if ev.button() == Qt.LeftButton:
#             self.clicked.emit()
#             ev.accept()
#             return
#         super().mousePressEvent(ev)