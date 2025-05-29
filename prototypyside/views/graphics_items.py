# prototypyside/views/graphics_items.py

from PySide6.QtCore import Qt, QRectF, QPointF
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
        
        # REMOVE THIS: Let mouseMoveEvent handle the "drag" via custom logic
        # self.setFlag(QGraphicsItem.ItemIsMovable) 
        
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setFlag(QGraphicsItem.ItemIgnoresParentOpacity) 
        
        # REMOVE THIS: Z-value is handled by parent_element.update_handles_position() setting it to 1
        # self.setZValue(parent_item.zValue() + 100000) 

        self.handle_type = handle_type
        self.parent_element = parent_item
        self.start_pos = QPointF()
        
        # Add new attribute for scene rect
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
        self.start_pos = event.scenePos()
        # Store SCENE bounding rect instead of local rect
        self.start_scene_rect = self.parent_element.sceneBoundingRect()
        self.parent_element.setSelected(True)
        event.accept()  # Important

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if event.buttons() == Qt.LeftButton:
            delta = event.scenePos() - self.start_pos
            # Pass scene rect instead of local rect
            self.parent_element.resize_from_handle(self.handle_type, delta, self.start_scene_rect)
            event.accept() # Prevent further propagation
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        self.parent_element.element_changed.emit()
        super().mouseReleaseEvent(event)