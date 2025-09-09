from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QGraphicsObject, QGraphicsItem, QGraphicsSceneHoverEvent, QGraphicsSceneMouseEvent

from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.services.proto_class import ProtoClass



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

    def __init__(self, outline: "ElementOutline", key: str, anchor: _Anchor, size: float = 8.0):
        super().__init__(outline)  # child of outline
        self.outline = outline
        self.key = key
        self.anchor = anchor
        self._size = size

        # Ignore view transforms so the hit target stays ~constant on screen.
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        # We never want to select/move handles themselves.
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setAcceptedMouseButtons(QtCore.Qt.LeftButton)
        self.setAcceptHoverEvents(True)
        self.setCursor(_cursor_for_anchor(anchor))

    # Small and cheap; no need for complex painting.
    def boundingRect(self) -> QtCore.QRectF:
        s = self._size
        return QtCore.QRectF(-s/2.0, -s/2.0, s, s)

    def paint(self, p: QtGui.QPainter, opt, widget=None):
        # Keep it lightweight; outline decides visibility.
        p.save()
        p.setPen(QtGui.QPen(QtCore.Qt.black))
        p.setBrush(QtCore.Qt.white)
        p.drawRect(self.boundingRect())
        p.restore()

    def mousePressEvent(self, e: QGraphicsSceneMouseEvent):
        self._startScenePos = e.scenePos()
        self.dragBegan.emit(self)
        e.accept()

    def mouseMoveEvent(self, e: QGraphicsSceneMouseEvent):
        # Map delta to element-local space; rotation/scales are handled by Qt.
        el = self.outline._el
        localStart = el.mapFromScene(self._startScenePos)
        localNow   = el.mapFromScene(e.scenePos())
        localDelta = localNow - localStart
        self.dragMoved.emit(self, localDelta)
        e.accept()

    def mouseReleaseEvent(self, e: QGraphicsSceneMouseEvent):
        self.dragEnded.emit(self)
        e.accept()

# prototypyside/views/overlays/element_outline.py

from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF, QObject
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QGraphicsObject

# NOTE: this class is intentionally self-contained and does not import app-specific helpers,
# except for relying on the element exposing: _geometry, dpi, geometryAboutToChange, rectChanged.


class ElementOutline(QGraphicsObject):
    """
    Generic outline overlay. Lives as a child of the element so coords are local.

    Expectations:
      - target element stores geometry in UnitStrGeometry (local rect always (0,0,w,h)),
        with scene position separate in geometry.px.pos.
      - element exposes Signals:
          geometryAboutToChange(old_geom)
          rectChanged(QRectF)  # px-space convenience signal
          geometryChanged(new_geom)  # optional; we use if present
      - element provides .dpi
    """
    def __init__(
        self,
        target_element: QGraphicsObject,
        pen_color: QColor = QColor(0, 175, 236, 255),
        pen_width_px: float = 1.2,
    ) -> None:
        super().__init__(parent=target_element)

        # --- config / public attrs expected by rest of app ---
        self._el = target_element
        self.pen_color = QColor(pen_color)
        self.pen_width_px = float(pen_width_px)
        self.is_hovered: bool = False

        # Z just above element (handles, if any, can set higher z)
        try:
            self.setZValue(self._el.zValue() + 0.5)
        except Exception:
            pass

        # Interaction policy (visual only; no selection/move)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setFlag(QGraphicsObject.ItemIsSelectable, False)
        self.setFlag(QGraphicsObject.ItemIsMovable, False)

        # --- keep outline geometry in sync with element geometry ---
        # We handle both the "about to change" (for prepareGeometryChange)
        # and "changed" (to repaint). We also connect rectChanged for convenience.
        # All of these exist in your ComponentElement.
        if hasattr(self._el, "geometryAboutToChange"):
            self._el.geometryAboutToChange.connect(self._on_el_geometry_about_to_change)
        if hasattr(self._el, "rectChanged"):
            self._el.rectChanged.connect(self._on_el_rect_changed)
        if hasattr(self._el, "geometryChanged"):
            self._el.geometryChanged.connect(self._on_el_geometry_changed)

    # ----- convenience -----
    @property
    def dpi(self) -> float:
        # Elements expose dpi; fall back to 96 if missing
        return getattr(self._el, "dpi", 96.0)

    def frame_rect(self) -> QRectF:
        """
        The element’s local frame. With UnitStrGeometry we always expect (0,0,w,h).
        """
        geom = getattr(self._el, "_geometry", None)
        if geom is None:
            return QRectF()
        # UnitStrGeometry -> px -> QRectF
        px = geom.to("px", dpi=self.dpi)
        return QRectF(px.rect)

    def _outline_margin_px(self) -> float:
        """
        Extra outward padding so the outline’s boundingRect fully contains
        the painted stroke and the hover highlight (cosmetic pen).
        """
        # Base stroke + small cushion for hover ring (drawn with cosmetic width ~2px)
        return max(2.0, self.pen_width_px * 0.5 + 1.5)

    # ----- QGraphicsObject overrides -----
    def boundingRect(self) -> QRectF:
        # Keep it tight around the element frame, expanded by the margin
        r = self.frame_rect()
        if r.isNull():
            return QRectF()
        m = self._outline_margin_px()
        return r.adjusted(-m, -m, m, m)

    # ----- painting -----
    def paint(self, painter: QPainter, option, widget=None) -> None:
        rect = self.frame_rect()
        if rect.isNull():
            return

        painter.save()

        # Base outline
        pen = QPen(self.pen_color)
        pen.setWidthF(self.pen_width_px)  # keep same behavior as before (non-cosmetic)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        # Sub-pixel adjust for crisp stroke
        painter.drawRect(rect.adjusted(0.5, 0.5, -0.5, -0.5))

        # Hover accent (cosmetic so it reads at any zoom; matches current behavior)
        if self.is_hovered:
            hover_pen = QPen(QColor(0, 195, 255, 255))
            hover_pen.setWidthF(2.0)
            hover_pen.setCosmetic(True)
            painter.setPen(hover_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect.adjusted(1.0, 1.0, -1.0, -1.0))

        painter.restore()

    # ----- hover -----
    def hoverMoveEvent(self, ev) -> None:
        hovered = self.frame_rect().contains(ev.pos())
        if hovered != self.is_hovered:
            self.is_hovered = hovered
            self.update()
        self.setCursor(Qt.PointingHandCursor if hovered else Qt.ArrowCursor)
        super().hoverMoveEvent(ev)

    def hoverLeaveEvent(self, ev) -> None:
        if self.is_hovered:
            self.is_hovered = False
            self.update()
        self.unsetCursor()
        super().hoverLeaveEvent(ev)

    # ----- element geometry sync -----
    def _on_el_geometry_about_to_change(self, *_):
        # Element’s bounding rect is about to change – announce ours too
        self.prepareGeometryChange()

    def _on_el_rect_changed(self, *_):
        # After element rect changed, repaint outline
        # (boundingRect() already updated via prepareGeometryChange above)
        self.update()

    def _on_el_geometry_changed(self, *_):
        # Safety: some code paths may emit geometryChanged without rectChanged
        self.update()


# class ElementOutline(QGraphicsObject):
#     """
#     Generic outline overlay. Lives as a child of the element so coords are local.
#     """
#     def __init__(
#         self,
#         target_element,
#         pen_color: QColor = QColor(0, 175, 236, 255),
#         pen_width_px: float = 1.2,
#     ):
#         super().__init__(parent=target_element)

#         self._el = target_element
#         self.pen_color = pen_color
#         self.pen_width_px = float(pen_width_px)
#         self.is_hovered = False
#         # --- in TextOutline.__init__ ---
#         self._is_expanded = False
#         self._cached_overset_rect: QRectF | None = None

#         # Draw above the element (but below handles if they use a higher z)
#         self.setZValue(self._el.zValue() + 0.5)
#         self.setAcceptHoverEvents(True)
#         self.setAcceptedMouseButtons(Qt.LeftButton)
#         self.setFlag(QGraphicsObject.ItemIsSelectable, False)
#         self.setFlag(QGraphicsObject.ItemIsMovable, False)

#     # ----- geometry -----
#     def frame_rect(self) -> QRectF:
#         return self._el._geometry.to("px", dpi=self._el.dpi).rect

#     def el_rect(self):
#         pass

#     def boundingRect(self) -> QRectF:
#         # Base outline just tracks the element rect.
#         return self.frame_rect()

#     # ----- painting -----
#     def paint(self, painter: QPainter, option, widget=None):
#         painter.save()
#         rect = self.frame_rect()

#         pen = QPen(self.pen_color)
#         pen.setWidthF(self.pen_width_px)
#         painter.setPen(pen)
#         painter.setBrush(Qt.NoBrush)
#         painter.drawRect(rect.adjusted(0.5, 0.5, -0.5, -0.5))

#         if self.is_hovered:
#             hover_pen = QPen(QColor(0, 195, 255, 255))
#             hover_pen.setWidthF(2.0)
#             hover_pen.setCosmetic(True)
#             painter.setPen(hover_pen)
#             painter.drawRect(rect.adjusted(1, 1, -1, -1))

#         painter.restore()

#     # ----- hover -----

#     def hoverMoveEvent(self, ev):
#         hovered = self.frame_rect().contains(ev.pos())
#         if hovered != self.is_hovered:
#             self.is_hovered = hovered
#             self.update()
#         self.setCursor(Qt.PointingHandCursor if hovered else Qt.ArrowCursor)

#     def hoverLeaveEvent(self, ev):
#         if self.is_hovered:
#             self.is_hovered = False
#             self.update()
#         self.unsetCursor()


class TextOutline(ElementOutline):

    def __init__(
        self,
        target_element,
        pen_color: QColor = QColor(0, 175, 236, 255),
        pen_width_px: float = 1.2,
    ):
        super().__init__(target_element=target_element,
                         pen_color=pen_color,
                         pen_width_px=pen_width_px)

        self._is_expanded = False

    @property
    def renderer(self):
        return self._el._renderer

    # --- fix the setter; keep it tiny & authoritative ---
    @property
    def is_expanded(self) -> bool:
        return self._is_expanded

    @is_expanded.setter
    def is_expanded(self, state: bool) -> None:
        state = bool(state)
        if state == self._is_expanded:
            return

        # both outline and element bounding rects will change
        self._el.prepareGeometryChange()
        self.prepareGeometryChange()

        if state:
            r = getattr(self._el, "_renderer", None)
            orc = getattr(r, "overset_rect", None)
            if isinstance(orc, QRectF) and not orc.isNull():
                self._cached_overset_rect = QRectF(orc)
            else:
                self._cached_overset_rect = QRectF(self.el_rect())
        else:
            self._cached_overset_rect = None

        # keep renderer in sync if it cares
        if hasattr(self._el, "_renderer"):
            self._el._renderer.is_expanded = state

        self._is_expanded = state



    # ---------- Utilities ----------
    def el_rect(self) -> QRectF:
        return self._el._geometry.to("px", dpi=self._el.dpi).rect

    # Fix overset_rect() – use cached rect while expanded, and fix the return typo
    def overset_rect(self) -> QRectF:
        if self.is_expanded and isinstance(self._cached_overset_rect, QRectF):
            return self._cached_overset_rect
        r = getattr(self._el, "_renderer", None)
        if r and getattr(r, "has_overflow", False) and isinstance(getattr(r, "overset_rect", None), QRectF):
            return r.overset_rect
        return self.el_rect()   # <-- fixed typo: was return el_rect()

    # frame_rect() stays the same but now respects the cache
    def frame_rect(self) -> QRectF:
        if self.is_expanded:
            r = self.overset_rect()
            if isinstance(r, QRectF):
                return r
        return self.el_rect()

    # --- show the button whenever we're expanded OR we truly have overflow ---
    @property
    def has_overflow(self) -> bool:
        if self.is_expanded:
            return True
        r = getattr(self._el, "_renderer", None)
        return bool(r and getattr(r, "has_overflow", False))


    @property
    def can_expand(self) -> bool:
        return self.has_overflow and not self.is_expanded

    # ---------- Hit target for the ± button ----------
    def _button_size_px(self) -> float:
        # Keep it physically sized
        return float(UnitStr("4 pt").to("px", dpi=self._el.dpi))

    # --- hit/united stays the same; now benefits from the new has_overflow ---
    def hit_and_united_rect(self) -> tuple[Optional[QRectF], QRectF]:
        base = self.frame_rect()
        if not self.has_overflow:
            return None, base
        size_px = self._button_size_px()
        x = base.right() - size_px
        y = base.top() + (2 * size_px)
        hit = QRectF(x, y, size_px, size_px)
        return hit, base.united(hit)

    # def hit_and_united_rect(self) -> tuple[Optional[QRectF], QRectF]:
    #     base = self.frame_rect()

    #     if not self.has_overflow:
    #         # Nothing to click; just return the base rect
    #         return None, base

    #     size_px = self._button_size_px()
    #     # Place near the top-right *inside* the frame
    #     x = base.right() - size_px
    #     y = base.top() + (2 * size_px)

    #     hit = QRectF(x, y, size_px, size_px)
    #     united = base.united(hit)
        return hit, united

    def hit_rect(self) -> Optional[QRectF]:
        hit, _ = self.hit_and_united_rect()
        return hit

    def united_rect(self) -> QRectF:
        _, united = self.hit_and_united_rect()
        return united

    def boundingRect(self) -> QRectF: 
        return self.united_rect()

    # ---------- Paint ----------
    def paint(self, painter: QPainter, option, widget=None):
        painter.save()
        hit, frame = self.hit_and_united_rect()

        pen = QPen(self.pen_color)
        painter.setPen(pen)
        pen.setWidthF(self.pen_width_px)
        painter.setBrush(Qt.NoBrush)
        painter.save()

        if self.is_hovered:
            hover_pen = QPen(QColor(0, 195, 255, 80))
            hover_pen.setWidthF(2.0)
            # hover_pen.setCosmetic(True)
            pen.setWidthF(self.pen_width_px * 2.0)
            painter.setPen(hover_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(frame.adjusted(1, 1, -1, -1))
        else:
            painter.drawRect(frame.adjusted(0.5, 0.5, -0.5, -0.5))

        painter.restore()

        # --- (tiny tidy) paint: use the cosmetic pen when drawing the button ---
        if hit:
            box_pen = QPen(pen)
            box_pen.setCosmetic(True)
            painter.setPen(box_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(hit)

            pad = 0.1 * hit.width()
            inner = hit.adjusted(pad, pad, -pad, -pad)
            cx, cy = inner.center().x(), inner.center().y()

            # minus always
            painter.drawLine(QPointF(inner.left(), cy), QPointF(inner.right(), cy))

            # plus stem only when NOT expanded
            if not self.is_expanded:
                painter.drawLine(QPointF(cx, inner.top()), QPointF(cx, inner.bottom()))

        painter.restore()

    # ---------- Events ----------
    # mousePressEvent – notify the ELEMENT (not only the outline) that its bounding rect changes
    def mousePressEvent(self, ev):
        hit = self.hit_rect()
        if ev.button() == Qt.LeftButton and (hit is not None) and hit.contains(ev.pos()):
            # Bounding rects will change for both outline and element
            self._el.prepareGeometryChange()
            self.prepareGeometryChange()

            self.is_expanded = not self.is_expanded

            self._el.update()
            self.update()
            ev.accept()
            return
        super().mousePressEvent(ev)

