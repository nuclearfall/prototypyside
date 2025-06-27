from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QObject
from PySide6.QtGui import QColor, QFont, QPen, QBrush, QPainter
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QGraphicsSceneDragDropEvent
from typing import Optional, Dict, Any
from prototypyside.views.graphics_items import ResizeHandle
from prototypyside.utils.qt_helpers import qrectf_to_list, list_to_qrectf
from prototypyside.utils.unit_converter import parse_dimension, format_dimension
from prototypyside.utils.unit_str import UnitStr
from prototypyside.utils.style_serialization_helpers import save_style, load_style
from prototypyside.config import HandleType

class ComponentElement(QGraphicsObject):
    element_changed = Signal()

    def __init__(self, pid, rect: QRectF, pos:QPointF, template_pid = None,
                 parent: Optional[QGraphicsObject] = None, name: str = None):
        super().__init__(parent)
        self._pid = pid
        self._template_pid = template_pid

        self._dpi = parent.dpi if parent and hasattr(parent, "dpi") else 300

        self._x = UnitStr(pos.x(), unit="in")
        self._y = UnitStr(pos.y(), unit="in")
        self._width = UnitStr(rect.width(), unit="in")
        self._height = UnitStr(rect.height(), unit="in")

        self._name = name

        # Set the QGraphicsItem position (scene expects px)
        self.setPos(self._x.to("px", self._dpi), self._y.to("px", self._dpi))
        self._color = QColor(Qt.black)
        self._bg_color = QColor(255,255,255,0)
        self._border_color = QColor(Qt.black)
        self._border_width = UnitStr("0.05 pt", dpi=self._dpi)
        self._alignment = Qt.AlignLeft
        self._content: Optional[str] = ""

        self.setFlags(
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self._handles: Dict[HandleType, ResizeHandle] = {}
        self.create_handles()


    # --- Property Getters and Setters --- #

    @property
    def template_pid(self):
        return self._template_pid 

    @template_pid.setter
    def template_pid(self, pid_val):
        if self._template_pid != pid_val:
            self._template_pid = pid_val
            self.element_changed.emit()
            self.update()

    @property
    def pid(self):
        return self._pid

    @pid.setter 
    def pid(self, pid_str):
        if self._pid != pid_str:
            self._pid = pid_str
            self.element_changed.emit()
            self.update()

    @property
    def name(self):
        return self._name

    @name.setter 
    def name(self, value):
        if self._name != value:
            self._name = value
            self.element_changed.emit()
    
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
    def border_width(self) -> "UnitStr":
        return self._border_width

    @border_width.setter
    def border_width(self, value):
        # Accept a UnitStr, string, or number (as current unit)
        if isinstance(value, UnitStr):
            bw = value
        elif isinstance(value, (int, float)):
            # Assume in current canonical unit (e.g., "pt")
            bw = UnitStr(value, unit="pt", dpi=self._dpi)
        elif isinstance(value, str):
            bw = UnitStr(value, dpi=self._dpi)
        else:
            raise ValueError("Unsupported type for border_width")
        
        if getattr(self, "_border_width", None) != bw:
            self._border_width = bw
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
    def unit(self):
        return self._unit

    @property
    def rect(self):
        # Always returns rect in px, local coordinates (0,0)
        return QRectF(
            0, 0,
            self._width.to("px", self._dpi),
            self._height.to("px", self._dpi)
        )

    @rect.setter
    def rect(self, qrectf: QRectF):
        # Accepts a QRectF in px; updates logical size, but never position!
        self.prepareGeometryChange()
        self._width = UnitStr(qrectf.width() / self._dpi, unit="in", dpi=self._dpi)
        self._height = UnitStr(qrectf.height() / self._dpi, unit="in", dpi=self._dpi)
        self.element_changed.emit()
        self.update()

    def setPos(self, *args):
        # Store both logical and px position
        if len(args) == 1 and isinstance(args[0], QPointF):
            pt_px = args[0]
        elif len(args) == 2:
            pt_px = QPointF(args[0], args[1])
        else:
            raise ValueError("setPos expects QPointF or x, y")
        self._x = UnitStr(pt_px.x() / self._dpi, unit="in", dpi=self._dpi)
        self._y = UnitStr(pt_px.y() / self._dpi, unit="in", dpi=self._dpi)
        super().setPos(pt_px)
        self.element_changed.emit()
        self.update()

    def resize_from_handle(self, handle_type: HandleType, delta: QPointF, start_scene_rect: QRectF):
        """Resize by handle: supports all 8 directions with proper boundary constraints."""
        self.prepareGeometryChange()
        dpi = getattr(self, "_dpi", 300)
        scene = self.scene()
        scene_rect = scene.sceneRect() if scene else QRectF()

        # 1. Convert starting rect and delta to local coordinates
        local_start_rect = self.mapRectFromScene(start_scene_rect)
        new_rect = QRectF(local_start_rect)
        delta_local = self.mapFromScene(delta) - self.mapFromScene(QPointF(0, 0))

        # 2. Update rect based on handle type
        if handle_type == HandleType.TOP_LEFT:
            new_rect.setTopLeft(new_rect.topLeft() + delta_local)
        elif handle_type == HandleType.TOP_CENTER:
            new_rect.setTop(new_rect.top() + delta_local.y())
        elif handle_type == HandleType.TOP_RIGHT:
            new_rect.setTopRight(new_rect.topRight() + delta_local)
        elif handle_type == HandleType.RIGHT_CENTER:
            new_rect.setRight(new_rect.right() + delta_local.x())
        elif handle_type == HandleType.BOTTOM_RIGHT:
            new_rect.setBottomRight(new_rect.bottomRight() + delta_local)
        elif handle_type == HandleType.BOTTOM_CENTER:
            new_rect.setBottom(new_rect.bottom() + delta_local.y())
        elif handle_type == HandleType.BOTTOM_LEFT:
            new_rect.setBottomLeft(new_rect.bottomLeft() + delta_local)
        elif handle_type == HandleType.LEFT_CENTER:
            new_rect.setLeft(new_rect.left() + delta_local.x())

        # 3. Enforce minimum size (10x10 pixels)
        min_size = 10
        if new_rect.width() < min_size:
            if handle_type in (HandleType.LEFT_CENTER, HandleType.TOP_LEFT, HandleType.BOTTOM_LEFT):
                new_rect.setLeft(new_rect.right() - min_size)
            else:
                new_rect.setRight(new_rect.left() + min_size)
        if new_rect.height() < min_size:
            if handle_type in (HandleType.TOP_CENTER, HandleType.TOP_LEFT, HandleType.TOP_RIGHT):
                new_rect.setTop(new_rect.bottom() - min_size)
            else:
                new_rect.setBottom(new_rect.top() + min_size)

        # 4. Constrain to scene boundaries
        new_scene_rect = self.mapRectToScene(new_rect)
        
        # Left boundary
        if new_scene_rect.left() < scene_rect.left():
            offset = scene_rect.left() - new_scene_rect.left()
            if handle_type in (HandleType.LEFT_CENTER, HandleType.TOP_LEFT, HandleType.BOTTOM_LEFT):
                new_rect.setLeft(new_rect.left() + offset)
            else:
                new_rect.setRight(new_rect.right() - offset)
        
        # Top boundary
        if new_scene_rect.top() < scene_rect.top():
            offset = scene_rect.top() - new_scene_rect.top()
            if handle_type in (HandleType.TOP_CENTER, HandleType.TOP_LEFT, HandleType.TOP_RIGHT):
                new_rect.setTop(new_rect.top() + offset)
            else:
                new_rect.setBottom(new_rect.bottom() - offset)
        
        # Right boundary
        if new_scene_rect.right() > scene_rect.right():
            offset = new_scene_rect.right() - scene_rect.right()
            new_rect.setRight(new_rect.right() - offset)
        
        # Bottom boundary
        if new_scene_rect.bottom() > scene_rect.bottom():
            offset = new_scene_rect.bottom() - scene_rect.bottom()
            new_rect.setBottom(new_rect.bottom() - offset)

        # 5. Snap to grid if enabled
        if hasattr(scene, "is_snap_to_grid") and scene.is_snap_to_grid:
            snapped_tl = scene.snap_to_grid(self.mapToScene(new_rect.topLeft()))
            snapped_br = scene.snap_to_grid(self.mapToScene(new_rect.bottomRight()))
            new_rect = self.mapRectFromScene(QRectF(snapped_tl, snapped_br))

        # 6. Update position and dimensions
        new_scene_pos = self.mapToScene(new_rect.topLeft())
        self.setPos(new_scene_pos)
        
        # Update logical units (convert from pixels to inches)
        self._x = UnitStr(new_scene_pos.x() / dpi, unit="in", dpi=dpi)
        self._y = UnitStr(new_scene_pos.y() / dpi, unit="in", dpi=dpi)
        self._width = UnitStr(new_rect.width() / dpi, unit="in", dpi=dpi)
        self._height = UnitStr(new_rect.height() / dpi, unit="in", dpi=dpi)
        
        # Update the local rect
        self._rect = QRectF(0, 0, new_rect.width(), new_rect.height())
        
        # Final updates
        self.update_handles()
        self.element_changed.emit()
        self.update()


    # --- Rotation/Flip support ---
    @property
    def rotation(self):
        return self._rotation

    @rotation.setter
    def rotation(self, angle_deg):
        self._rotation = angle_deg % 360
        self.setTransform(self._build_transform())
        self.element_changed.emit()

    def flip_x(self):
        self._flipped_x = not self._flipped_x
        self.setTransform(self._build_transform())
        self.element_changed.emit()

    def flip_y(self):
        self._flipped_y = not self._flipped_y
        self.setTransform(self._build_transform())
        self.element_changed.emit()

    def _build_transform(self):
        t = QTransform()
        cx = self._width.to("px", self._dpi) / 2
        cy = self._height.to("px", self._dpi) / 2
        t.translate(cx, cy)
        if self._flipped_x:
            t.scale(-1, 1)
        if self._flipped_y:
            t.scale(1, -1)
        t.rotate(self._rotation)
        t.translate(-cx, -cy)
        return t

    def boundingRect(self):
        return QRectF(0, 0, self._width.to("px", self._dpi), self._height.to("px", self._dpi))


    def itemChange(self, change, value):
        return super().itemChange(change, value)

    def paint(self, painter: QPainter, option, widget=None):
        # Fill background
        bg_color = self.bg_color
        if not isinstance(bg_color, QColor):
            bg_color = QColor(bg_color)  # fallback
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect)

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
            painter.drawRect(self.rect)

        # Optional: draw resize handles
        if self.handles_visible:
            self.draw_handles()

    def to_dict(self):
        """Serialize the element to a dictionary with logical units."""
        return {
            "pid": self._pid,
            "template_pid": self._template_pid,
            "name": self._name,
            "x": self._x.raw if self._x else "0 in",
            "y": self._y.raw if self._y else "0 in",
            "width": self._width.raw if self._width else "0.5 in",
            "height": self._height.raw if self._height else "0.5 in",
            "color": self._color.rgba() if self._color else None,  # Modified for alpha
            "bg_color": self._bg_color.rgba() if self._bg_color else None, # Modified for alpha
            "border_color": self._border_color.rgba() if self._border_color else None, # Modified for alpha
            "border_width": self._border_width.raw if self._border_width else "0.05 pt",
            "alignment": int(self._alignment) if self._alignment is not None else None,
            "content": self._content if self._content is not None else "",
            # Add subclass/extra fields as needed.
        }

    @classmethod
    def from_dict(cls, data, parent=None, dpi=300):
        pid = data.get("pid")
        # Defensive: always provide default valid unit strings
        pos_x = data.get("x", "0 in") or "0 in"
        pos_y = data.get("y", "0 in") or "0 in"
        rect_width = data.get("width", "1 in") or "1 in"
        rect_height = data.get("height", "1 in") or "1 in"

        # Convert to floats in logical units (inches) for rect and pos
        rect = QRectF(
            0, 0,
            UnitStr(rect_width, dpi=dpi).to("in", dpi),
            UnitStr(rect_height, dpi=dpi).to("in", dpi)
        )
        pos = QPointF(
            UnitStr(pos_x, dpi=dpi).to("in", dpi),
            UnitStr(pos_y, dpi=dpi).to("in", dpi)
        )
        template_pid = data.get("template_pid")
        name = data.get("name", None)

        obj = cls(
            pid=pid,
            rect=rect,
            pos=pos,
            template_pid=template_pid,
            parent=parent,
            name=name
        )
        # Restore style and other fields
        if "color" in data and data["color"] is not None:
            obj._color = QColor.fromRgba(data["color"])
        if "bg_color" in data and data["bg_color"] is not None:
            obj._bg_color = QColor.fromRgba(data["bg_color"])
        if "border_color" in data and data["border_color"] is not None:
            obj._border_color = QColor.fromRgba(data["border_color"])

        if "border_width" in data and data["border_width"]:
            obj._border_width = UnitStr(data["border_width"], dpi=dpi)
        if "alignment" in data and data["alignment"] is not None:
            obj._alignment = int(data["alignment"])
        if "content" in data and data["content"] is not None:
            obj._content = data["content"]
        # Handle subclass-specific fields (see below)
        return obj

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
        # Always get handle positions from current UnitStr and DPI
        w = self._width.to("px", self._dpi)
        h = self._height.to("px", self._dpi)
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

    # def resize_from_handle(self, handle: ResizeHandle, delta: QPointF, start_scene_rect: QRectF):
    #     self.prepareGeometryChange()

    #     handle_type = handle.handle_type

    #     # Convert the scene-based starting rect into local item coordinates
    #     local_start_rect = self.mapRectFromScene(start_scene_rect)
    #     new_rect = QRectF(local_start_rect)

    #     # Convert delta to local coordinates
    #     delta_local = self.mapFromScene(self.mapToScene(QPointF(0, 0)) + delta) - QPointF(0, 0)

    #     # Adjust dimensions based on which handle is used
    #     if handle_type == HandleType.TOP_LEFT:
    #         new_rect.setTopLeft(new_rect.topLeft() + delta_local)
    #     elif handle_type == HandleType.TOP_RIGHT:
    #         new_rect.setTopRight(new_rect.topRight() + delta_local)
    #     elif handle_type == HandleType.BOTTOM_LEFT:
    #         new_rect.setBottomLeft(new_rect.bottomLeft() + delta_local)
    #     elif handle_type == HandleType.BOTTOM_RIGHT:
    #         new_rect.setBottomRight(new_rect.bottomRight() + delta_local)
    #     elif handle_type == HandleType.TOP_CENTER:
    #         new_rect.setTop(new_rect.top() + delta_local.y())
    #     elif handle_type == HandleType.BOTTOM_CENTER:
    #         new_rect.setBottom(new_rect.bottom() + delta_local.y())
    #     elif handle_type == HandleType.LEFT_CENTER:
    #         new_rect.setLeft(new_rect.left() + delta_local.x())
    #     elif handle_type == HandleType.RIGHT_CENTER:
    #         new_rect.setRight(new_rect.right() + delta_local.x())

    #     # Enforce minimum size
    #     min_w, min_h = 10, 10
    #     if new_rect.width() < min_w:
    #         new_rect.setWidth(min_w)
    #     if new_rect.height() < min_h:
    #         new_rect.setHeight(min_h)

    #     # ✅ Snap to grid if enabled in the scene
    #     scene = self.scene()
    #     if hasattr(scene, "is_snap_to_grid") and scene.is_snap_to_grid:
    #         top_left = scene.snap_to_grid(self.mapToScene(new_rect.topLeft()))
    #         bottom_right = scene.snap_to_grid(self.mapToScene(new_rect.bottomRight()))
    #         new_rect = self.mapRectFromScene(QRectF(top_left, bottom_right))

    #     # Calculate how much the top-left moved
    #     top_left_offset = new_rect.topLeft() - self.rect.topLeft()

    #     # --- UNITSTR ADJUSTMENT: update logical model from new px values ---
    #     dpi = getattr(self, "_dpi", 300)
    #     self._width = UnitStr(new_rect.width() / dpi, unit="in", dpi=dpi)
    #     self._height = UnitStr(new_rect.height() / dpi, unit="in", dpi=dpi)
    #     # You may also want to update _x and _y if origin moves:
    #     # If your model stores _x, _y in physical units:
    #     if hasattr(self, "_x") and hasattr(self, "_y"):
    #         self._x = UnitStr(self.pos().x() / dpi, unit="in", dpi=dpi)
    #         self._y = UnitStr(self.pos().y() / dpi, unit="in", dpi=dpi)

    #     # Resize the internal rect (scene/display)
    #     self.rect = QRectF(0, 0, new_rect.width(), new_rect.height())

    #     # Move the item only if top-left changed
    #     if top_left_offset != QPointF(0, 0):
    #         self.setPos(self.pos() + top_left_offset)

    #     self.update()
    #     self.update_handles()
    #     self.element_changed.emit()


    def clone(self):
        """Clone the element via its serialized dictionary structure."""
        data = self.to_dict()
        data["name"] = None
        return type(self).from_dict(data)



class TextElement(ComponentElement):
    def __init__(self, pid, rect: QRectF, pos:QPointF, template_pid = None,
                 parent: Optional[QGraphicsObject] = None, name: str = None):

        super().__init__(pid, rect, pos, template_pid, parent, name)

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
            painter.drawText(self.rect, self.alignment, self._content) # Use direct alignment property

    def to_dict(self):
        data = super().to_dict()
        data['font'] = self.font.toString()  # Serialize QFont to string
        return data

    @classmethod
    def from_dict(cls, data, parent=None, dpi=300):
        element = super().from_dict(data, parent=parent, dpi=dpi)
        font_string = data.get("font", "Arial,12")
        font = QFont()
        font.fromString(font_string)
        element.font = font
        return element

class ImageElement(ComponentElement):
    def __init__(self, pid, rect: QRectF, pos:QPointF, template_pid = None,
                 parent: Optional[QGraphicsObject] = None, name: str = None):
        super().__init__(pid, rect, pos, template_pid, parent, name)

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
    def from_dict(cls, data, parent=None, dpi=300):
        element = super().from_dict(data, parent=parent, dpi=dpi)
        element.keep_aspect = data.get("keep_aspect", True)
        return element

    def paint(self, painter: QPainter, option, widget=None):
        super().paint(painter, option, widget)

        if self._pixmap:
            if self.keep_aspect: # Use direct keep_aspect property
                scaled = self._pixmap.scaled(
                    self.rect.size().toSize(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                x = self.rect.x() + (self.rect.width() - scaled.width()) / 2
                y = self.rect.y() + (self.rect.height() - scaled.height()) / 2
                painter.drawPixmap(QPointF(x, y), scaled)
            else:
                painter.drawPixmap(self.rect.topLeft(), self._pixmap.scaled(
                    self.rect.size().toSize(),
                    Qt.IgnoreAspectRatio,
                    Qt.SmoothTransformation
                ))
        else:
            # Draw placeholder box and prompt
            painter.setPen(QPen(Qt.gray, 1, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.rect)

            painter.setPen(QPen(Qt.darkGray))
            font = painter.font()
            font.setPointSize(10)
            font.setItalic(True)
            painter.setFont(font)

            placeholder_text = "Drop Image\nor Double Click to Set"
            painter.drawText(self.rect, Qt.AlignCenter, placeholder_text)

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
            

