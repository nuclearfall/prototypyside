# prototypyside/views/graphics_items.py

from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import QColor, QPen, QBrush, QCursor
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem, QGraphicsSceneMouseEvent
from typing import TYPE_CHECKING

from prototypyside.config import (
    HANDLE_SIZE, HANDLE_COLOR, HandleType
)

if TYPE_CHECKING:
    from prototypyside.models.game_component_elements import GameComponentElement
else:
    GameComponentElement = object


class ResizeHandle(QGraphicsRectItem):
    def __init__(self, parent_item: 'GameComponentElement', handle_type: HandleType):
        size = HANDLE_SIZE
        half_size = size / 2
        super().__init__(-half_size, -half_size, size, size, parent_item)

        self.setBrush(QBrush(HANDLE_COLOR))
        self.setPen(QPen(HANDLE_COLOR.darker(150)))

        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, False)
        self.setFlag(QGraphicsItem.ItemIgnoresParentOpacity, True)
        self.setAcceptedMouseButtons(Qt.LeftButton)  # ⬅️ Be explicit
        self.drag_started = False  # debounce flag
        self.handle_type = handle_type
        self.parent_element = parent_item
        self.start_pos = QPointF()
        self.start_scene_rect = QRectF()

        self.setCursor(self._get_cursor_for_handle_type(handle_type))

    def _get_cursor_for_handle_type(self, handle_type: HandleType) -> QCursor:
        if handle_type in [HandleType.TOP_LEFT, HandleType.BOTTOM_RIGHT]:
            return QCursor(Qt.SizeFDiagCursor)
        elif handle_type in [HandleType.TOP_RIGHT, HandleType.BOTTOM_LEFT]:
            return QCursor(Qt.SizeBDiagCursor)
        elif handle_type in [HandleType.TOP_CENTER, HandleType.BOTTOM_CENTER]:
            return QCursor(Qt.SizeVerCursor)
        elif handle_type in [HandleType.LEFT_CENTER, HandleType.RIGHT_CENTER]:
            return QCursor(Qt.SizeHorCursor)
        return QCursor(Qt.ArrowCursor)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        print(f"[DEBUG] Handle pressed: {self.handle_type}")
        event.accept() 


