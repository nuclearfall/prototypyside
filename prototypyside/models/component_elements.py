from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QPointF, QSize, Signal, QObject
from PySide6.QtGui import (QColor, QFont, QPen, QBrush, QTextDocument, QTextOption, QPainter, QPixmap, QPalette,
            QAbstractTextDocumentLayout)
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QGraphicsSceneDragDropEvent
from typing import Optional, Dict, Any, Union
from prototypyside.views.graphics_items import ResizeHandle
from prototypyside.utils.qt_helpers import qrectf_to_list, list_to_qrectf, qfont_from_string
from prototypyside.utils.unit_str import UnitStr
from prototypyside.utils.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.ustr_helpers import geometry_with_px_rect, geometry_with_px_pos
from prototypyside.utils.style_serialization_helpers import save_style, load_style
from prototypyside.config import HandleType, ALIGNMENT_MAP
from prototypyside.utils.proto_helpers import get_prefix, issue_pid

class ComponentElement(QGraphicsObject):
    _serializable_fields = {
        # dict_key      : (from_fn,                 to_fn,                   default)
        "template_pid": (lambda v: v,              lambda v: v,            None),
        "name":         (lambda v: v,              lambda v: v,            ""),
        "z_order":      (int,                      lambda z: z,            0),
        "color":        (QColor.fromRgba,          lambda c: c.rgba(),     None),
        "bg_color":     (QColor.fromRgba,          lambda c: c.rgba(),     None),
        "border_color": (QColor.fromRgba,          lambda c: c.rgba(),     None),
        "border_width": (UnitStr.from_dict,        lambda u: u.to_dict(),     UnitStr("1pt")),
        "alignment":    (str,                      lambda a: a,            "Center"),
        "content":      (lambda v: v,              lambda v: v,            ""),
    }
    item_changed = Signal()

    def __init__(self, pid, geometry: UnitStrGeometry, template_pid = None, 
            parent: Optional[QGraphicsObject] = None, name: str = None):
        super().__init__(parent)
        self._pid = pid
        self._template_pid = template_pid
        self._geometry = geometry
        self._dpi = geometry.dpi
        self._unit = "px"
        self._name = name
        # Set the QGraphicsItem position (scene expects px)
        self.setPos(self._geometry.px.pos)
        self._color = QColor(Qt.black)
        self._bg_color = QColor(255,255,255,0)
        self._border_color = QColor(Qt.black)
        self._border_width = UnitStr("0.5 pt", dpi=self._dpi)
        self._alignment = "Top Left"
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
    def alignment_flags(self):
        return ALIGNMENT_MAP.get(self.alignment, Qt.AlignCenter)
    @property
    def dpi(self) -> int:
        return self._dpi

    @dpi.setter
    def dpi(self, new: int):
        if self._dpi != new:
            self._dpi = new

    @property
    def unit(self) -> str:
        return self._unit

    @unit.setter
    def unit(self, new: str):
        if self._unit != new:
            self._unit = new

    @property
    def geometry(self):
        return self._geometry

    @geometry.setter
    def geometry(self, new_geom: UnitStrGeometry):
        # print(f"[SETTER] geometry called with {new_geom}")
        if self._geometry == new_geom:
            # print("[SETTER] geometry unchanged")
            return

        self.prepareGeometryChange()
        # print(f"[SETTER] prepareGeometryChange called")
        # print(f"[SETTER] pos set to {self._geometry.px.pos}")
        self._geometry = new_geom
        super().setPos(self._geometry.to(self.unit, dpi=self.dpi).pos)
        # self.item_changed.emit()
        self.update()

    def boundingRect(self) -> QRectF:
        return self._geometry.to(self.unit, dpi=self.dpi).rect

    # This method is for when ONLY the rectangle (size) changes,
    # not the position.
    def setRect(self, new_rect: QRectF):
        if self._geometry.to(self.unit, dpi=self.dpi).rect == new_rect:
            return
        self.prepareGeometryChange()
        geometry_with_px_rect(self._geometry, new_rect)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        # This is called when the scene moves the item.
        if change == QGraphicsItem.ItemPositionChange and value != self.pos():
            # Block signals to prevent a recursive loop if a connected item
            # also tries to set the position.
            signals_blocked = self.signalsBlocked()
            self.blockSignals(True)
            geometry_with_px_pos(self._geometry, value)
            # print(f"[ITEMCHANGE] Called with change={change}, value={value}")
            # print(f"[ITEMCHANGE] Geometry.pos updated to: {self._geometry.px.pos}")
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
            self.item_changed.emit()
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
            self.item_changed.emit()
    
    @property
    def color(self) -> QColor:
        return self._color

    @color.setter
    def color(self, value: QColor):
        if self._color != value:
            self._color = value
            self.item_changed.emit()
            self.update()

    @property
    def bg_color(self) -> QColor:
        return self._bg_color

    @bg_color.setter
    def bg_color(self, value: QColor):
        if self._bg_color != value:
            self._bg_color = value
            self.item_changed.emit()
            self.update()

    @property
    def border_color(self) -> QColor:
        return self._border_color

    @border_color.setter
    def border_color(self, value: QColor):
        if self._border_color != value:
            self._border_color = value
            self.item_changed.emit()
            self.update()

    @property
    def border_width(self) -> "UnitStr":
        return self._border_width

    @border_width.setter
    def border_width(self, value):
        # Accept a UnitStr, string, or number (as current unit)
        self._border_width = value
        self.item_changed.emit()
        self.update()
        
        if getattr(self, "_border_width", None) != value:
            self._border_width = value
            self.item_changed.emit()
            self.update()

    @property
    def alignment(self) -> Qt.AlignmentFlag:
        return self._alignment

    @alignment.setter
    def alignment(self, value: str):
        if self._alignment != value:
            self._alignment = value
            self.item_changed.emit()
            self.update()

    @property
    def content(self) -> Optional[str]:
        return self._content

    @content.setter
    def content(self, content: str):
        self._content = content
        self.item_changed.emit()
        self.update()

    @property
    def unit(self):
        return self._unit

    def resize_from_handle(self, handle_type: HandleType, delta: QPointF, start_scene_rect: QRectF):
        """Resize by handle: supports all 8 directions with proper boundary constraints."""
        self.prepareGeometryChange()
        dpi = self.dpi
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
            dpi=self.dpi
        )

        # 7. Final updates
        self.update_handles()
        self.item_changed.emit()
        self.update()

    def update_from_merge_data(merge_data):
        self.content = merge_data
        self.elment_changed.emit()
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        """
        Draws the background, border, and handles of the element using the specified unit and DPI.

        Parameters:
            painter (QPainter): The painter used to draw the element.
            option: QStyleOptionGraphicsItem passed by the scene.
            widget: Optional widget; unused.
        """
        rect = self.geometry.to(self.unit, dpi=self.dpi).rect

        # --- Background Fill ---
        bg = self._bg_color if isinstance(self._bg_color, QColor) else QColor(self._bg_color)

        painter.setBrush(QBrush(bg))
        painter.setPen(Qt.NoPen)
        painter.drawRect(rect)

        # --- Border ---
        try:
            bw = float(self._border_width.to(self.unit, dpi=self.dpi))
        except Exception:
            bw = 1.0

        if bw > 0:
            border_col = self._border_color if isinstance(self._border_color, QColor) else QColor(self._border_color)
            pen = QPen(border_col)
            pen.setWidthF(bw)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)

        # --- Resize Handles (only shown if visible) ---
        if self.handles_visible:
            self.draw_handles()


    def to_dict(self) -> Dict[str, Any]:
        data = {
            "pid":      self._pid,
            "geometry": self._geometry.to_dict(),
        }
        for key, (_, to_fn, default) in self._serializable_fields.items():
            val = getattr(self, f"_{key}", default)
            data[key] = to_fn(val) if (val is not None) else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any], registry, is_clone=False) -> "ElementBase":
        geom = UnitStrGeometry.from_dict(data["geometry"])
        pid = data.get("pid")
        prefix = get_prefix(pid)
        if is_clone:
            pid = issue_pid(prefix)
        obj = ImageElement if prefix == 'ie' else TextElement
        inst = obj(pid=pid,
                   geometry=geom,
                   template_pid=None,  # will be set below if present
                   name=None)          # ditto
        # now restore everything via our metadata
        for key, (from_fn, _, default) in cls._serializable_fields.items():
            raw = data.get(key, default)
            if raw is None:
                continue
            setattr(inst, f"_{key}", from_fn(raw))
        registry.register(inst)
        return inst
        
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
    _subclass_serializable = {
        # maps attribute name -> (dict_key, from_fn, to_fn, default)
        "font": (
            "font",
            qfont_from_string,
            lambda f: f.toString(),
            QFont("Arial", 12)
        )
    }

    def __init__(self, pid, geometry: UnitStrGeometry, template_pid = None, 
            parent: Optional[QGraphicsObject] = None, name: str = None):
        super().__init__(pid, geometry, template_pid, parent, name)

        self._font = QFont("Arial", 12)
        self._content = "Sample Text"

    # --- Text-specific Property Getters and Setters ---
    @property
    def font(self) -> QFont:
        return self._font

    @font.setter
    def font(self, value: QFont):
        if self._font != value:
            self.prepareGeometryChange() # Font change might change layout/size
            self._font = value
            self.item_changed.emit()
            self.update()

    # --- End Text-specific Property Getters and Setters ---

    def to_dict(self):
        data = super().to_dict()  # ← include base fields
        for attr, (key, _, to_fn, default) in self._subclass_serializable.items():
            val = getattr(self, f"_{attr}", default)
            data[key] = to_fn(val)
        return data

    @classmethod
    def from_dict(cls, data: dict, registry, is_clone=False):
        inst = super().from_dict(data, registry, is_clone)
        for attr, (key, from_fn, _, default) in cls._subclass_serializable.items():
            raw = data.get(key, default)
            # We want to set content using the content setter.
            if hasattr(inst, f"{attr}"):
                setattr(inst, f"{attr}", from_fn(raw))
            else:
                setattr(inst, f"_{attr}", from_fn(raw))
        return inst

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)

        rect = self.geometry.to(self.unit, dpi=self.dpi).rect
        painter.save()

        # 1) build the document
        doc = QTextDocument()
        doc.setDefaultFont(self.font)

        # force text color
        ctx = QAbstractTextDocumentLayout.PaintContext()
        ctx.palette.setColor(QPalette.Text, self.color)

        doc.setDocumentMargin(0)
        doc.setDefaultTextOption(QTextOption(self.alignment_flags))
        doc.setPlainText(self.content or "")
        doc.setTextWidth(rect.width())

        # 2) clip if needed
        if doc.size().height() > rect.height():
            painter.setClipRect(rect)

        # 3) translate into position and draw
        painter.translate(rect.topLeft())
        doc.documentLayout().draw(painter, ctx)

        painter.restore()
    # # draw background & border
    # super().paint(painter, option, widget, unit=self.unit, dpi=self.dpi)

    # rect = self.geometry.to(self.unit, dpi=self.dpi).rect
    # painter.save()
    # painter.setPen(self.color)                     # use your element’s color
    # painter.setBrush(Qt.NoBrush)
    # # wrap text to the rectangle
    # painter.drawText(
    #     rect,
    #     self.alignment_flags | Qt.TextWordWrap,
    #     self.content or ""
    # )
    # painter.restore()
        """
        Draws the styled background + text using QTextDocument inside the specified rect.

        Parameters:
            unit (str): Unit like 'in', 'mm', or 'px' used to compute drawing size.
            dpi (int): Resolution in dots-per-inch for physical scaling.
        """
        # # Base element painting: bg and border
        # super().paint(painter, option, widget)

        # rect = self.geometry.to(self.unit, dpi=self.dpi).rect
        # painter.save()

        # doc = QTextDocument()
        # doc.setDefaultFont(self.font)
        # doc.setPlainText(self.content or "")
        # doc.setTextWidth(rect.width())

        # layout = doc.documentLayout()
        # required_height = layout.documentSize().height()
        # if required_height > rect.height():
        #     painter.setClipRect(rect)

        # painter.translate(rect.topLeft())
        # doc.drawContents(painter, QRectF(0, 0, rect.width(), rect.height()))
        # painter.restore()

class ImageElement(ComponentElement):
    _subclass_serializable = {
        "keep_aspect": ("keep_aspect",
                        lambda x: bool(x),
                        lambda b: b,
                        True),
    }

    def __init__(self, pid, geometry: UnitStrGeometry, template_pid = None, 
            parent: Optional[QGraphicsObject] = None, name: str = None):
        super().__init__(pid, geometry, template_pid, parent, name)

        self._pixmap: Optional[QPixmap] = None
        # _content is handled by ComponentElement
        self._alignment = "Center"
        # Image-specific properties
        self._keep_aspect = True
        self.showPlaceholderText = True

        self.setAcceptDrops(True)

    # override the content getter/setter
    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, new_content: Optional[str]):
        # always clear pixmap if new_content is None or invalid
        if not new_content or not Path(new_content).exists():
            self._pixmap = None
            self._content = None
        else:
            pm = QPixmap(new_content)
            self._pixmap = pm if not pm.isNull() else None
            self._content = new_content
        self.item_changed.emit()
        self.update()



    # --- Image-specific Property Getters and Setters ---
    @property
    def keep_aspect(self) -> bool:
        return self._keep_aspect

    @keep_aspect.setter
    def keep_aspect(self, value: bool):
        if self._keep_aspect != value:
            self._keep_aspect = value
            self.item_changed.emit()
            self.update()

    # --- End Image-specific Property Getters and Setters ---

    def paint(self, painter: QPainter, option, widget=None):
        """
        Paints an image inside the bounding rect, respecting aspect ratio and logical units.
        Always draws the border *after* the content so it sits on top.
        """
        # 1) figure out our rect & size
        rect = self.geometry.to(self.unit, dpi=self.dpi).rect
        size = self.geometry.to(self.unit, dpi=self.dpi).size
        w = size.width()
        h = size.height()
        # 2) draw the image *first*
        if self._pixmap:
            if self._keep_aspect:
                scaled = self._pixmap.scaled(
                    w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                x = rect.x() + (rect.width() - scaled.width()) / 2
                y = rect.y() + (rect.height() - scaled.height()) / 2
                painter.drawPixmap(QPointF(x, y), scaled)
            else:
                painter.drawPixmap(
                    rect.topLeft(),
                    self._pixmap.scaled(size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                )

        # 3) or draw placeholder text *instead* (still before the border)
        elif self.showPlaceholderText:
            painter.save()
            painter.setPen(QPen(Qt.darkGray))
            font = painter.font()
            font.setPointSize(10)
            font.setItalic(True)
            painter.setFont(font)
            painter.drawText(rect, self.alignment_flags,
                             "Drop Image\nor Double Click to Set")
            painter.restore()

        # 4) finally, draw the border on top
        super().paint(painter, option, widget)


    def to_dict(self):
        data = super().to_dict()  # ← include base fields
        for attr, (key, _, to_fn, default) in self._subclass_serializable.items():
            val = getattr(self, f"_{attr}", default)
            data[key] = to_fn(val)
        return data

    @classmethod
    def from_dict(cls, data: dict, registry, is_clone=False):
        inst = super().from_dict(data, registry, is_clone)
        for attr, (key, from_fn, _, default) in cls._subclass_serializable.items():
            raw = data.get(key, default)
            if hasattr(inst, f"{attr}"):
                setattr(inst, f"{attr}", from_fn(raw))
            else:
                setattr(inst, f"_{attr}", from_fn(raw))
        return inst

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
            

