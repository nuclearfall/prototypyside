from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QPointF, QSize, Signal, QObject
from PySide6.QtGui import (QColor, QFont, QPen, QBrush, QTextDocument, QTextOption, QPainter, QPixmap, QPalette,
            QAbstractTextDocumentLayout, QTransform)
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QGraphicsSceneDragDropEvent
from typing import Optional, Dict, Any, Union
from prototypyside.views.graphics_items import ResizeHandle
from prototypyside.utils.qt_helpers import qrectf_to_list, list_to_qrectf, qfont_from_string
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
        self._rotation = 0
        self._pre_resize_state = {} # Add this to your __init_


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

    # This property and three methods must be defined for each object.
    # These three methods must be defined for each object.
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
        # The super().setPos() call is incorrect here, as the geometry object
        # already contains the position. The item's position is managed by
        # ItemPositionChange or direct calls to setPos.
        # Let's rely on the geometry's internal pixel position.
        super().setPos(self._geometry.px.pos)
        
        # --- Add this line ---
        self.update_handles() # Explicitly update handles after geometry changes
        
        self.item_changed.emit() # You may want to emit this signal
        self.update()
    # @geometry.setter
    # def geometry(self, new_geom: UnitStrGeometry):
    #     # print(f"[SETTER] geometry called with {new_geom}")
    #     if self._geometry == new_geom:
    #         # print("[SETTER] geometry unchanged")
    #         return

    #     self.prepareGeometryChange()
    #     # print(f"[SETTER] prepareGeometryChange called")
    #     # print(f"[SETTER] pos set to {self._geometry.px.pos}")
    #     self._geometry = new_geom
    #     super().setPos(self._geometry.to(self.unit, dpi=self.dpi).pos)
    #     # self.item_changed.emit()
    #     self.update()

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
            self.nameChanged.emit(value)  # Emit signal when name changes
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
        print(f"[DEBUG] Setting content on {self.name} → {content}")
        self._content = content
        self.item_changed.emit()
        self.update()

    # # component_element.py (or wherever store_pre_resize_state lives)
    # def store_pre_resize_state(self):
    #     rect = self.boundingRect()  # or self.rect() depending on your class
    #    # full scene transform and its inverse (used in move)
    #     scene_tx = self.sceneTransform()
    #     inv_tx, ok = scene_tx.inverted()
    #     anchors = self._edge_centers()

    #     self._pre_resize_state = {
    #         "rect": rect,
    #         "pos":  self.scenePos(),
    #         "anchors": {
    #             # map your HandleType enum -> QPointF
    #             HandleType.TOP_LEFT:      anchors["TOP_LEFT"],
    #             HandleType.TOP_RIGHT:     anchors["TOP_RIGHT"],
    #             HandleType.BOTTOM_LEFT:   anchors["BOTTOM_LEFT"],
    #             HandleType.BOTTOM_RIGHT:  anchors["BOTTOM_RIGHT"],
    #             HandleType.TOP_CENTER:    anchors["TOP_CENTER"],
    #             HandleType.BOTTOM_CENTER: anchors["BOTTOM_CENTER"],
    #             HandleType.LEFT_CENTER:   anchors["LEFT_CENTER"],
    #             HandleType.RIGHT_CENTER:  anchors["RIGHT_CENTER"],
    #             # (optional) center if you need it
    #             # HandleType.CENTER:     anchors["CENTER"],
    #             # 👇 these two lines satisfy your mover’s expectation
    #             "transform": scene_tx,
    #             "inv_transform": inv_tx,
    #         }
    #     }
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
    # def finalize_resize(self):
    #         """
    #         Clears the stored state and emits a signal with the old and new
    #         geometry, allowing the scene to create an undo command.
    #         """
    #         if not self._pre_resize_state:
    #             return

    #         old_geometry = self._pre_resize_state.get('geometry')
    #         new_geometry = self.geometry

    #         if old_geometry != new_geometry:
    #             # Emit the signal that the scene will listen to.
    #             self.resize_finished.emit(self, new_geometry, old_geometry)

    #         self._pre_resize_state.clear()

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

    # def resize_from_handle(self, handle_type: HandleType, handle_scene_pos: QPointF):
        """
        Resizes the item using an anchor-point strategy to correctly handle rotation.
        """
        # if not self._pre_resize_state:
        #     return
            
        # self.prepareGeometryChange()

        # # 1. Get the stationary anchor point's original scene position
        # anchor_scene_pos = self._pre_resize_state['anchors'][handle_type]

        # # 2. Map the handle's new scene position into the item's original local coordinate space
        # original_transform = self._pre_resize_state['transform']
        #new_handle_local_pos, _ = original_transform.inverted().map(handle_scene_pos)

        # # 3. Get the original local bounding rect
        # original_local_rect = self._pre_resize_state['geometry'].to("px", self.dpi).rect

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
        st = getattr(self, "_pre_resize_state", None)
        if not st:
            return

        self.prepareGeometryChange()

        r0        = st["rect0"]
        pos0      = st["pos0_scene"]
        handle0   = st["handle_local0"]
        sx, sy    = st["sx"], st["sy"]
        affect_w  = st["affect_w"]
        affect_h  = st["affect_h"]

        # Mouse delta in LOCAL space
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

    # def resize_from_handle(self, handle_type, handle_scene_pos):
    #     st = getattr(self, "_pre_resize_state", None)
    #     if not st:
    #         return

    #     self.prepareGeometryChange()

    #     r0        = st["rect0"]
    #     pos0      = st["pos0_scene"]
    #     handle0   = st["handle_local0"]
    #     sx, sy    = st["sx"], st["sy"]

    #     # mouse delta in LOCAL space
    #     delta_local = self.mapFromScene(handle_scene_pos) - handle0

    #     min_size = 10.0
    #     new_w = max(min_size, r0.width()  + sx * delta_local.x())
    #     new_h = max(min_size, r0.height() + sy * delta_local.y())

    #     # when pulling left/top, origin shifts in local space
    #     shift_x_local = (r0.width()  - new_w) if sx == -1 else 0.0
    #     shift_y_local = (r0.height() - new_h) if sy == -1 else 0.0

    #     # convert local shift to a scene vector (respects rotation/scale)
    #     p00 = self.mapToScene(QPointF(0, 0))
    #     pss = self.mapToScene(QPointF(shift_x_local, shift_y_local))
    #     shift_scene_vec = pss - p00

    #     # keep the opposite side visually anchored
    #     self.setPos(pos0 + shift_scene_vec)

    #     # update rect (local, origin at 0,0; do NOT call normalized())
    #     final_local_rect = QRectF(0, 0, new_w, new_h)
    #     self._geometry = UnitStrGeometry.from_px(rect=final_local_rect, pos=self.pos(), dpi=self.dpi)

    #     self.update_handles()
    #     self.item_changed.emit()
    #     st = self._pre_resize_state
    #     if not st: return

    #     self.prepareGeometryChange()

    #     r0   = st["rect0"]
    #     pos0 = st["pos0_scene"]
    #     sx, sy = st["sx"], st["sy"]

    #     # mouse delta in LOCAL space
    #     delta_local = self.mapFromScene(handle_scene_pos) - st["handle_local0"]

    #     # grow width/height in the direction of the pulled side(s)
    #     min_size = 10.0
    #     new_w = max(min_size, r0.width()  + sx * delta_local.x())
    #     new_h = max(min_size, r0.height() + sy * delta_local.y())

    #     # if dragging the left/top side (sx/sy == -1), origin must shift in local space
    #     shift_x_local = (r0.width()  - new_w) if sx == -1 else 0.0
    #     shift_y_local = (r0.height() - new_h) if sy == -1 else 0.0

    #     # convert local shift to a SCENE vector (respects rotation/scale)
    #     p00 = self.mapToScene(QPointF(0, 0))
    #     pss = self.mapToScene(QPointF(shift_x_local, shift_y_local))
    #     shift_scene_vec = pss - p00

    #     # apply new scene position to keep the opposite side visually anchored
    #     self.setPos(pos0 + shift_scene_vec)

    #     # update rect (always origin-at-0,0 in local space)
    #     final_local_rect = QRectF(0, 0, new_w, new_h)
    #     self._geometry = UnitStrGeometry.from_px(rect=final_local_rect, pos=self.pos(), dpi=self.dpi)

    #     self.update_handles()
    #     self.item_changed.emit()

    def mousePressOnHandle(self, handle_item, event):
        r0 = self._geometry.to("px", self.dpi).rect                 # local rect (0,0,w,h)
        c  = r0.center()
        hp = handle_item.pos()                                      # handle LOCAL pos (child of element)

        # derive signs from handle’s local position relative to center
        def sign(v): return 0 if abs(v) < 1e-6 else (1 if v > 0 else -1)
        sx = sign(hp.x() - c.x())   # left = -1, right = +1, centers = 0
        sy = sign(hp.y() - c.y())   # top  = -1, bottom = +1, centers = 0

        self._pre_resize_state = {
            "rect0": r0,
            "pos0_scene": self.pos(),
            "handle_local0": self.mapFromScene(event.scenePos()),
            "sx": sx,
            "sy": sy,
        }

    def begin_handle_resize(self, handle_item, event):
        r0 = self._geometry.to("px", self.dpi).rect  # local rect, origin at (0,0)
        sx, sy, affect_w, affect_h = self._axes_for_handle(self._active_handle)

        self._pre_resize_state = {
            "rect0": r0,
            "pos0_scene": self.pos(),
            "handle_local0": self.mapFromScene(event.scenePos()),
            "sx": sx,
            "sy": sy,
            "affect_w": affect_w,
            "affect_h": affect_h,
        }


    def end_handle_resize(self):
        # good place to clear the snapshot, emit a finished signal,
        # or push an undo command using rect before/after if you track it
        self._pre_resize_state = None

    # def resize_from_handle(self, handle_type: HandleType, delta: QPointF, start_scene_rect: QRectF):
    #     """
    #     Resize by handle, correctly handling rotated items by temporarily aligning
    #     with the scene, performing the resize, and then restoring the rotation.
    #     """
    #     self.prepareGeometryChange()
        
    #     # --- Store original rotation and temporarily un-rotate the item ---
    #     original_rotation = self.rotation
    #     if original_rotation != 0:
    #         self.setRotation(0)

    #     # The rest of your scene-based logic now works perfectly because the item is axis-aligned.
    #     scene = self.scene()
    #     scene_rect = scene.sceneRect() if scene else QRectF()

    #     # Work in scene coordinates
    #     new_rect = QRectF(start_scene_rect)
        
    #     # Update rect based on handle type using scene coordinates
    #     if handle_type == HandleType.TOP_LEFT:
    #         new_rect.setTopLeft(new_rect.topLeft() + delta)
    #     elif handle_type == HandleType.TOP_CENTER:
    #         new_rect.setTop(new_rect.top() + delta.y())
    #     elif handle_type == HandleType.TOP_RIGHT:
    #         new_rect.setTopRight(new_rect.topRight() + delta)
    #     elif handle_type == HandleType.RIGHT_CENTER:
    #         new_rect.setRight(new_rect.right() + delta.x())
    #     elif handle_type == HandleType.BOTTOM_RIGHT:
    #         new_rect.setBottomRight(new_rect.bottomRight() + delta)
    #     elif handle_type == HandleType.BOTTOM_CENTER:
    #         new_rect.setBottom(new_rect.bottom() + delta.y())
    #     elif handle_type == HandleType.BOTTOM_LEFT:
    #         new_rect.setBottomLeft(new_rect.bottomLeft() + delta)
    #     elif handle_type == HandleType.LEFT_CENTER:
    #         new_rect.setLeft(new_rect.left() + delta.x())

    #     # Enforce minimum size (10x10 pixels)
    #     min_size = 10
    #     if new_rect.width() < min_size:
    #         if handle_type in (HandleType.LEFT_CENTER, HandleType.TOP_LEFT, HandleType.BOTTOM_LEFT):
    #             new_rect.setLeft(new_rect.right() - min_size)
    #         else:
    #             new_rect.setRight(new_rect.left() + min_size)
    #     if new_rect.height() < min_size:
    #         if handle_type in (HandleType.TOP_CENTER, HandleType.TOP_LEFT, HandleType.TOP_RIGHT):
    #             new_rect.setTop(new_rect.bottom() - min_size)
    #         else:
    #             new_rect.setBottom(new_rect.top() + min_size)

    #     # Constrain to scene boundaries
    #     if new_rect.left() < scene_rect.left():
    #         new_rect.setLeft(scene_rect.left())
    #     if new_rect.top() < scene_rect.top():
    #         new_rect.setTop(scene_rect.top())
    #     if new_rect.right() > scene_rect.right():
    #         new_rect.setRight(scene_rect.right())
    #     if new_rect.bottom() > scene_rect.bottom():
    #         new_rect.setBottom(scene_rect.bottom())

    #     # Update position and geometry based on the un-rotated resize
    #     new_scene_pos = new_rect.topLeft()
    #     new_local_rect = QRectF(0, 0, new_rect.width(), new_rect.height())
        
    #     self.setPos(new_scene_pos)
    #     self._geometry = UnitStrGeometry.from_px(
    #         rect=new_local_rect, pos=new_scene_pos, dpi=self.dpi
    #     )
        
    #     # --- Restore the original rotation ---
    #     if original_rotation != 0:
    #         # We must use the helper function to set the origin point correctly before rotating
    #         rotate_item(self, original_rotation)
    #         self._rotation = original_rotation # Ensure the internal state is correct

    #     # Final updates
    #     self.update_handles()
    #     self.item_changed.emit()
    #     self.update()
    # def resize_from_handle(self, handle_type: HandleType, delta: QPointF, start_scene_rect: QRectF):
    #     """Resize by handle: supports all 8 directions with proper boundary constraints."""
    #     self.prepareGeometryChange()
    #     dpi = self.dpi
    #     scene = self.scene()
    #     scene_rect = scene.sceneRect() if scene else QRectF()

    #     # 1. Convert starting rect and delta to local coordinates
    #     local_start_rect = self.mapRectFromScene(start_scene_rect)
    #     new_rect = QRectF(local_start_rect)
    #     delta_local = self.mapFromScene(delta) - self.mapFromScene(QPointF(0, 0))

    #     # 2. Update rect based on handle type
    #     if handle_type == HandleType.TOP_LEFT:
    #         new_rect.setTopLeft(new_rect.topLeft() + delta_local)
    #     elif handle_type == HandleType.TOP_CENTER:
    #         new_rect.setTop(new_rect.top() + delta_local.y())
    #     elif handle_type == HandleType.TOP_RIGHT:
    #         new_rect.setTopRight(new_rect.topRight() + delta_local)
    #     elif handle_type == HandleType.RIGHT_CENTER:
    #         new_rect.setRight(new_rect.right() + delta_local.x())
    #     elif handle_type == HandleType.BOTTOM_RIGHT:
    #         new_rect.setBottomRight(new_rect.bottomRight() + delta_local)
    #     elif handle_type == HandleType.BOTTOM_CENTER:
    #         new_rect.setBottom(new_rect.bottom() + delta_local.y())
    #     elif handle_type == HandleType.BOTTOM_LEFT:
    #         new_rect.setBottomLeft(new_rect.bottomLeft() + delta_local)
    #     elif handle_type == HandleType.LEFT_CENTER:
    #         new_rect.setLeft(new_rect.left() + delta_local.x())

    #     # 3. Enforce minimum size (10x10 pixels)
    #     min_size = 10
    #     if new_rect.width() < min_size:
    #         if handle_type in (HandleType.LEFT_CENTER, HandleType.TOP_LEFT, HandleType.BOTTOM_LEFT):
    #             new_rect.setLeft(new_rect.right() - min_size)
    #         else:
    #             new_rect.setRight(new_rect.left() + min_size)
    #     if new_rect.height() < min_size:
    #         if handle_type in (HandleType.TOP_CENTER, HandleType.TOP_LEFT, HandleType.TOP_RIGHT):
    #             new_rect.setTop(new_rect.bottom() - min_size)
    #         else:
    #             new_rect.setBottom(new_rect.top() + min_size)

    #     # 4. Constrain to scene boundaries
    #     new_scene_rect = self.mapRectToScene(new_rect)
    #     if new_scene_rect.left() < scene_rect.left():
    #         new_scene_rect.setLeft(scene_rect.left())
    #     if new_scene_rect.top() < scene_rect.top():
    #         new_scene_rect.setTop(scene_rect.top())
    #     if new_scene_rect.right() > scene_rect.right():
    #         new_scene_rect.setRight(scene_rect.right())
    #     if new_scene_rect.bottom() > scene_rect.bottom():
    #         new_scene_rect.setBottom(scene_rect.bottom())
        
    #     new_rect = self.mapRectFromScene(new_scene_rect)

    #     # 5. Snap to grid if enabled
    #     if hasattr(scene, "is_snap_to_grid") and scene.is_snap_to_grid:
    #         snapped_tl = scene.snap_to_grid(self.mapToScene(new_rect.topLeft()))
    #         snapped_br = scene.snap_to_grid(self.mapToScene(new_rect.bottomRight()))
    #         new_rect = self.mapRectFromScene(QRectF(snapped_tl, snapped_br))

    #     # 6. Update position and geometry
    #     new_scene_pos = self.mapToScene(new_rect.topLeft())
        
    #     # The dimensions of new_rect are correct, but its position is relative
    #     # to the old item position. We need a rect with the same dimensions but
    #     # at origin (0,0) for the new local coordinate system.
    #     new_local_bounds = QRectF(0, 0, new_rect.width(), new_rect.height())

    #     # Set the item's position to the new top-left corner in the scene
    #     self.setPos(new_scene_pos)

    #     # Create the new geometry object using the correct local bounds and new scene position
    #     self._geometry = UnitStrGeometry.from_px(
    #         rect=new_local_bounds,
    #         pos=new_scene_pos,
    #         dpi=self.dpi
    #     )

    #     # 7. Final updates
    #     self.update_handles()
    #     self.item_changed.emit()
    #     self.update()

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


