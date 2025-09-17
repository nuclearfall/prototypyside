# incremental_grid.py
from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import QRectF, QPointF, Qt, Slot, QEvent, QObject
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene

from prototypyside.utils.units.unit_str import UnitStr

DEFAULT_INCREMENTS = {
    "cm": {4: 0.125,  3: 0.25,   2: 0.50,  1: 2.0},
    "mm": {4: 2.5,    3: 5.0,    2: 10.0,  1: 25.0},
    "in": {4: 0.0625, 3: 0.125,  2: 0.25,  1: 0.5},
    "px": {4: 5.0,    3: 10.0,   2: 50.0,  1: 100.0},
    "pt": {4: 4.5,    3: 9.0,    2: 36.0,  1: 72.0},
}

# increments are converted to UnitStr.


DEFAULT_DARK  = 120
DEFAULT_LIGHT = 200


class IncrementalGrid(QGraphicsItem):
    """
    Scene-wide incremental grid with optional snapping enforcement.
    SAFE wiring: explicit attach/detach API. No disconnect warnings.
    """
    def __init__(
        self,
        settings,
        *,
        template: Optional[QGraphicsItem] = None,
        darkest: QColor = QColor(DEFAULT_DARK, DEFAULT_DARK, DEFAULT_DARK),
        lightest: QColor = QColor(DEFAULT_LIGHT, DEFAULT_LIGHT, DEFAULT_LIGHT),
        increment: Optional[dict] = None,
        snap_enabled: bool = True,
        enforce_enabled: bool = False,
        default_snap_level: int = 4,
        scene = None,
        parent: Optional[QGraphicsItem] = None,
    ):
        super().__init__(parent)
        self._settings   = settings
        self._template   = template
        self._increments = increment or DEFAULT_INCREMENTS
        self._darkest    = darkest
        self._lightest   = lightest

        self._snap_enabled     = bool(snap_enabled)
        self._enforce_enabled  = bool(enforce_enabled)
        self._default_level    = int(default_snap_level)

        self._rect = QRectF()                # cached sceneRect
        self._wired_scene: QGraphicsScene | None = None
        self._scene_event_proxy = self._SceneEventProxy(self)
        self._adjusting = False              # recursion guard

        self.setZValue(1)                  # behind items by default
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)

        self._contrast_mode = "normal"   # "normal" | "debug"

        # Current all increments are in given and used as float values,
        # but given that we will use UnitStringsFields that won't be the
        # case. For now we'll convert increments to UnitStr values.
        self.unit_str_inc = {outkey: {inkey: \
            UnitStr(inval, unit=outkey, dpi=template.dpi) \
            for inkey, inval in outval.items()} \
            for outkey, outval in DEFAULT_INCREMENTS.items()}

        self._settings.unit_changed.connect(self._on_unit_changed)

        # NEW: auto-attach if provided
        if scene is not None:
            self._wired_scene: QGraphicsScene = scene
            self.attach_to_scene(scene)

    # ───────────────────── Public toggles ─────────────────────
    @Slot(bool)
    def setSnapEnabled(self, enabled: bool):
        self._snap_enabled = bool(enabled)

    def isSnapEnabled(self) -> bool:
        return self._snap_enabled

    @Slot(bool)
    def setEnforcementEnabled(self, enabled: bool):
        self._enforce_enabled = bool(enabled)

    def isEnforcementEnabled(self) -> bool:
        return self._enforce_enabled

    def setDefaultSnapLevel(self, level: int):
        self._default_level = int(level)

    def defaultSnapLevel(self) -> int:
        return self._default_level

    # ───────────────────── Attach / Detach ─────────────────────
    def attach_to_scene(self, scene: QGraphicsScene | None):
        """Explicitly wire to a scene after addItem(self)."""
        if scene is None or scene is self._wired_scene:
            if scene is not None:
                self._sync_rect(scene)
            return
        self.detach_from_scene()
        try:
            scene.sceneRectChanged.connect(self._on_scene_rect_changed)
        except Exception:
            pass
        try:
            scene.installEventFilter(self._scene_event_proxy)
        except Exception:
            pass
        self._wired_scene = scene
        self._sync_rect(scene)

    def detach_from_scene(self):
        """Explicitly unwire from the current scene, if any."""
        if self._wired_scene is None:
            return
        scn = self._wired_scene
        try:
            scn.sceneRectChanged.disconnect(self._on_scene_rect_changed)
        except Exception:
            pass
        try:
            scn.removeEventFilter(self._scene_event_proxy)
        except Exception:
            pass
        self._wired_scene = None

    # ─────────────────── QGraphicsItem core ────────────────────
    def boundingRect(self) -> QRectF:
        return self._rect

    def set_contrast_mode(self, mode: str):
        self._contrast_mode = mode
        self.update()

    def paint(self, painter, *_):
            if not self.isVisible() or self._rect.isEmpty():
                return
            painter.save()
            try:
                painter.setRenderHint(QPainter.Antialiasing, False)
                base_pen = QPen(Qt.black)
                base_pen.setCosmetic(True)
                painter.setPen(base_pen)

                unit = getattr(self._settings, "display_unit", "in")
                increments = self._increments.get(unit, {})
                if not increments:
                    return

                levels = sorted(increments.keys(), reverse=True)
                num_levels = max(1, len(levels))
                gray_range = DEFAULT_LIGHT - DEFAULT_DARK

                # DEBUG: force high-contrast dark lines when needed
                def _level_color(i, level):
                    if self._contrast_mode == "debug":
                        # darkest possible for visibility; thicker major grid
                        return QColor(0, 0, 0) if level == 1 else QColor(40, 40, 40)
                    gray_value = DEFAULT_LIGHT - int(i * (gray_range / (num_levels - 1 or 1)))
                    return QColor(gray_value, gray_value, gray_value)

                origin = QPointF(0.0, 0.0)
                if self._template and hasattr(self._template, "mapToScene") and hasattr(self._template, "geometry"):
                    try:
                        origin = self._template.mapToScene(self._template.geometry.to(self.unit, dpi=self.dpi).rect)
                    except Exception:
                        origin = QPointF(0.0, 0.0)

                left, right, top, bottom = (
                    self._rect.left(), self._rect.right(), self._rect.top(), self._rect.bottom()
                )

                for i, level in enumerate(levels):
                    spacing = self.get_grid_spacing(level)
                    if spacing <= 0:
                        continue

                    pen = painter.pen()
                    pen.setColor(_level_color(i, level))
                    pen.setWidth(2 if level == 1 else 1)
                    painter.setPen(pen)

                    start_x = left  - math.fmod((left  - origin.x()), spacing)
                    start_y = top   - math.fmod((top   - origin.y()), spacing)

                    x = start_x
                    if spacing > 0 and x - spacing > left:
                        x -= spacing
                    while x <= right:
                        painter.drawLine(x, top, x, bottom)
                        x += spacing

                    y = start_y
                    if spacing > 0 and y - spacing > top:
                        y -= spacing
                    while y <= bottom:
                        painter.drawLine(left, y, right, y)
                        y += spacing
            finally:
                painter.restore()

    # ───────────────────── Grid helpers ───────────────────────
    def _raw_increment(self, level: int) -> float:
        return self._increments[self._settings.unit][level]

    def get_grid_spacing(self, level: int) -> float:
        inc = self._increments[self._settings.unit][level]
        return UnitStr(inc, unit=self._settings.unit, dpi=self._settings.dpi).px

    def snap_to_grid(self, pos: QPointF, level: int | None = None) -> QPointF:
        if not self._snap_enabled:
            return pos
        level = self._default_level if level is None else int(level)

        spacing = self.get_grid_spacing(level)
        if spacing <= 0:
            return pos

        origin = QPointF(0.0, 0.0)
        if self._template and hasattr(self._template, "mapToScene") and hasattr(self._template, "boundingRect"):
            try:
                origin = self._template.mapToScene(self._template.geometry.to(self.unit, unit=self.dpi))
            except Exception:
                origin = QPointF(0.0, 0.0)

        sx = round((pos.x() - origin.x()) / spacing) * spacing + origin.x()
        sy = round((pos.y() - origin.y()) / spacing) * spacing + origin.y()
        return QPointF(sx, sy)

    # ─────────────── Scene/unit reactions & sync ──────────────
    @Slot(QRectF)
    def _on_scene_rect_changed(self, rect: QRectF):
        self.prepareGeometryChange()
        self._rect = QRectF(rect)
        self.update()

    @Slot(str)
    def _on_unit_changed(self, _new_unit: str):
        self.update()

    def _sync_rect(self, scene: QGraphicsScene):
        """Initialize our cached rect from the current scene rect."""
        self.prepareGeometryChange()
        print(f'Scene rect is {scene.sceneRect()}')
        self._rect = QRectF(scene.sceneRect())
        self.update()

    def __del__(self):
        self.detach_from_scene()

    # ───────────────── Enforcement internals ──────────────────
    class _SceneEventProxy(QObject):
        """Event filter proxy to enforce snapping during drags/resizes."""
        def __init__(self, grid: "IncrementalGrid"):
            super().__init__()
            self._grid = grid

        def eventFilter(self, obj, event) -> bool:
            grid = self._grid
            if not grid._enforce_enabled or grid._adjusting:
                return False

            et = event.type()
            if et in (QEvent.GraphicsSceneMouseMove, QEvent.GraphicsSceneMouseRelease):
                scn: Optional[QGraphicsScene] = grid._wired_scene
                if scn is None:
                    return False
                grabbed = scn.mouseGrabberItem()
                if grabbed is None:
                    return False

                # 1) Position enforcement
                try:
                    grid._adjusting = True
                    snapped_pos = grid.snap_to_grid(grabbed.pos(), grid._default_level)
                    if snapped_pos != grabbed.pos():
                        try:
                            grabbed.setPos(snapped_pos)
                        except Exception:
                            pass
                finally:
                    grid._adjusting = False

                # 2) Optional resize cooperation hook
                if hasattr(grabbed, "request_rect_snap") and callable(getattr(grabbed, "request_rect_snap")):
                    try:
                        grid._adjusting = True
                        if hasattr(grabbed, "boundingRect") and hasattr(grabbed, "mapToScene"):
                            br = grabbed.boundingRect()
                            pts = grabbed.mapToScene(br)
                            xs = [p.x() for p in pts]
                            ys = [p.y() for p in pts]
                            rect_scene = QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
                        else:
                            rect_scene = QRectF(snapped_pos, snapped_pos)
                        _ = grabbed.request_rect_snap(rect_scene)
                    finally:
                        grid._adjusting = False

                return False

            return False
