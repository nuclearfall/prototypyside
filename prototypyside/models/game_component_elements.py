from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QObject
from PySide6.QtGui import QColor, QFont, QPen, QBrush, QPainter
from PySide6.QtWidgets import QGraphicsItem, QGraphicsSceneDragDropEvent
from typing import Optional, Dict, Any
from prototypyside.views.graphics_items import ResizeHandle
from prototypyside.utils.qt_helpers import qrectf_to_list, list_to_qrectf
from prototypyside.utils.unit_converter import parse_dimension, format_dimension
from prototypyside.utils.style_serialization_helpers import save_style, load_style
from prototypyside.config import HandleType


class GameComponentElement(QGraphicsItem, QObject):
    element_changed = Signal()

    def __init__(self, name: str, rect: QRectF, parent_qobject: Optional[QObject] = None):
        QObject.__init__(self, parent_qobject)
        QGraphicsItem.__init__(self)
        self.element_type = None
        self.name = name
        self._rect = QRectF(0, 0, rect.width(), rect.height())
        self.setPos(rect.topLeft())

        self._style = {
                'color': QColor(0, 0, 0),
                'bg_color': QColor(255, 255, 255, 0),
                'border_color': QColor(0, 0, 0),
                'border_width': "1 px",
            }

        self._content: Optional[str] = None

        self.setFlags(
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self._handles: Dict[HandleType, ResizeHandle] = {}
        self.create_handles()

    def setPos(self, *args):
        print(f"[setPos] Called with: {args}")
        super().setPos(*args)
        self.element_changed.emit() # Emit when rectangle changes

    def setRect(self, rect):
        _, _, w, h = rect.getRect()
        self._rect = QRectF(0, 0, w, h)
        self.element_changed.emit() # Emit when rectangle changes

    def itemChange(self, change, value):
        print(f"[itemChange] Change: {change}, Value: {value}")
        return super().itemChange(change, value)

    def boundingRect(self) -> QRectF:
        # padding = max(10, self._style.get('border_width', 0))
        # return self._rect.adjusted(-padding, -padding, padding, padding)
        return self._rect
        
    def paint(self, painter: QPainter, option, widget=None):
        # Fill background
        bg_color = self._style.get("bg_color", QColor(255, 255, 255, 0))
        if not isinstance(bg_color, QColor):
            bg_color = QColor(bg_color)  # fallback
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self._rect)

        # Draw border if specified
        raw_border_width = self._style.get("border_width", "0")
        try:
            border_width = parse_dimension(self.get_border_width())
        except (ValueError, TypeError):
            border_width = 0

        if border_width > 0:
            border_color = self._style.get("border_color", QColor(0, 0, 0))
            if not isinstance(border_color, QColor):
                border_color = QColor(border_color)
            pen = QPen(border_color)
            pen.setWidthF(border_width)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self._rect)

        # Optional: draw resize handles
        if self.handles_visible:
            self.draw_handles()

    def to_dict(self) -> Dict[str, Any]:
        style_data = save_style(self._style)
        return {
            'type': self.__class__.__name__,
            'name': self.name,
            'rect': [self._rect.x(), self._rect.y(), self._rect.width(), self._rect.height()],
            'content': self._content,
            'style': style_data,
            'pos_x': self.pos().x(),
            'pos_y': self.pos().y(),
            'z_value': self.zValue()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], parent_qobject: Optional[QObject] = None) -> "GameComponentElement":
        from prototypyside.models.game_component_elements import create_element  # Avoid circular import

        name = data.get("name", "unnamed")
        rect = list_to_qrectf(data.get("rect", [0, 0, 100, 40]))
        element_type = data.get("type")

        # Use existing factory to create the correct subclass
        element = create_element(element_type, name, rect, parent_qobject)

        # Populate fields
        element._content = data.get("content")
        style_patch = load_style(data.get("style", {}))
        element._style.update(style_patch)
        element.setPos(QPointF(data.get("pos_x", 0), data.get("pos_y", 0)))
        element.setZValue(data.get("z_value", 0))

        return element


    def set_content(self, content: str):
        self._content = content
        self.element_changed.emit()
        self.update()

    def get_content(self) -> Optional[str]:
        return self._content

    def set_style_property(self, key: str, value: Any):
        if self._style.get(key) != value:
            self._style[key] = value
            self.element_changed.emit()
            self.update()

    def get_style(self):
        return self._style

    def get_name(self):
        return self.name

    def get_border_width(self):
        return self._style['border_width']

    def set_border_width(self, value):
        self._style['border_width'] = value

    @property
    def rect(self):
        return self._rect

    @property
    def handles_visible(self) -> bool:
        return any(handle.isVisible() for handle in self._handles.values())

    def create_handles(self):
        if self._handles:
            return
        for h_type in HandleType:
            handle = ResizeHandle(self, h_type)
            self._handles[h_type] = handle
        self.update_handles()

    def draw_handles(self):
        self.update_handles()
        for handle in self._handles.values():
            handle.show()

    def show_handles(self):
        for handle in self._handles.values():
            handle.show()

    def hide_handles(self):
        for handle in self._handles.values():
            handle.hide()

    def update_handles(self):
        w, h = self._rect.width(), self._rect.height()
        positions = {
            HandleType.TOP_LEFT: QPointF(0, 0),
            HandleType.TOP_CENTER: QPointF(w / 2, 0),
            HandleType.TOP_RIGHT: QPointF(w, 0),
            HandleType.RIGHT_CENTER: QPointF(w, h / 2),
            HandleType.BOTTOM_RIGHT: QPointF(w, h),
            HandleType.BOTTOM_CENTER: QPointF(w / 2, h),
            HandleType.BOTTOM_LEFT: QPointF(0, h),
            HandleType.LEFT_CENTER: QPointF(0, h / 2),
        }
        for handle_type, pos in positions.items():
            handle = self._handles.get(handle_type)
            if handle:
                handle.setPos(pos)

    def resize_from_handle(self, handle: ResizeHandle, delta: QPointF, start_scene_rect: QRectF):
        self.prepareGeometryChange()

        handle_type = handle.handle_type

        # Convert the scene-based starting rect into local item coordinates
        local_start_rect = self.mapRectFromScene(start_scene_rect)
        new_rect = QRectF(local_start_rect)

        # Convert delta to local coordinates
        delta_local = self.mapFromScene(self.mapToScene(QPointF(0, 0)) + delta) - QPointF(0, 0)

        # Adjust dimensions based on which handle is used
        if handle_type == HandleType.TOP_LEFT:
            new_rect.setTopLeft(new_rect.topLeft() + delta_local)
        elif handle_type == HandleType.TOP_RIGHT:
            new_rect.setTopRight(new_rect.topRight() + delta_local)
        elif handle_type == HandleType.BOTTOM_LEFT:
            new_rect.setBottomLeft(new_rect.bottomLeft() + delta_local)
        elif handle_type == HandleType.BOTTOM_RIGHT:
            new_rect.setBottomRight(new_rect.bottomRight() + delta_local)
        elif handle_type == HandleType.TOP_CENTER:
            new_rect.setTop(new_rect.top() + delta_local.y())
        elif handle_type == HandleType.BOTTOM_CENTER:
            new_rect.setBottom(new_rect.bottom() + delta_local.y())
        elif handle_type == HandleType.LEFT_CENTER:
            new_rect.setLeft(new_rect.left() + delta_local.x())
        elif handle_type == HandleType.RIGHT_CENTER:
            new_rect.setRight(new_rect.right() + delta_local.x())

        # Enforce minimum size
        min_w, min_h = 10, 10
        if new_rect.width() < min_w:
            new_rect.setWidth(min_w)
        if new_rect.height() < min_h:
            new_rect.setHeight(min_h)

        # ✅ Snap to grid if enabled in the scene
        scene = self.scene()
        if hasattr(scene, "is_snap_to_grid") and scene.is_snap_to_grid:
            top_left = scene.snap_to_grid(self.mapToScene(new_rect.topLeft()))
            bottom_right = scene.snap_to_grid(self.mapToScene(new_rect.bottomRight()))
            new_rect = self.mapRectFromScene(QRectF(top_left, bottom_right))

        # Calculate how much the top-left moved
        top_left_offset = new_rect.topLeft() - self._rect.topLeft()

        # Resize the internal rect
        self._rect = QRectF(0, 0, new_rect.width(), new_rect.height())

        # Move the item only if top-left changed
        if top_left_offset != QPointF(0, 0):
            self.setPos(self.pos() + top_left_offset)

        self.update()
        self.update_handles()
        self.element_changed.emit()

    def clone(self):
        """Clone the element via its serialized dictionary structure."""
        data = self.to_dict()
        data["name"] = f"{data['name']}_copy" if "name" in data else "unnamed_copy"
        return type(self).from_dict(data)



class TextElement(GameComponentElement):
    def __init__(self, name: str, rect: QRectF, parent_qobject: Optional[QObject] = None):
        super().__init__(name, rect, parent_qobject)

        self.element_type = "TextElement"
        self._style.update({
            'font': QFont("Arial", 12),
            'color': QColor(0, 0, 0),
            'alignment': Qt.AlignCenter,
        })

    def paint(self, painter: QPainter, option, widget=None):
        super().paint(painter, option, widget)
        painter.setFont(self._style.get("font", QFont("Arial", 12)))
        painter.setPen(self._style.get("color", QColor(0, 0, 0)))
        if self._content:
            painter.drawText(self._rect, self._style.get("alignment", Qt.AlignCenter), self._content)



class ImageElement(GameComponentElement):
    def __init__(self, name: str, rect: QRectF, parent_qobject: Optional[QObject] = None):
        super().__init__(name, rect, parent_qobject)

        self.element_type = "ImageElement"
        self._pixmap: Optional[QPixmap] = None
        self._content: Optional[str] = None
        self._style.update({
            'maintain_aspect': True,
            'alignment': Qt.AlignCenter,
        })
        self.setAcceptDrops(True)

    def set_content(self, content: str):
        self._content = content
        try:
            pixmap = QPixmap(content)
            self._pixmap = pixmap if not pixmap.isNull() else None
        except Exception:
            self._pixmap = None
        self.element_changed.emit()
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        super().paint(painter, option, widget)

        if self._pixmap:
            if self._style.get("maintain_aspect", True):
                scaled = self._pixmap.scaled(
                    self._rect.size().toSize(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                x = self._rect.x() + (self._rect.width() - scaled.width()) / 2
                y = self._rect.y() + (self._rect.height() - scaled.height()) / 2
                painter.drawPixmap(QPointF(x, y), scaled)
            else:
                painter.drawPixmap(self._rect.topLeft(), self._pixmap.scaled(
                    self._rect.size().toSize(),
                    Qt.IgnoreAspectRatio,
                    Qt.SmoothTransformation
                ))
        else:
            # Draw placeholder box and prompt
            painter.setPen(QPen(Qt.gray, 1, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self._rect)

            painter.setPen(QPen(Qt.darkGray))
            font = painter.font()
            font.setPointSize(10)
            font.setItalic(True)
            painter.setFont(font)

            placeholder_text = "Drop Image\nor Double Click to Set"
            painter.drawText(self._rect, Qt.AlignCenter, placeholder_text)

    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0]
            file_path = url.toLocalFile()
            if file_path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif")):
                self.set_content(file_path)
            event.acceptProposedAction()

    def mouseDoubleClickEvent(self, event):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(None, "Select Image", "", "Images (*.png *.jpg *.bmp *.gif)")
        if path:
            self.set_content(path)
    

def create_element(element_type: str, name: str, rect: QRectF, parent_qobject: Optional[QObject] = None) -> GameComponentElement:
    if element_type == "TextElement":
        return TextElement(name, rect, parent_qobject)
    elif element_type == "ImageElement":
        return ImageElement(name, rect, parent_qobject)
    else:
        return GameComponentElement(name, rect, parent_qobject)

