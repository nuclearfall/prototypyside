# prototypyside/mixins/rotatable_mixin.py
from __future__ import annotations
from contextlib import contextmanager
from typing import Literal, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QTransform, QPainter
from PySide6.QtWidgets import QGraphicsItem

# If you already have a RenderMode enum, import it.
try:
    from prototypyside.models.component_template import RenderMode
except Exception:
    # Fallback to simple sentinel; replace with your real RenderMode
    class RenderMode:
        GUI = 1
        EXPORT = 2

PivotMode = Literal["center", "top_left", "custom"]

class RotatableMixin:
    """
    Unifies rotation behavior across GUI (QGraphicsItem) and offscreen/export painters.
    - Store rotation in degrees.
    - Choose a pivot (center, top_left, or custom point in *item-local px*).
    - Use begin_rotated_paint(...) in paint() to apply the right strategy automatically.
    """

    # ---- Public config (backed by _rotation, etc.) ----
    _rotation: float = 0.0
    _pivot_mode: PivotMode = "center"
    _pivot_custom_px: Optional[QPointF] = None  # local px coords

    # Optional margin pad used to expand boundingRect for rotated content
    _rotation_pad_px: float = 1.0

    # ---- Basic API ----
    def rotation(self) -> float:
        return float(getattr(self, "_rotation", 0.0))

    def set_rotation(self, degrees: float) -> None:
        self._rotation = float(degrees)

    def pivot_mode(self) -> PivotMode:
        return getattr(self, "_pivot_mode", "center")

    def set_pivot_mode(self, mode: PivotMode) -> None:
        assert mode in ("center", "top_left", "custom")
        self._pivot_mode = mode

    def set_custom_pivot_px(self, point: Optional[QPointF]) -> None:
        """Set a custom pivot in *local px* space."""
        self._pivot_custom_px = point

    # ---- Derived values ----
    def _pivot_point_px(self, content_rect_px: QRectF) -> QPointF:
        mode = self.pivot_mode()
        if mode == "center":
            return QPointF(content_rect_px.center())
        if mode == "top_left":
            return QPointF(content_rect_px.topLeft())
        # custom
        if self._pivot_custom_px is not None:
            return QPointF(self._pivot_custom_px)
        # fallback: center
        return QPointF(content_rect_px.center())

    def rotation_transform_px(self, content_rect_px: QRectF) -> QTransform:
        """Transform that rotates around the configured pivot."""
        t = QTransform()
        angle = self.rotation
        if abs(angle) < 1e-7:
            return t
        pivot = self._pivot_point_px(content_rect_px)
        t.translate(pivot.x(), pivot.y())
        t.rotate(angle)
        t.translate(-pivot.x(), -pivot.y())
        return t

    # ---- Paint helpers ----
    @contextmanager
    def begin_rotated_paint(
        self,
        painter: QPainter,
        content_rect_px: QRectF,
        render_mode: int,
        item_for_gui_sync: Optional[QGraphicsItem] = None,
    ):
        """
        Use this at the start of paint():

        with self.begin_rotated_paint(painter, rect_px, render_mode, item_for_gui_sync=self):
            ... draw unrotated content in local coordinates ...

        Behavior:
          - In GUI mode (RenderMode.GUI) and if item_for_gui_sync is a QGraphicsItem,
            we *sync* the item's transformOrigin/rotation and DO NOT apply a painter transform.
          - Otherwise, we apply a QTransform to the painter for the duration of the block.
        """
        angle = self.rotation
        if abs(angle) < 1e-7:
            # No rotation → no-op
            yield
            return

        if render_mode == getattr(RenderMode, "GUI", 1) and isinstance(item_for_gui_sync, QGraphicsItem):
            # Use native QGraphicsItem rotation for proper picking/handles/hover:
            pivot = self._pivot_point_px(content_rect_px)
            # transform origin is in item local coords
            item_for_gui_sync.setTransformOriginPoint(pivot)
            item_for_gui_sync.setRotation(angle)
            # No painter transform here; QGI handles it
            yield
            return

        # Offscreen/export or non-QGraphics case → painter-based rotation
        painter.save()
        painter.setWorldTransform(self.rotation_transform_px(content_rect_px), True)
        try:
            yield
        finally:
            painter.restore()

    # ---- Geometry helpers for bounding/shape mapping ----
    def rotated_bounding_rect_px(self, unrotated_rect_px: QRectF) -> QRectF:
        t = self.rotation_transform_px(unrotated_rect_px)
        r = t.mapRect(unrotated_rect_px)
        pad = getattr(self, "_rotation_pad_px", 1.0)
        return r.adjusted(-pad, -pad, pad, pad)

    def map_path_with_rotation(self, path, content_rect_px: QRectF):
        """
        Return a new QPainterPath mapped by the current rotation transform.
        Useful for shape() overrides.
        """
        t = self.rotation_transform_px(content_rect_px)
        return t.map(path)

    # ---- (De)serialization helpers (optional) ----
    def rotation_to_dict(self) -> Tuple[float, str, Optional[Tuple[float, float]]]:
        custom = None
        if self._pivot_custom_px is not None:
            custom = (float(self._pivot_custom_px.x()), float(self._pivot_custom_px.y()))
        return (self.rotation, self.pivot_mode(), custom)

    def rotation_from_dict(self, data) -> None:
        """
        data may be a dict like:
          {"rotation": 15.0, "pivot_mode": "center", "pivot_custom_px": [12.0, 34.0]}
        or a tuple from rotation_to_dict()
        """
        if isinstance(data, dict):
            self.set_rotation(float(data.get("rotation", 0.0)))
            self.set_pivot_mode(data.get("pivot_mode", "center"))
            tup = data.get("pivot_custom_px")
            self.set_custom_pivot_px(QPointF(tup[0], tup[1])) if tup else self.set_custom_pivot_px(None)
        elif isinstance(data, (tuple, list)) and len(data) in (2, 3):
            deg, mode = data[0], data[1]
            self.set_rotation(float(deg))
            self.set_pivot_mode(mode)  # type: ignore[arg-type]
            if len(data) == 3 and data[2] is not None:
                x, y = data[2]
                self.set_custom_pivot_px(QPointF(float(x), float(y)))
            else:
                self.set_custom_pivot_px(None)
