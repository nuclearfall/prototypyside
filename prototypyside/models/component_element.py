from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QPointF, QSize, Signal, QObject
from PySide6.QtGui import (QColor, QFont, QPen, QBrush, QTextDocument, QTextOption, QPainter, QPixmap, QPalette,
            QAbstractTextDocumentLayout, QTransform)
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QGraphicsSceneDragDropEvent, QStyleOptionGraphicsItem
from typing import Optional, Dict, Any, Union
from prototypyside.views.graphics_items import ResizeHandle
from prototypyside.utils.qt_helpers import qrectf_to_list, list_to_qrectf
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.units.unit_str_helpers import geometry_with_px_rect, geometry_with_px_pos
from prototypyside.config import HandleType, ALIGNMENT_MAP
from prototypyside.utils.proto_helpers import get_prefix, resolve_pid
from prototypyside.utils.graphics_item_helpers import rotate_item
from prototypyside.config import HandleType

class ComponentElement(QGraphicsObject):
    _serializable_fields = {
        # dict_key      : (from_fn,                 to_fn,                   default)
        "tpid": (lambda v: v,              lambda v: v,            None),
        #"name":         (lambda v: v,              lambda v: v,            lambda v: v),
        "z_order":      (int,                      lambda z: z,            0),
        "color":        (QColor.fromRgba,          lambda c: c.rgba(),     None),
        "bg_color":     (QColor.fromRgba,          lambda c: c.rgba(),     None),
        "border_color": (QColor.fromRgba,          lambda c: c.rgba(),     None),
        "border_width": (UnitStr.from_dict,        lambda u: u.to_dict(),     UnitStr("1pt")),
        "alignment":    (str,                      lambda a: a,            "Center"),
        "content":      (lambda v: v,              lambda v: v,            ""),
    }
    item_changed = Signal()
    nameChanged = Signal(str)  # Add this signal
    property_changed = Signal(str, str, str, object)   # (parent_pid, element_pid, property_name, value)
    structure_changed = Signal(str)               # (element_pid)
    resize_finished = Signal(object, object, object) # item, new_geometry, old_geometry

    def __init__(self, pid, registry, geometry: UnitStrGeometry, tpid = None, 
            parent: Optional[QGraphicsObject] = None, name: str = None):
        super().__init__(parent)
        self._pid = pid
        self._tpid = tpid
        self.registry = registry
        self.ldpi = registry.ldpi
        self._geometry = geometry
        self._dpi = 300
        self._unit = "px"
        self._name = name
        self.setPos(self._geometry.px.pos)
        self._color = QColor(Qt.black)
        self._bg_color = QColor(255,255,255,0)
        self._border_color = QColor(Qt.black)
        self._border_width = UnitStr("0.0 pt", dpi=self._dpi)
        self._alignment = "Top Left"
        self._content: Optional[str] = ""
        self._rotation = 0
        self._pre_resize_state = {} # Add this to your __init_
        self.display_only = True

        self.setFlags(
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self._handles: Dict[HandleType, ResizeHandle] = {}
        for handle in self._handles:
            handle.setParentItem(self)
        self.create_handles()

    # --- Property Getters and Setters --- #
    @property
    def rotation(self):
        return self._rotation

    @rotation.setter
    def rotation(self, value: int):
        if value != self._rotation:
            self._rotation = value
            rotate_item(self, value)
            self.item_changed.emit()
            self.update()

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
            self.update()

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
        if self._geometry == new_geom:
            return

        self.prepareGeometryChange()
        self._geometry = new_geom
        super().setPos(self._geometry.px.pos)
        self.update_handles()
        self.item_changed.emit() # You may want to emit this signal
        self.update()

    def boundingRect(self) -> QRectF:
        return self._geometry.to("px", dpi=self.dpi).rect

    # This method is for when ONLY the rectangle (size) changes,
    # not the position.
    def setRect(self, new_rect: QRectF):
        if self._geometry.to("px", dpi=self.dpi).rect == new_rect:
            return
        self.prepareGeometryChange()
        self.geometry = geometry_with_px_rect(self._geometry, new_rect, dpi=self.dpi)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        # This is called when the scene moves the item.
        if change == QGraphicsItem.ItemPositionChange and value != self.pos():
            # Block signals to prevent a recursive loop if a connected item
            # also tries to set the position.
            signals_blocked = self.signalsBlocked()
            self.blockSignals(True)
            geometry_with_px_pos(self._geometry, value, dpi=self.dpi)
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
            self.nameChanged.emit(value)
            self.item_changed.emit()
            self.update()
    
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
    def border_width(self, value: "UnitStr"):
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
        bw = float(self._border_width.to("px", dpi=self.dpi))
        if self.display_only:
            pen = QPen(QColor(0, 80, 200, 100))  # RGBA: darker blue, 90% opacity
            pen.setWidthF(1.0)
            pen.setCosmetic(True)  # always 1px on screen
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect.adjusted(0.5, 0.5, -0.5, -0.5))
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
        print(f"rotation on serializing is {self.rotation}")
        data = {
            "pid":      self._pid,
            "geometry": self._geometry.to_dict(),
            "name": self._name
        }

        for key, (_, to_fn, default) in self._serializable_fields.items():
            val = getattr(self, f"_{key}", default)
            data[key] = to_fn(val) if (val is not None) else None
        data["rotation"] = self._rotation
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
            registry=registry,
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
        inst.rotation = data.get("rotation", 0)
        print(f"rotation rehydrated as {inst.rotation}")
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

    def store_pre_resize_state(self):
        rect = self.boundingRect()
        scene_tx = self.sceneTransform()
        inv_tx = scene_tx
        anchors = self._edge_centers()

        self._pre_resize_state = {
            "geometry": self.geometry,  # Store entire geometry
            "anchors": {
                HandleType.TOP_LEFT: anchors["TOP_LEFT"],
                HandleType.TOP_RIGHT: anchors["TOP_RIGHT"],
                HandleType.BOTTOM_LEFT: anchors["BOTTOM_LEFT"],
                HandleType.BOTTOM_RIGHT: anchors["BOTTOM_RIGHT"],
                HandleType.TOP_CENTER: anchors["TOP_CENTER"],
                HandleType.BOTTOM_CENTER: anchors["BOTTOM_CENTER"],
                HandleType.LEFT_CENTER: anchors["LEFT_CENTER"],
                HandleType.RIGHT_CENTER: anchors["RIGHT_CENTER"],
            },
            # MOVE TRANSFORMS TO TOP LEVEL
            "transform": scene_tx,
            "inv_transform": inv_tx,
        }

    def finalize_resize(self):
        if not self._pre_resize_state:
            return

        # Get stored geometry instead of rect
        old_geometry = self._pre_resize_state.get('geometry')
        new_geometry = self.geometry

        if old_geometry != new_geometry:
            self.resize_finished.emit(self, new_geometry, old_geometry)
        self._pre_resize_state.clear()

    def _edge_centers(self, to_scene=True):
        # Always a QRectF in *local* coords
        rect: QRectF = self.boundingRect()

        cx = rect.center().x()
        cy = rect.center().y()

        # Local points
        pts = {
            "TOP_LEFT":      rect.topLeft(),
            "TOP_RIGHT":     rect.topRight(),
            "BOTTOM_LEFT":   rect.bottomLeft(),
            "BOTTOM_RIGHT":  rect.bottomRight(),
            "TOP_CENTER":    QPointF(cx, rect.top()),
            "BOTTOM_CENTER": QPointF(cx, rect.bottom()),
            "LEFT_CENTER":   QPointF(rect.left(),  cy),
            "RIGHT_CENTER":  QPointF(rect.right(), cy),
            "CENTER":        rect.center(),
        }

        if not to_scene:
            return pts
        # Map to scene (per‑point to avoid polygon conversion)
        return {k: self.mapToScene(v) for k, v in pts.items()}

    def _axes_for_handle(self, handle_type):
        # returns (sx, sy, affect_w, affect_h)
        # sx/sy ∈ {-1, 0, +1} denote which side is being dragged in LOCAL axes.
        # affect_w/affect_h tell us whether width/height should actually change.

        if handle_type == HandleType.TOP_LEFT:
            return (-1, -1, True,  True)
        if handle_type == HandleType.TOP_CENTER:
            return ( 0, -1, False, True)
        if handle_type == HandleType.TOP_RIGHT:
            return (+1, -1, True,  True)
        if handle_type == HandleType.RIGHT_CENTER:
            return (+1,  0, True,  False)
        if handle_type == HandleType.BOTTOM_RIGHT:
            return (+1, +1, True,  True)
        if handle_type == HandleType.BOTTOM_CENTER:
            return ( 0, +1, False, True)
        if handle_type == HandleType.BOTTOM_LEFT:
            return (-1, +1, True,  True)
        if handle_type == HandleType.LEFT_CENTER:
            return (-1,  0, True,  False)
        return (0, 0, False, False)

    def resize_from_handle(self, handle_type, handle_scene_pos):
        sc = self.scene()

        st = getattr(self, "_pre_resize_state", None)
        if not st:
            return

        if sc is not None and hasattr(sc, "snap_to_grid"):
            handle_scene_pos = sc.snap_to_grid(handle_scene_pos)

        self.prepareGeometryChange()
        r0        = st["rect0"]
        pos0      = st["pos0_scene"]
        handle0   = st["handle_local0"]
        sx, sy    = st["sx"], st["sy"]
        affect_w  = st["affect_w"]
        affect_h  = st["affect_h"]

        # Mouse delta in LOCAL space (from snapped scene pos)
        delta_local = self.mapFromScene(handle_scene_pos) - handle0

        # Only apply the component(s) that this handle should change
        dx = delta_local.x() if affect_w else 0.0
        dy = delta_local.y() if affect_h else 0.0

        # Grow sizes in the pulled direction(s)
        min_size = 10.0
        new_w = max(min_size, r0.width()  + sx * dx)
        new_h = max(min_size, r0.height() + sy * dy)

        # If pulling left/top, the local origin must shift to keep the opposite edge fixed
        shift_x_local = (r0.width()  - new_w) if (affect_w and sx == -1) else 0.0
        shift_y_local = (r0.height() - new_h) if (affect_h and sy == -1) else 0.0

        # Convert local shift to a SCENE vector (respects rotation/scale)
        p00 = self.mapToScene(QPointF(0, 0))
        pss = self.mapToScene(QPointF(shift_x_local, shift_y_local))
        shift_scene_vec = pss - p00

        # Apply new scene pos to keep the opposite side visually anchored
        self.setPos(pos0 + shift_scene_vec)

        # Update rect (local, origin at 0,0). Do NOT call normalized().
        final_local_rect = QRectF(0, 0, new_w, new_h)
        self._geometry = UnitStrGeometry.from_px(rect=final_local_rect, pos=self.pos(), dpi=self.dpi)

        self.update_handles()
        self.item_changed.emit()

    def begin_handle_resize(self, handle_item, event):
        r0 = self._geometry.to("px", self.dpi).rect  # local rect, origin at (0,0)
        sx, sy, affect_w, affect_h = self._axes_for_handle(self._active_handle)
        sc = self.scene()
        
        press_scene_pos = sc.snap_to_grid(event.scenePos()) if sc is not None and hasattr(sc, "snap_to_grid") else event.scenePos()

        self._pre_resize_state = {
            "rect0": r0,
            "pos0_scene": self.pos(),
            "handle_local0": self.mapFromScene(press_scene_pos),   # ⬅ mapped from snapped scene pos
            "sx": sx,
            "sy": sy,
            "affect_w": affect_w,
            "affect_h": affect_h,
        }

    def end_handle_resize(self):
        # good place to clear the snapshot, emit a finished signal,
        # or push an undo command using rect before/after if you track it
        self._pre_resize_state = None

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

