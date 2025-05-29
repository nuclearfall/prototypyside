# prototypyside/models/game_component_elements.py

from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QObject
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QImage, QPixmap
from PySide6.QtWidgets import QGraphicsItem, QGraphicsSceneMouseEvent
from typing import List, Dict, Any, Optional, Union, TYPE_CHECKING
from pathlib import Path

# Import constants from config
from prototypyside.config import MIN_ELEMENT_SIZE, HANDLE_SIZE, HandleType

# Import helper functions from utils
from prototypyside.utils.qt_helpers import (
    qrectf_to_list, qcolor_to_rgba, qfont_to_dict,
    rgba_to_qcolor, dict_to_qfont, qtalignment_to_str, str_to_qtalignment
)

# Import ResizeHandle (your custom handle class)
from prototypyside.views.graphics_items import ResizeHandle

# For type hinting GameComponentTemplate
if TYPE_CHECKING:
    from prototypyside.models.game_component_template import GameComponentTemplate
    from prototypyside.views.graphics_scene import GameComponentGraphicsScene



class GameComponentElement(QGraphicsItem, QObject): # Re-added QObject
    element_changed = Signal()

    def __init__(self, name: str, rect: QRectF, parent_qobject: QObject = None):
        QObject.__init__(self, parent_qobject)
        QGraphicsItem.__init__(self)
        self.name = name
        self._rect = rect
        # Store template for access to its properties, but parent_qobject manages Qt ownership
        self.template: Optional['GameComponentTemplate'] = None # Will be set by GameComponentTemplate.from_dict or add_element
        self._content: Optional[str] = None
        self._style: Dict[str, Any] = {
            'font': QFont("Arial", 12),
            'color': QColor(0, 0, 0),
            'bg_color': QColor(255, 255, 255, 0),
            'border_color': QColor(0, 0, 0),
            'border_width': 0,
            'alignment': Qt.AlignCenter
        }

        self._handles: Dict[HandleType, ResizeHandle] = {} # Corrected type hint for dict values
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setFlag(QGraphicsItem.ItemSendsScenePositionChanges)

        self.create_handles()
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True) # Ensure this is set for itemChange to fire on geometry changes

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            new_pos = value
            # Ensure the scene is a GameComponentGraphicsScene to access sceneRect
            if hasattr(self.scene(), 'sceneRect'):
                rect = self.scene().sceneRect()
                # Clamp to scene rect
                new_x = min(max(new_pos.x(), rect.left()), rect.right() - self._rect.width())
                new_y = min(max(new_pos.y(), rect.top()), rect.bottom() - self._rect.height())
                return QPointF(new_x, new_y)
        elif change == QGraphicsItem.ItemSelectedHasChanged:
            self.handle_selection_change(value)
        return super().itemChange(change, value)

    def create_handles(self):
        if not self._handles:
            handle_types = [
                HandleType.TOP_LEFT, HandleType.TOP_CENTER, HandleType.TOP_RIGHT,
                HandleType.LEFT_CENTER, HandleType.RIGHT_CENTER,
                HandleType.BOTTOM_LEFT, HandleType.BOTTOM_CENTER, HandleType.BOTTOM_RIGHT
            ]
            for h_type in handle_types:
                handle = ResizeHandle(self, h_type) # Parent handle to this QGraphicsItem
                self._handles[h_type] = handle
            self.update_handles_position()
            self.hide_handles()

    def update_handles_position(self):
        rect = self.boundingRect()
        center_x = rect.center().x()
        center_y = rect.center().y()

        handle_positions = {
            HandleType.TOP_LEFT: QPointF(rect.left(), rect.top()),
            HandleType.TOP_CENTER: QPointF(center_x, rect.top()),
            HandleType.TOP_RIGHT: QPointF(rect.right(), rect.top()),
            HandleType.RIGHT_CENTER: QPointF(rect.right(), center_y),
            HandleType.BOTTOM_RIGHT: QPointF(rect.right(), rect.bottom()),
            HandleType.BOTTOM_CENTER: QPointF(center_x, rect.bottom()),
            HandleType.BOTTOM_LEFT: QPointF(rect.left(), rect.bottom()),
            HandleType.LEFT_CENTER: QPointF(rect.left(), center_y),
        }

        for handle_type, handle_item in self._handles.items():
            handle_item.setPos(handle_positions[handle_type])

    def show_handles(self):
        for handle in self._handles.values():
            handle.setVisible(True)

    def hide_handles(self):
        for handle in self._handles.values():
            handle.setVisible(False)

    def handle_selection_change(self, selected: bool):
        for handle in self._handles.values():
            handle.setVisible(selected)

    def resize_from_handle(self, handle_type: HandleType, delta: QPointF, start_scene_rect: QRectF):
        new_scene_rect = QRectF(start_scene_rect)

        if handle_type == HandleType.TOP_LEFT:
            new_scene_rect.setTopLeft(start_scene_rect.topLeft() + delta)
        elif handle_type == HandleType.TOP_CENTER:
            new_scene_rect.setTop(start_scene_rect.top() + delta.y())
        elif handle_type == HandleType.TOP_RIGHT:
            new_scene_rect.setTopRight(start_scene_rect.topRight() + delta)
        elif handle_type == HandleType.LEFT_CENTER:
            new_scene_rect.setLeft(start_scene_rect.left() + delta.x())
        elif handle_type == HandleType.RIGHT_CENTER:
            new_scene_rect.setRight(start_scene_rect.right() + delta.x())
        elif handle_type == HandleType.BOTTOM_LEFT:
            new_scene_rect.setBottomLeft(start_scene_rect.bottomLeft() + delta)
        elif handle_type == HandleType.BOTTOM_CENTER:
            new_scene_rect.setBottom(start_scene_rect.bottom() + delta.y())
        elif handle_type == HandleType.BOTTOM_RIGHT:
            new_scene_rect.setBottomRight(start_scene_rect.bottomRight() + delta)

        # Enforce minimum size
        if new_scene_rect.width() < MIN_ELEMENT_SIZE:
            if handle_type in [HandleType.LEFT_CENTER, HandleType.TOP_LEFT, HandleType.BOTTOM_LEFT]:
                new_scene_rect.setLeft(new_scene_rect.right() - MIN_ELEMENT_SIZE)
            else:
                new_scene_rect.setWidth(MIN_ELEMENT_SIZE)

        if new_scene_rect.height() < MIN_ELEMENT_SIZE:
            if handle_type in [HandleType.TOP_CENTER, HandleType.TOP_LEFT, HandleType.TOP_RIGHT]:
                new_scene_rect.setTop(new_scene_rect.bottom() - MIN_ELEMENT_SIZE)
            else:
                new_scene_rect.setHeight(MIN_ELEMENT_SIZE)

        # Convert scene position to parent coordinates
        if self.parentItem():
            new_pos = self.parentItem().mapFromScene(new_scene_rect.topLeft())
        else:
            new_pos = new_scene_rect.topLeft()

        self.prepareGeometryChange()
        self.setPos(new_pos)
        self._rect = QRectF(0, 0, new_scene_rect.width(), new_scene_rect.height())
        self.update_handles_position()
        self.element_changed.emit()

    @classmethod
    def create(cls, element_type: str, name: str, rect: QRectF, parent_qobject: QObject = None) -> 'GameComponentElement':
        if element_type == "TextElement":
            return TextElement(name, rect, parent_qobject=parent_qobject)
        elif element_type == "ImageElement":
            return ImageElement(name, rect, parent_qobject=parent_qobject)
        elif element_type == "LabelElement":
            return LabelElement(name, rect, parent_qobject=parent_qobject)
        elif element_type == "ContainerElement":
            return ContainerElement(name, rect, parent_qobject=parent_qobject)
        else:
            raise ValueError(f"Unknown element type: {element_type}")

    def boundingRect(self) -> QRectF:
        return self._rect

    def set_content(self, content: str):
        if self._content != content:
            self._content = content
            self.element_changed.emit()
            self.update()

    def get_content(self) -> Optional[str]:
        return self._content

    def set_rect(self, new_rect: QRectF):
        if self._rect != new_rect:
            self.prepareGeometryChange()
            self._rect = new_rect
            self.element_changed.emit()
            self.update()
            self.update_handles_position()

    def set_style_property(self, key: str, value: Any):
        if self._style.get(key) != value:
            self._style[key] = value
            self.element_changed.emit()
            self.update()

    def paint(self, painter: QPainter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)

        if isinstance(self._style.get('bg_color'), QColor):
            painter.setBrush(QBrush(self._style['bg_color']))
        else:
            painter.setBrush(QBrush(QColor(255, 255, 255, 0)))

        if isinstance(self._style.get('border_color'), QColor) and \
           isinstance(self._style.get('border_width'), (int, float)):
            painter.setPen(QPen(self._style['border_color'], self._style['border_width']))
        else:
            painter.setPen(Qt.NoPen)

        painter.drawRect(0, 0, self._rect.width(), self._rect.height())

        if self.isSelected():
            selection_pen = QPen(Qt.darkBlue, 0, Qt.DotLine)
            painter.setPen(selection_pen)
            painter.setBrush(Qt.NoBrush)
            selection_rect = self.boundingRect().adjusted(-2, -2, 2, 2)
            painter.drawRect(selection_rect)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        self.element_changed.emit()
        super().mouseReleaseEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        super().mousePressEvent(event)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.__class__.__name__,
            'name': self.name,
            'rect': qrectf_to_list(self._rect),
            'content': self._content,
            'style': {
                'font': qfont_to_dict(self._style['font']),
                'color': qcolor_to_rgba(self._style['color']),
                'bg_color': qcolor_to_rgba(self._style['bg_color']),
                'border_color': qcolor_to_rgba(self._style['border_color']),
                'border_width': self._style['border_width'],
                'alignment': qtalignment_to_str(self._style['alignment'])
            },
            'pos_x': self.pos().x(),
            'pos_y': self.pos().y(),
            'z_value': self.zValue()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], template: 'GameComponentTemplate', parent_qobject: QObject = None) -> 'GameComponentElement':
        element_type = data.get('type', 'GameComponentElement')
        name = data.get('name', 'Unnamed')
        rect = QRectF(*data.get('rect', [0, 0, 50, 50]))

        # The 'template' parameter is passed here to the create method,
        # which will then pass it as 'parent_qobject' to the subclass constructors.
        instance = GameComponentElement.create(element_type, name, rect, template) # template is the parent_qobject for the element

        # After creating the instance, assign its template property
        instance.template = template

        if 'style' in data and isinstance(data['style'], Dict):
            instance.from_dict_style(data['style'])

        instance.set_content(data.get('content'))

        instance.setPos(data.get('pos_x', 0), data.get('pos_y', 0))
        instance.setZValue(data.get('z_value', 0))

        return instance

    def from_dict_style(self, style_data: Dict[str, Any]):
        if 'font' in style_data:
            if isinstance(style_data['font'], Dict):
                self._style['font'] = dict_to_qfont(style_data['font'])
            else:
                self._style['font'] = QFont("Arial", 12)
        if 'color' in style_data:
            if isinstance(style_data['color'], List):
                self._style['color'] = rgba_to_qcolor(style_data['color'])
            else:
                self._style['color'] = QColor(0, 0, 0)
        if 'bg_color' in style_data:
            if isinstance(style_data['bg_color'], List):
                self._style['bg_color'] = rgba_to_qcolor(style_data['bg_color'])
            else:
                self._style['bg_color'] = QColor(255, 255, 255, 0)
        if 'border_color' in style_data:
            if isinstance(style_data['border_color'], List):
                self._style['border_color'] = rgba_to_qcolor(style_data['border_color'])
            else:
                self._style['border_color'] = QColor(0, 0, 0)
        if 'border_width' in style_data:
            if isinstance(style_data['border_width'], (int, float)):
                self._style['border_width'] = style_data['border_width']
            else:
                self._style['border_width'] = 0
        if 'alignment' in style_data:
            if isinstance(style_data['alignment'], str):
                self._style['alignment'] = str_to_qtalignment(style_data['alignment'])
            else:
                self._style['alignment'] = Qt.AlignCenter
        self.update()


class TextElement(GameComponentElement):
    # Removed 'template' argument from __init__ for subclasses,
    # as 'parent_qobject' is the standard way to pass QObject parent.
    # The 'template' property will be assigned by GameComponentElement.from_dict or add_element.
    def __init__(self, name: str, rect: QRectF, parent_qobject: QObject = None):
        super().__init__(name, rect, parent_qobject) # Pass parent_qobject to base class
        self._style['bg_color'] = QColor(240, 240, 240, 100)
        self._style['alignment'] = Qt.AlignLeft | Qt.AlignTop

    def paint(self, painter: QPainter, option, widget):
        super().paint(painter, option, widget)

        if isinstance(self._style.get('font'), QFont):
            painter.setFont(self._style['font'])
        else:
            painter.setFont(QFont("Arial", 10))

        if isinstance(self._style.get('color'), QColor):
            painter.setPen(QPen(self._style['color']))
        else:
            painter.setPen(QPen(QColor(0, 0, 0)))

        if self._content is not None:
            if isinstance(self._style.get('alignment'), Qt.AlignmentFlag) or isinstance(self._style.get('alignment'), int):
                text_alignment = self._style['alignment']
            else:
                text_alignment = Qt.AlignCenter
            painter.drawText(self.boundingRect(), text_alignment, self._content)


class ImageElement(GameComponentElement):
    def __init__(self, name: str, rect: QRectF, parent_qobject: QObject = None):
        super().__init__(name, rect, parent_qobject)
        self._pixmap: Optional[QPixmap] = None
        self._original_content: Optional[str] = None

    def set_content(self, content: str):
        if self._original_content == content:
            return

        self._original_content = content
        if content and Path(content).exists():
            try:
                self._pixmap = QPixmap(content)
                if self._pixmap.isNull():
                    self._pixmap = None
            except Exception as e:
                self._pixmap = None
        else:
            self._pixmap = None

        self.element_changed.emit()
        self.update()

    def paint(self, painter: QPainter, option, widget):
        if self._pixmap and not self._pixmap.isNull():
            scaled_pixmap = self._pixmap.scaled(
                self.boundingRect().size().toSize(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            x = self.boundingRect().x() + (self.boundingRect().width() - scaled_pixmap.width()) / 2
            y = self.boundingRect().y() + (self.boundingRect().height() - scaled_pixmap.height()) / 2
            painter.drawPixmap(QPointF(x, y), scaled_pixmap)
        else:
            painter.setBrush(QColor(200, 200, 200, 100))
            painter.setPen(QPen(Qt.gray, 1, Qt.DashLine))
            painter.drawRect(self.boundingRect())
            painter.drawText(self.boundingRect(), Qt.AlignCenter, "Image Placeholder\n(CSV Path or Drag)")

        super().paint(painter, option, widget)


class LabelElement(GameComponentElement):
    def __init__(self, name: str, rect: QRectF, parent_qobject: QObject = None):
        super().__init__(name, rect, parent_qobject)
        self.set_content("Static Label")
        self._style['bg_color'] = QColor(255, 255, 255, 0)
        self._style['alignment'] = Qt.AlignCenter

    def paint(self, painter: QPainter, option, widget):
        super().paint(painter, option, widget)

        if isinstance(self._style.get('font'), QFont):
            painter.setFont(self._style['font'])
        else:
            painter.setFont(QFont("Arial", 10))

        if isinstance(self._style.get('color'), QColor):
            painter.setPen(QPen(self._style['color']))
        else:
            painter.setPen(QPen(QColor(0, 0, 0)))

        if self._content is not None:
            if isinstance(self._style.get('alignment'), Qt.AlignmentFlag) or isinstance(self._style.get('alignment'), int):
                text_alignment = self._style['alignment']
            else:
                text_alignment = Qt.AlignCenter
            painter.drawText(self.boundingRect(), text_alignment, self._content)


class ContainerElement(GameComponentElement):
    def __init__(self, name: str, rect: QRectF, parent_qobject: QObject = None):
        super().__init__(name, rect, parent_qobject)
        self._style['bg_color'] = QColor(100, 100, 255, 50)
        self._style['border_color'] = QColor(100, 100, 255)
        self._style['border_width'] = 2
        self.set_content("Container")

    def paint(self, painter: QPainter, option, widget):
        if isinstance(self._style.get('bg_color'), QColor):
            painter.setBrush(QBrush(self._style['bg_color']))
        else:
            painter.setBrush(QBrush(QColor(100, 100, 255, 50)))

        if isinstance(self._style.get('border_color'), QColor) and isinstance(self._style.get('border_width'), (int, float)):
            painter.setPen(QPen(self._style['border_color'], self._style['border_width'], Qt.DotLine))
        else:
            painter.setPen(QPen(QColor(100, 100, 255), 2, Qt.DotLine))

        painter.drawRect(self.boundingRect())

        if self._content:
            if isinstance(self._style.get('font'), QFont):
                painter.setFont(self._style['font'])
            else:
                painter.setFont(QFont("Arial", 10, QFont.Bold))

            if isinstance(self._style.get('color'), QColor):
                painter.setPen(QPen(self._style['color']))
            else:
                painter.setPen(QColor(50,50,50))

            painter.drawText(self.boundingRect(), Qt.AlignCenter, self._content)

        super().paint(painter, option, widget)