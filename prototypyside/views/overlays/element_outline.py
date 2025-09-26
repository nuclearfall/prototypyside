# element_outline.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF, QSizeF, Signal
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import (QApplication, QGraphicsObject, 
    QGraphicsItem, QStyleOptionGraphicsItem, QGraphicsSceneHoverEvent, 
    QGraphicsSceneMouseEvent
)

from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.services.proto_class import ProtoClass
from prototypyside.widgets.text_overlay import TextOverlay


@dataclass(frozen=True)
class _Anchor:
    left:   bool
    right:  bool
    top:    bool
    bottom: bool

_ANCHORS = {
    "nw": _Anchor(True,  False, True,  False),
    "n":  _Anchor(False, False, True,  False),
    "ne": _Anchor(False, True,  True,  False),
    "e":  _Anchor(False, True,  False, False),
    "se": _Anchor(False, True,  False, True ),
    "s":  _Anchor(False, False, False, True ),
    "sw": _Anchor(True,  False, False, True ),
    "w":  _Anchor(True,  False, False, False),
}

def local_rect(rect_or_size):
    if isinstance(rect_or_size, (QRectF, QSizeF)):
        w = rect_or_size.width()
        h = rect_or_size.height()
        return QRectF(0, 0, w, h)
    return None

def _cursor_for_anchor(a: _Anchor) -> Qt.CursorShape:
    # Choose intuitive cursors; Qt flips under rotation automatically.
    if a.left and a.top:     return Qt.SizeFDiagCursor   # ↘︎↖︎
    if a.right and a.bottom: return Qt.SizeFDiagCursor
    if a.right and a.top:    return Qt.SizeBDiagCursor   # ↗︎↙︎
    if a.left and a.bottom:  return Qt.SizeBDiagCursor
    if a.left or a.right:    return Qt.SizeHorCursor
    if a.top or a.bottom:    return Qt.SizeVerCursor
    return Qt.ArrowCursor


class _ResizeHandle(QGraphicsObject):
    dragBegan = Signal(object)                 # self
    dragMoved = Signal(object, QPointF) # self, localDelta
    dragEnded = Signal(object)                 # self

    def __init__(self, outline: "ElementOutline", key: str, anchor: _Anchor, size: float = 4.0):
        super().__init__(outline)  # child of outline
        self.outline = outline
        self.key = key
        self.anchor = anchor
        self._size = size
        self._startScenePos = None
        # Ignore view transforms so the hit target stays ~constant on screen.
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        # We never want to select/move handles themselves.
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setAcceptHoverEvents(True)
        self.setCursor(_cursor_for_anchor(anchor))
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)

    # Small and cheap; no need for complex painting.
    def boundingRect(self) -> QRectF:
        s = self._size
        return QRectF(-s/2.0, -s/2.0, s, s)

    def render(self, ctx, painter: QPainter):
        # Keep it lightweight; outline decides visibility.
        if ctx.is_component_tab:
            painter.save()
            painter.setPen(QPen(QColor(0, 175, 236, 255)))
            painter.setBrush(QColor(0, 175, 236, 255))
            painter.drawRect(self.boundingRect())
            painter.restore()

    def paint(self, painter, option=None, widget=None):
        painter.save()
        self.render(self.outline.element.ctx, painter)
        painter.restore()

    def mousePressEvent(self, e):
        scene = self.scene()
        self._startScenePos = e.scenePos()
        self.dragBegan.emit(self)
        scene.sendEvent(self.outline.element, e)  # <-- correct target & var
        e.accept()

    def mouseMoveEvent(self, e: QGraphicsSceneMouseEvent):
        # Map delta to element-local space; rotation/scales are handled by Qt.
        el = self.outline.element
        localStart = el.mapFromScene(self._startScenePos)
        localNow   = el.mapFromScene(e.scenePos())
        localDelta = localNow - localStart
        self.dragMoved.emit(self, localDelta)
        e.accept()

    def mouseReleaseEvent(self, e: QGraphicsSceneMouseEvent):
        self.dragEnded.emit(self)
        e.accept()


# NOTE: this class is intentionally self-contained and does not import app-specific helpers,
# except for relying on the element exposing: _geometry, dpi, geometryAboutToChange, rectChanged.


class ElementOutline(QGraphicsObject):
    """
    Sets element outline and manages resize handles.
    IMPORTANT: uses self.element as the referenced element (matches your codebase).
    """

    def __init__(
        self,
        element,
        pen_color: QColor = QColor(0, 175, 236, 255),
        pen_width_px: float = 1.2,
        parent=None
    ):
        super().__init__(parent)
        self.element = element  # <— keep existing name
        self._ctx = element.ctx
        self._handles = {}
        self.pen_color = pen_color
        self.pen_width_px = pen_width_px
        # self.setParentItem(self.element)
        # Outline should not be pickable; element remains the primary selection.
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setAcceptHoverEvents(True)
        self.setZValue(self.element.zValue() + 1.0)
        self.setFlag(QGraphicsItem.ItemHasNoContents, False)

        # Signals to stay in sync with geometry & selection.
        if hasattr(self.element, "geometryAboutToChange"):
            self.element.geometryAboutToChange.connect(self.prepareGeometryChange)
        if hasattr(self.element, "geometryChanged"):
            self.element.geometryChanged.connect(self._on_geometry_changed)

        # If your element emits these, wire them (optional but nice).
        if hasattr(self.element, "selectionChanged"):
            self.element.selectionChanged.connect(self._on_selection_changed)
        if hasattr(self.element, "visibilityChanged"):
            self.element.visibilityChanged.connect(self.update)

        # Create handles once.
        self._create_handles()
        # Initial layout.
        self._on_geometry_changed()
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)

    # ---------- Public-ish helpers ----------

    def show_handles(self, show: bool):
        for h in self._handles.values():
            h.setVisible(bool(show))
        # self.update()  # refresh outline paint (selection cues, etc.)

    # ---------- Geometry plumbing ----------
    def _current_draw_rect(self) -> QRectF:
        """
        What the outline should draw around *right now*.
        For text, TextElementOutline overrides this to include expanded bounds.
        """
        return self.element.geometry.px.rect

    def _on_geometry_changed(self, *args):
        # Layout handles around the current draw rect; cheap early-out.
        r = self._current_draw_rect()

        # Position 8 handles at corners and mids.
        cx = (r.left() + r.right()) * 0.5
        cy = (r.top()  + r.bottom()) * 0.5
        pos = {
            "nw": QPointF(r.left(),  r.top()),
            "n":  QPointF(cx,        r.top()),
            "ne": QPointF(r.right(), r.top()),
            "e":  QPointF(r.right(), cy),
            "se": QPointF(r.right(), r.bottom()),
            "s":  QPointF(cx,        r.bottom()),
            "sw": QPointF(r.left(),  r.bottom()),
            "w":  QPointF(r.left(),  cy),
        }
        for k, h in self._handles.items():
            h.setPos(pos[k])

        # Only show when element is selected & visible (policy — tweak as you like).
        self.update_visibility_policy()
        self.update()

    def update_visibility_policy(self):
        is_selected = getattr(self.element, "isSelected", None)
        self.show_handles(is_selected)

    # ---------- Handles ----------

    def _create_handles(self):
        for key, anchor in _ANCHORS.items():
            h = _ResizeHandle(self, key, anchor)
            h.dragBegan.connect(self._on_drag_began)
            h.dragMoved.connect(self._on_drag_moved)
            h.dragEnded.connect(self._on_drag_ended)
            h.hide()  # selection will reveal
            self._handles[key] = h

    def _on_drag_began(self, handle: _ResizeHandle):
        # Cache original local rect and parent-space position once
        self._dragOriginRect = QRectF(self._current_draw_rect())   # (0,0,w,h) in LOCAL
        self._dragOriginPosParent = QPointF(self.element.pos())        # parent-space pos

    def _on_drag_moved(self, handle: _ResizeHandle, localDelta: QPointF):
        a  = handle.anchor
        r0 = UnitStrGeometry(self._dragOriginRect, unit="px", dpi=300).px.rect
        scene = self.element.scene()
        # Compute new size from the handle's side(s). Local delta is already in the element's space.
        # Right/bottom increase size with +dx/+dy; left/top increase with -dx/-dy.
        new_w = r0.width()
        new_h = r0.height()

        if a.right:
            new_w = r0.width() + localDelta.x()
        elif a.left:
            new_w = r0.width() - localDelta.x()

        if a.bottom:
            new_h = r0.height() + localDelta.y()
        elif a.top:
            new_h = r0.height() - localDelta.y()

        # Enforce a minimum (avoid collapsing/inversion)
        min_size = 1.0
        new_w = max(min_size, new_w)
        new_h = max(min_size, new_h)

        # Optional: aspect ratio with Shift
        mods = QApplication.keyboardModifiers()
        if mods & Qt.ShiftModifier and r0.height() > 0:
            ar = r0.width() / r0.height()
            # Corner drag: lock AR by adjusting the dominant axis
            if (a.left or a.right) and (a.top or a.bottom):
                dw = abs(new_w - r0.width())
                dh = abs(new_h - r0.height())
                if dw >= dh:
                    new_h = max(min_size, new_w / ar)
                else:
                    new_w = max(min_size, new_h * ar)
            elif (a.left or a.right):
                new_h = max(min_size, new_w / ar)
            elif (a.top or a.bottom):
                new_w = max(min_size, new_h * ar)

        # Because our local rect must remain (0,0,new_w,new_h),
        # dragging from LEFT/TOP requires shifting the item's position so
        # the opposite edge stays visually anchored.
        shift_x_local = (r0.width()  - new_w) if a.left  else 0.0
        shift_y_local = (r0.height() - new_h) if a.top   else 0.0
        # Convert the local shift vector to a parent-space delta
        p0 = self.element.mapToParent(QPointF(0.0, 0.0))
        p1 = self.element.mapToParent(scene.snap_to_grid(QPointF(shift_x_local, shift_y_local)))
        shift_parent = p1 - p0
        # We'll treat w, h as a point to use snap_to_grid logic:
        snapped_wh = scene.snap_to_grid(QPointF(new_w, new_h))
        new_w = snapped_wh.x()
        new_h = snapped_wh.y()

        # Commit: move the item first, then set the new rect (still local at 0,0)
        # This ensures pos() reflects the origin shift for left/top drags.
        self.element.setPos(self._dragOriginPosParent + shift_parent)

        # Set the new local rect via the element API (fires signals/handle relayout)

        self.element.setRect(QRectF(0.0, 0.0, new_w, new_h))

    def _on_drag_ended(self, handle: _ResizeHandle):
        # If you batch undo on scene press/release, nothing to do here.
        # Otherwise, push a single undo now with the element’s new geometry.
        pass

    # ---------- Painting ----------

    def boundingRect(self) -> QRectF:
        # Include a little padding for the handles around the draw rect.
        r = self._current_draw_rect()
        pad = 12.0
        return r.adjusted(-pad, -pad, pad, pad)

    def render(self, ctx, painter: QPainter):
        # Base outline paint: TextElementOutline overrides as needed.
        if ctx.is_gui and ctx.is_component_tab:
            selection_state = self.element.isSelected()

            self.show_handles(selection_state)
            r = self._current_draw_rect()
            painter.save()
            pen = QPen(self.pen_color, self.pen_width_px)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(r)
            painter.restore()

    def paint(self, painter:QPainter, option=None, widget=None):
        painter.save()
        self.render(self.element.ctx, painter)
        painter.restore()

    def _on_selection_changed(self, *args):
        self.update_visibility_policy()


# class TextOutline(ElementOutline):
#     # NEW: bubble editor lifecycle to the outside so your controller/tab can push undo
#     textEditStarted   = Signal(object)                 # (element)
#     textEditCommitted = Signal(object, str, str)       # (element, new_html, old_html)
#     textEditCanceled  = Signal(object)                 # (element)

#     def __init__(
#         self,
#         element,
#         pen_color: QColor = QColor(0, 175, 236, 255),
#         pen_width_px: float = 1.2,
#         parent=None
#     ):
#         super().__init__(
#             element=element, 
#             pen_color=pen_color, 
#             pen_width_px=pen_width_px, 
#             parent=parent
#         )

#     # ---------------------------------------------------------------------
#     # Existing properties (unchanged)
#     # @property
#     # def renderer(self):
#     #     return self.element._renderer

#     # @property
#     # def has_overflow(self) -> bool:
#     #     return self.element.renderer.has_overflow

#     # @property
#     # def is_expanded(self):
#     #     return self.element.renderer.is_expanded

#     # @is_expanded.setter
#     # def is_expanded(self, state: bool):
#     #     self.element.renderer.is_expanded = state
#     #     self.expandedChanged.emit(state)
#     #     self.update()

#     # ---------- Utilities ----------
#     def base_rect(self) -> QRectF:
#         return self.element.geometry.to(self.element.unit, dpi=self.element.dpi).rect

#     def frame_rect(self) -> QRectF:
#         if not self.element.renderer.has_overflow or self.element.renderer.can_expand:
#             return self.base_rect()
#         if self.is_expanded:
#             return self.element.renderer.overset_rect
#         return self.base_rect()

#     def boundingRect(self) -> QRectF:
#         return self.united_rect()

#     @property
#     def can_expand(self) -> bool:
#         return self.element.renderer.has_overflow and not self.element.renderer.is_expanded

#     def _button_size_px(self) -> float:
#         return float(UnitStr("4 pt").to(self.element.unit, dpi=self.element.dpi))

#     def hit_and_united_rect(self) -> tuple[QRectF | None, QRectF]:
#         base = self.frame_rect()
#         hit = None
#         if self.element.renderer.has_overflow:
#             size_px = 18.0
#             x = base.right() - size_px
#             y = base.top() + (2 * size_px)
#             hit = QRectF(x, y, size_px, size_px)
#         return hit, base.united(hit) if hit else base

#     def hit_rect(self) -> QRectF | None:
#         hit, _ = self.hit_and_united_rect()
#         return hit

#     def united_rect(self) -> QRectF:
#         _, united = self.hit_and_united_rect()
#         return united

#     def render(self, ctx, painter: QPainter):
#         if ctx.is_component_tab and ctx.is_gui:
#             painter.save()
#             hit = self.hit_rect()
#             pen = QPen(self.pen_color, self.pen_width_px)
#             painter.setPen(pen)

#             if hit:
#                 painter.save()
#                 box_pen = QPen(pen)
#                 box_pen.setCosmetic(True)
#                 painter.setPen(box_pen)
#                 painter.setBrush(Qt.NoBrush)
#                 painter.drawRect(hit)

#                 pad = 0.1 * hit.width()
#                 inner = hit.adjusted(pad, pad, -pad, -pad)
#                 cx, cy = inner.center().x(), inner.center().y()
#                 painter.drawLine(inner.left(), cy, inner.right(), cy)
#                 if not self.element.renderer.is_expanded:
#                     painter.drawLine(cx, inner.top(), cx, inner.bottom())
#                 painter.restore()

#             painter.restore()

#     # ---------------------------------------------------------------------
#     # Mouse events

#     def mousePressEvent(self, e: QGraphicsSceneMouseEvent):
#         hr = self.hit_rect()
#         if hr is not None and not hr.isNull() and hr.contains(e.pos()):
#             self.prepareGeometryChange()
#             self.element.renderer.is_expanded = not self.element.renderer.is_expanded
#             self.update()
#             self.element.update()
#             e.accept()
#             return
#         e.ignore()
