from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QPointF, QSize, Signal, QObject
from PySide6.QtGui import (QColor, QFont, QPen, QBrush, QTextDocument, QTextOption, QPainter, QPixmap, QPalette,
            QAbstractTextDocumentLayout)
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QGraphicsSceneDragDropEvent
from typing import Optional, Dict, Any, Union
from prototypyside.views.graphics_items import ResizeHandle
from prototypyside.utils.qt_helpers import qrectf_to_list, list_to_qrectf, qfont_from_string
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.ustr_helpers import geometry_with_px_rect, geometry_with_px_pos
from prototypyside.config import HandleType, ALIGNMENT_MAP
from prototypyside.utils.proto_helpers import get_prefix, resolve_pid

class ComponentElement(QGraphicsObject):
    _serializable_fields = {
        # dict_key      : (from_fn,                 to_fn,                   default)
        "tpid": (lambda v: v,              lambda v: v,            None),
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
    property_changed = Signal(str, str, str, object)   # (parent_pid, element_pid, property_name, value)
    structure_changed = Signal(str)               # (element_pid)

    def __init__(self, pid, geometry: UnitStrGeometry, tpid = None, 
            parent: Optional[QGraphicsObject] = None, name: str = None):
        super().__init__(parent)
        self._pid = pid
        self._tpid = tpid
        self._geometry = geometry
        self._dpi = 300
        self._unit = "px"
        self._name = name
        # Set the QGraphicsItem position (scene expects px)
        self.setPos(self._geometry.px.pos)
        self._color = QColor(Qt.black)
        self._bg_color = QColor(255,255,255,0)
        self._border_color = QColor(Qt.black)
        self._border_width = UnitStr("0.0 pt", dpi=self._dpi)
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
        return self._geometry.to("px", dpi=self.dpi).rect

    # This method is for when ONLY the rectangle (size) changes,
    # not the position.
    def setRect(self, new_rect: QRectF):
        if self._geometry.to("px", dpi=self.dpi).rect == new_rect:
            return
        self.prepareGeometryChange()
        self.geometry = geometry_with_px_rect(self._geometry, new_rect)

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
    def tpid(self):
        return self._tpid

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

    def paint(self, painter: QPainter, option, widget=None):
        """
        Draws the background, border, and handles of the element using the specified unit and DPI.

        Parameters:
            painter (QPainter): The painter used to draw the element.
            option: QStyleOptionGraphicsItem passed by the scene.
            widget: Optional widget; unused.
        """
        rect = self.geometry.to("px", dpi=self.dpi).rect

        # --- Background Fill ---
        bg = self._bg_color if isinstance(self._bg_color, QColor) else QColor(self._bg_color)

        painter.setBrush(QBrush(bg))
        painter.setPen(Qt.NoPen)
        painter.drawRect(rect)

        # --- Border ---
        try:
            bw = float(self._border_width.to("px", dpi=self.dpi))
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
    def from_dict(cls, data: Dict[str, Any], registry, is_clone: bool = False) -> "ElementBase":
        # 1) Reconstruct geometry
        geom = UnitStrGeometry.from_dict(data["geometry"])

        # 2) Handle PID and cloning
        pid = resolve_pid(get_prefix(data.get("pid"))) if is_clone else data.get("pid")

        # 3) Template determines which subclass is `cls`
        inst = cls(
            pid=pid,
            geometry=geom,
            tpid=None,
            name=data.get("name")
        )
        inst._tpid = data.get("tpid", None)
        # 4) Restore all other serializable fields
        for key, (from_fn, _, default) in cls._serializable_fields.items():
            raw = data.get(key, default)
            if raw is None:
                continue
            setattr(inst, f"_{key}", from_fn(raw))
        # 5) Register and return
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


