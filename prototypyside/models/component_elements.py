from PySide6.QtCore import Qt, QRectF, QPointF, QSize, Signal, QObject
from PySide6.QtGui import (QColor, QFont, QPen, QBrush, QTextDocument, QPainter, QPixmap,
            QAbstractTextDocumentLayout)
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QGraphicsSceneDragDropEvent
from typing import Optional, Dict, Any
from prototypyside.views.graphics_items import ResizeHandle
from prototypyside.utils.qt_helpers import qrectf_to_list, list_to_qrectf
from prototypyside.utils.unit_str import UnitStr
from prototypyside.utils.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.ustr_helpers import with_rect, with_pos
from prototypyside.utils.style_serialization_helpers import save_style, load_style
from prototypyside.config import HandleType


class ComponentElement(QGraphicsObject):
    element_changed = Signal()

    def __init__(self, pid, geometry: UnitStrGeometry, template_pid = None, 
            parent: Optional[QGraphicsObject] = None, name: str = None):
        super().__init__(parent)
        self._pid = pid
        self._template_pid = template_pid
        self._geometry = geometry
        self._dpi = geometry.dpi
        self._name = name

        # Set the QGraphicsItem position (scene expects px)
        self.setPos(self._geometry.px.pos)
        self._color = QColor(Qt.black)
        self._bg_color = QColor(255,255,255,0)
        self._border_color = QColor(Qt.black)
        self._border_width = UnitStr("0.5 pt", dpi=self._dpi)
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

    # This property and three methods must be defined for each object.
    # These three methods must be defined for each object.
    @property
    def dpi(self):
        return self._dpi

    @property
    def geometry(self):
        return self._geometry

    @geometry.setter
    def geometry(self, new_geom: UnitStrGeometry):
        print(f"[SETTER] geometry called with {new_geom}")
        if self._geometry == new_geom:
            print("[SETTER] geometry unchanged")
            return

        self.prepareGeometryChange()
        print(f"[SETTER] prepareGeometryChange called")
        print(f"[SETTER] pos set to {self._geometry.px.pos}")
        self._geometry = new_geom
        super().setPos(self._geometry.px.pos)
        # self.element_changed.emit()
        self.update()

    def boundingRect(self) -> QRectF:
        return self._geometry.px.rect

    # This method is for when ONLY the rectangle (size) changes,
    # not the position.
    def setRect(self, new_rect: QRectF):
        if self._geometry.px.rect == new_rect:
            return
        self.prepareGeometryChange()
        with_rect(self._geometry, new_rect)
        # self.element_changed.emit()
        # self.update()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        # This is called when the scene moves the item.
        if change == QGraphicsItem.ItemPositionChange and value != self.pos():
            # Block signals to prevent a recursive loop if a connected slot
            # also tries to set the position.
            signals_blocked = self.signalsBlocked()
            self.blockSignals(True)
            with_pos(self._geometry, value)
            print(f"[ITEMCHANGE] Called with change={change}, value={value}")
            print(f"[ITEMCHANGE] Geometry.pos updated to: {self._geometry.px.pos}")
            self.blockSignals(signals_blocked)

        # It's crucial to call the base class implementation. This will update geometry.
        # If other signals are emitted or updates called for, it breaks the undo stack.
        return super().itemChange(change, value)

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
    def template_pid(self):
        return self._template_pid

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
        self._border_width = value
        self.element_changed.emit()
        self.update()
        
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

    def resize_from_handle(self, handle_type: HandleType, delta: QPointF, start_scene_rect: QRectF):
        """Resize by handle: supports all 8 directions with proper boundary constraints."""
        self.prepareGeometryChange()
        dpi = self._dpi
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
        if new_scene_rect.left() < scene_rect.left():
            new_scene_rect.setLeft(scene_rect.left())
        if new_scene_rect.top() < scene_rect.top():
            new_scene_rect.setTop(scene_rect.top())
        if new_scene_rect.right() > scene_rect.right():
            new_scene_rect.setRight(scene_rect.right())
        if new_scene_rect.bottom() > scene_rect.bottom():
            new_scene_rect.setBottom(scene_rect.bottom())
        
        new_rect = self.mapRectFromScene(new_scene_rect)

        # 5. Snap to grid if enabled
        if hasattr(scene, "is_snap_to_grid") and scene.is_snap_to_grid:
            snapped_tl = scene.snap_to_grid(self.mapToScene(new_rect.topLeft()))
            snapped_br = scene.snap_to_grid(self.mapToScene(new_rect.bottomRight()))
            new_rect = self.mapRectFromScene(QRectF(snapped_tl, snapped_br))

        # 6. Update position and geometry
        new_scene_pos = self.mapToScene(new_rect.topLeft())
        
        # The dimensions of new_rect are correct, but its position is relative
        # to the old item position. We need a rect with the same dimensions but
        # at origin (0,0) for the new local coordinate system.
        new_local_bounds = QRectF(0, 0, new_rect.width(), new_rect.height())

        # Set the item's position to the new top-left corner in the scene
        self.setPos(new_scene_pos)

        # Create the new geometry object using the correct local bounds and new scene position
        self._geometry = UnitStrGeometry.from_px(
            rect=new_local_bounds,
            pos=new_scene_pos,
            dpi=self._dpi
        )

        # 7. Final updates
        self.update_handles()
        self.element_changed.emit()
        self.update()

    def update_from_merge_data(merge_data):
        self.content = merge_data
        self.elment_changed.emit()
        self.update()


    def paint(self, painter: QPainter, option, widget=None):
        rect = self.boundingRect()

        # Background
        bg = self._bg_color if isinstance(self._bg_color, QColor) else QColor(self._bg_color)
        painter.setBrush(QBrush(bg))
        painter.setPen(Qt.NoPen)
        painter.drawRect(rect)

        # Border
        try:
            bw = float(self._border_width.px)
        except Exception:
            bw = 1.0
        if bw > 0:
            border_col = self._border_color if isinstance(self._border_color, QColor) else QColor(self._border_color)
            pen = QPen(border_col)
            pen.setWidthF(bw)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)

        # Handles
        if self.handles_visible:
            self.draw_handles()

    def to_dict(self):
        """Serialize the element to a dictionary with logical units."""
        return {
            "pid": self._pid,
            "template_pid": self._template_pid,
            "name": self._name,
            "geometry": self._geometry.dict(),
            "color": self._color.rgba() if self._color else None,  # Modified for alpha
            "bg_color": self._bg_color.rgba() if self._bg_color else None, # Modified for alpha
            "border_color": self._border_color.rgba() if self._border_color else None, # Modified for alpha
            "border_width": self._border_width.dict(),
            "alignment": int(self._alignment) if self._alignment is not None else None,
            "content": self._content if self._content is not None else "",
        }

    @classmethod
    def from_dict(cls, data):
        pid = data.get("pid")
        geometry = UnitStrGeometry.from_dict(data.get("geometry"))
        template_pid = data.get("template_pid")
        name = data.get("name", None)
        obj = cls(
            pid=pid,
            geometry=geometry,
            template_pid=template_pid,
            parent=None,
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
            obj._border_width = UnitStr.from_dict(data.get("border_width"))
        if "alignment" in data and data["alignment"] is not None:
            obj._alignment = int(data["alignment"])
        if "content" in data and data["content"] is not None:
            obj._content = data["content"]
        # Handle subclass-specific fields (see below)
        return obj

    def clone(self):
        data = self.to_dict()
        prefix = get_prefix(data.get("pid"))
        data["pid"] = issue_pid(prefix)
        data["name"] = f"{data.get('name', 'element')}_copy"
        return type(self).from_dict(data)
        
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
        w = self._geometry.px.size.width()
        h = self._geometry.px.size.height()
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


class TextElement(ComponentElement):
    def __init__(self, pid, geometry: UnitStrGeometry, template_pid = None, 
            parent: Optional[QGraphicsObject] = None, name: str = None):
        super().__init__(pid, geometry, template_pid, parent, name)

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
            self.prepareGeometryChange() # Font change might change layout/size
            self._font = value
            self._text_document.setDefaultFont(self._font) # Update document's font
            self.update_text_document_layout() # Recalculate layout based on new font
            self.element_changed.emit()
            self.update()

    # --- End Text-specific Property Getters and Setters ---

    def paint(self, painter: QPainter, option, widget=None):
        # Call base class paint to handle borders and basic styling first
        super().paint(painter, option, widget)
        rect = self.boundingRect()
        painter.save()

        # Set up QTextDocument for automatic word wrapping within rect
        doc = QTextDocument()
        doc.setDefaultFont(self.font)
        doc.setPlainText(self.content)
        doc.setTextWidth(rect.width())

        # Ensure content doesn't exceed rect height
        layout = doc.documentLayout()
        required_height = layout.documentSize().height()
        if required_height > rect.height():
            # Clip content to fit rect height if necessary
            painter.setClipRect(rect)

        # Position the text correctly within the rect
        painter.translate(rect.topLeft())
        doc.drawContents(painter, QRectF(0, 0, rect.width(), rect.height()))

        painter.restore()


    def to_dict(self):
        data = super().to_dict()
        data['font'] = self.font.toString()  # Serialize QFont to string
        return data

    @classmethod
    def from_dict(cls, data):
        element = super().from_dict(data)
        font_string = data.get("font", "Arial,12")
        font = QFont()
        font.fromString(font_string)
        element.font = font
        return element

class ImageElement(ComponentElement):
    def __init__(self, pid, geometry: UnitStrGeometry, template_pid = None, 
            parent: Optional[QGraphicsObject] = None, name: str = None):
        super().__init__(pid, geometry, template_pid, parent, name)

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
    def from_dict(cls, data):
        element = super().from_dict(data)
        element.keep_aspect = data.get("keep_aspect", True)
        return element

    def paint(self, painter: QPainter, option, widget=None):
        super().paint(painter, option, widget)
        rect = self.boundingRect()
        size = self.geometry.px.size
        size = QSize(size.width(), size.height())
        if self._pixmap:
            if self._keep_aspect:
                scaled = self._pixmap.scaled(
                    size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                x = rect.x() + (rect.width() - scaled.width()) / 2
                y = rect.y() + (rect.height() - scaled.height()) / 2
                painter.drawPixmap(QPointF(x, y), scaled)
            else:
                painter.drawPixmap(
                    rect.topLeft(),
                    self._pixmap.scaled(size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                )
        else:
            painter.setPen(QPen(Qt.gray, 1, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)
            painter.setPen(QPen(Qt.darkGray))
            font = painter.font()
            font.setPointSize(10)
            font.setItalic(True)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignCenter, "Drop Image\nor Double Click to Set")

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
            

