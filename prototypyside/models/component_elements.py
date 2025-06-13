from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QObject
from PySide6.QtGui import QColor, QFont, QPen, QBrush, QPainter
from PySide6.QtWidgets import QGraphicsItem, QGraphicsSceneDragDropEvent
from typing import Optional, Dict, Any
from prototypyside.views.graphics_items import ResizeHandle
from prototypyside.utils.qt_helpers import qrectf_to_list, list_to_qrectf
from prototypyside.utils.unit_converter import parse_dimension, format_dimension
from prototypyside.utils.style_serialization_helpers import save_style, load_style
from prototypyside.config import HandleType


class ComponentElement(QGraphicsItem, QObject):
    element_changed = Signal()

    def __init__(self, pid, rect: QRectF,
                 parent_qobject: Optional[QObject] = None, name: str = "Element"):
        QObject.__init__(self, parent_qobject)
        QGraphicsItem.__init__(self)
        self._pid = pid 
        self.element_type = None
        self._name = name
        self._rect = QRectF(0, 0, rect.width(), rect.height())
        self.setPos(rect.topLeft())
        # Move properties from _style to direct instance variables
        self._color = QColor(Qt.black)
        self._bg_color = QColor(255,255,255,0)
        self._border_color = QColor(Qt.black)
        self._border_width = "1 px" # Stored as string, parsed for painting
        self._alignment = Qt.AlignLeft # Default alignment for generic elements

        self._content: Optional[str] = ""

        self.setFlags(
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self._handles: Dict[HandleType, ResizeHandle] = {}
        self.create_handles()

    # --- Property Getters and Setters (formerly handled by _style dict) ---
    @property
    def pid(self):
        return self._pid
    @property
    def name(self):
        return self._name

    @name.setter 
    def name(self, value):
        self._name = value
    
    @property
    def color(self) -> QColor:
        return self._color

    @color.setter
    def color(self, value: QColor):
        if self._color != value:
            self._color = value
            self.element_changed.emit()
            self.update()

    @property
    def bg_color(self) -> QColor:
        return self._bg_color

    @bg_color.setter
    def bg_color(self, value: QColor):
        if self._bg_color != value:
            self._bg_color = value
            self.element_changed.emit()
            self.update()

    @property
    def border_color(self) -> QColor:
        return self._border_color

    @border_color.setter
    def border_color(self, value: QColor):
        if self._border_color != value:
            self._border_color = value
            self.element_changed.emit()
            self.update()

    @property
    def border_width(self) -> str:
        return self._border_width

    @border_width.setter
    def border_width(self, value: str):
        if self._border_width != value:
            self._border_width = value
            self.element_changed.emit()
            self.update()

    @property
    def alignment(self) -> Qt.AlignmentFlag:
        return self._alignment

    @alignment.setter
    def alignment(self, value: Qt.AlignmentFlag):
        if self._alignment != value:
            self._alignment = value
            self.element_changed.emit()
            self.update()

    @property
    def content(self) -> Optional[str]:
        return self._content

    @content.setter
    def content(self, content: str):
        self._content = content
        self.element_changed.emit()
        self.update()

    @property
    def rect(self):
        return self._rect

    # --- End Property Getters and Setters ---

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

    def paint(self, painter: QPainter, option, widget=None):
        # Fill background
        bg_color = self.bg_color
        if not isinstance(bg_color, QColor):
            bg_color = QColor(bg_color)  # fallback
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self._rect)

        # Draw border if specified
        raw_border_width = self.border_width
        try:
            border_width = parse_dimension(self.border_width)
        except (ValueError, TypeError):
            border_width = 1

        if border_width > 0:
            border_color = self.border_color
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
        # Serialize properties directly
        return {
            'type': self.__class__.__name__,
            'name': self.name,
            'rect': [self._rect.x(), self._rect.y(), self._rect.width(), self._rect.height()],
            'content': self._content,
            'pos_x': self.pos().x(),
            'pos_y': self.pos().y(),
            'z_value': self.zValue(),
            'color': self.color.name(), # Serialize QColor to hex string
            'bg_color': self.bg_color.name(), # Serialize QColor to hex string
            'border_color': self.border_color.name(), # Serialize QColor to hex string
            'border_width': self.border_width, # Store as string
            'alignment': int(self.alignment), # Store Qt.AlignmentFlag as int
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], parent_qobject=None):
        name = data.get("name", "Element")
        rect = list_to_qrectf(data.get("rect", [0, 0, 100, 40]))

        element = create_element(data.get("type"), name, rect, parent_qobject)

        # Shared properties
        element.content      = data.get("content", "")
        element.color        = QColor(data.get("color", "#000000"))
        element.bg_color     = QColor(data.get("bg_color", "#ffffff"))
        element.border_color = QColor(data.get("border_color", "#000000"))
        element.border_width = data.get("border_width", element.border_width)
        element.alignment    = Qt.AlignmentFlag(data.get("alignment", int(Qt.AlignLeft)))
        element.setPos(QPointF(data.get("pos_x", 0), data.get("pos_y", 0)))
        element.setZValue(data.get("z_value", 0))

        return element



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



class TextElement(ComponentElement):
    def __init__(self, pid, rect: QRectF,
                 parent_qobject: Optional[QObject] = None, name: str = "Image Element"):

        super().__init__(pid, rect, parent_qobject, name)

        self.element_type = "TextElement"
        self._font = QFont("Arial", 12)
        self._content = "Sample Text"
        self.text = True


    # --- Text-specific Property Getters and Setters ---
    @property
    def font(self) -> QFont:
        return self._font

    @font.setter
    def font(self, value: QFont):
        if self._font != value:
            self._font = value
            self.element_changed.emit()
            self.update()
    # --- End Text-specific Property Getters and Setters ---

    def paint(self, painter: QPainter, option, widget=None):
        super().paint(painter, option, widget)
        painter.setFont(self.font) # Use direct font property
        painter.setPen(self.color) # Use direct color property
        if self._content:
            painter.drawText(self._rect, self.alignment, self._content) # Use direct alignment property

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data['font'] = self.font.toString()  # Serialize QFont to string
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any], parent_qobject=None):
        element = super().from_dict(data, parent_qobject)
        font_string = data.get("font", "Arial,12")
        font = QFont()
        if not font.fromString(font_string):
            print("Warning: Failed to parse font string:", font_string)
        element.font = font
        return element


class ImageElement(ComponentElement):
    def __init__(self, pid, rect: QRectF,
                 parent_qobject: Optional[QObject] = None, name: str = "Image Element"):
        super().__init__(pid, rect, parent_qobject, name)

        self.element_type = "ImageElement"
        self._pixmap: Optional[QPixmap] = None
        # _content is handled by ComponentElement
        self.alignment = Qt.AlignCenter
        # Image-specific properties
        self._keep_aspect = True
        # _alignment is already handled by super().__init__; if it differs,
        # subclass's init will override it. For ImageElement, it's AlignCenter by default.
        
        self.setAcceptDrops(True)

    # override the content getter/setter
    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, content: str):
        # Overriding to handle pixmap loading
        if self._content != content:
            self._content = content
            try:
                pixmap = QPixmap(content)
                self._pixmap = pixmap if not pixmap.isNull() else None
            except Exception as e:
                print(f"Error loading image '{content}': {e}")
                self._pixmap = None
            self.element_changed.emit()
            self.update()

    # --- Image-specific Property Getters and Setters ---
    @property
    def keep_aspect(self) -> bool:
        return self._keep_aspect

    @keep_aspect.setter
    def keep_aspect(self, value: bool):
        if self._keep_aspect != value:
            self._keep_aspect = value
            self.element_changed.emit()
            self.update()
    # --- End Image-specific Property Getters and Setters ---
    def to_dict(self):
        data = super().to_dict()
        data['keep_aspect'] = self.keep_aspect
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any], parent_qobject=None):
        element = super().from_dict(data, parent_qobject)
        element.keep_aspect = data.get("keep_aspect", True)
        return element

    def paint(self, painter: QPainter, option, widget=None):
        super().paint(painter, option, widget)

        if self._pixmap:
            if self.keep_aspect: # Use direct keep_aspect property
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
                self.content = file_path
            event.acceptProposedAction()

    def mouseDoubleClickEvent(self, event):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(None, "Select Image", "", "Images (*.png *.jpg *.bmp *.gif)")
        if path:
            self.content = path
    
def create_element(element_type: str, name: str, rect: QRectF, parent_qobject: Optional[QObject] = None) -> ComponentElement:
    if element_type == "TextElement":
        return TextElement(name, rect, parent_qobject)
    elif element_type == "ImageElement":
        return ImageElement(name, rect, parent_qobject)
    else:
        return ComponentElement(name, rect, parent_qobject)

