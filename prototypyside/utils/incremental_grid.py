from PySide6.QtCore   import QRectF, QPointF, Qt, Slot
from PySide6.QtGui    import QPainter, QColor, QPen
from PySide6.QtWidgets import QGraphicsItem
from prototypyside.utils.units.unit_str import UnitStr

DEFAULT_INCREMENTS = {   # used when caller passes increment=None
    "cm": {3: 0.25, 2: 0.50, 1:  2.0},
    "mm": {4:    2.5, 3:   5, 2: 10.0, 1:25},
    "in": {4:0.0625, 3: 0.125, 2:  0.5, 1: 1.0},
    "px": {3:   10, 2:   50, 1:100.0},
    "pt": {4:    4.5, 3: 9, 2:   36, 1: 72.0},
}


DEFAULT_DARK  = 180
DEFAULT_LIGHT = 240

class IncrementalGrid(QGraphicsItem):
    """Multi-level incremental grid that also offers snap-to-grid."""
    def __init__(
        self, settings, *,
        darkest=QColor(DEFAULT_DARK),
        lightest=QColor(DEFAULT_LIGHT),
        increment=None,
        snap_enabled=True,
        parent=None
    ):
        super().__init__(parent)                         # parent is a QGraphicsItem or None
        self._settings   = settings
        self._increments = increment or DEFAULT_INCREMENTS
        self._darkest    = darkest
        self._lightest   = lightest
        self._snap       = snap_enabled

        self.setZValue(-50)                              # template = -100, items ≥ 0
        self.setAcceptedMouseButtons(Qt.NoButton)
        # React to global unit switches
        self._settings.unit_changed.connect(self._on_unit_changed)

    # ───────────────────────────────────── QGraphicsItem overrides ─────────
    def boundingRect(self) -> QRectF:
        return self.scene().sceneRect()

    def paint(self, painter, *_):
        if not self.isVisible():
            return
        rect = self.scene().sceneRect()
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, False)

        unit = self._settings.unit
        increments = self._increments.get(unit, {})
        levels = sorted(increments.keys(), reverse=True)
        num_levels = len(levels)

        gray_range = DEFAULT_LIGHT - DEFAULT_DARK

        for i, level in enumerate(levels):
            spacing = self.get_grid_spacing(level)

            gray_value = DEFAULT_LIGHT - int(i * (gray_range / max(1, num_levels - 1)))
            pen = QPen(QColor(gray_value, gray_value, gray_value))
            painter.setPen(pen)

            left = int(rect.left())
            right = int(rect.right())
            top = int(rect.top())
            bottom = int(rect.bottom())

            x = left - (left % spacing)
            while x < right:
                painter.drawLine(x, top, x, bottom)
                x += spacing

            y = top - (top % spacing)
            while y < bottom:
                painter.drawLine(left, y, right, y)
                y += spacing

    # def paint(self, painter: QPainter, *_):
    #     if not self.isVisible():
    #         return

    #     painter.save()
    #     painter.setRenderHint(QPainter.Antialiasing, False)

    #     unit = self._settings.unit
    #     increments = self._increments.get(unit, {})
    #     levels = sorted(increments.keys(), reverse=True)
    #     num_levels = len(levels)


    #     rect = self.boundingRect()
    #     left   = int(rect.left())
    #     right  = int(rect.right())
    #     top    = int(rect.top())
    #     bottom = int(rect.bottom())

    #     for i, level in enumerate(levels):
    #         spacing = self.get_grid_spacing(level)

    #         gray_value = light - int(i * (gray_range / max(1, num_levels - 1)))
    #         pen = QPen(QColor(gray_value, gray_value, gray_value), 0)
    #         painter.setPen(pen)

    #         # verticals
    #         x = left - (left % spacing)
    #         while x <= right:
    #             painter.drawLine(x, top, x, bottom)
    #             x += spacing

    #         # horizontals
    #         y = top - (top % spacing)
    #         while y <= bottom:
    #             painter.drawLine(left, y, right, y)
    #             y += spacing

    #     painter.restore()


    # ───────────────────────────────────── Grid helpers ────────────────────
    def _raw_increment(self, level):          # unchanged
        return self._increments[self._settings.unit][level]

    def get_grid_spacing(self, level: int) -> float:
        increment = self._increments[self._settings.unit][level]
        # tell UnitStr that `increment` is in the current unit:
        return UnitStr(increment,
                             unit=self._settings.unit,
                             dpi=self._settings.dpi).px

    # ───────────────────────────────────── Snap API ────────────────────────
    @Slot(bool)
    def setSnapEnabled(self, enabled: bool):
        self._snap = bool(enabled)

    def isSnapEnabled(self) -> bool:
        return self._snap

    def snap_to_grid(self, pos: QPointF, level: int = 3) -> QPointF:
        if not self._snap:
            return pos
        spacing = self.get_grid_spacing(level)
        return QPointF(
            round(pos.x() / spacing) * spacing,
            round(pos.y() / spacing) * spacing,
        )                  # trigger repaint

    # ───────────────────────────────────── Settings reaction ───────────────
    @Slot(str)
    def _on_unit_changed(self, _new_unit):
        self.prepareGeometryChange()
        self.update()
