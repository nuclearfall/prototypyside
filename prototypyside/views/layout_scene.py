from PySide6.QtWidgets import (
    QGraphicsScene, QGraphicsItem, QGraphicsSceneMouseEvent, QGraphicsSceneDragDropEvent,
    QGraphicsRectItem
)
from PySide6.QtCore import Slot, Qt, QSizeF, QRectF, QPointF, Signal
from PySide6.QtGui import QColor, QPen, QPainter, QBrush, QPixmap, QTransform

# Import your existing DesignerGraphicsView
from prototypyside.views.layout_view import LayoutView
# Import the model and view-item class
from prototypyside.models.layout_template import LayoutTemplate
#from prototypyside.views.layout_template_item import LayoutTemplateItem
from prototypyside.config import MEASURE_INCREMENT, LIGHTEST_GRAY, DARKEST_GRAY
from prototypyside.utils.unit_converter import parse_dimension

from typing import Optional, TYPE_CHECKING
import math

class LayoutScene(QGraphicsScene):
    """
    A QGraphicsScene tailored for LayoutTemplateItem:
    - Manages a single LayoutTemplateItem
    - Adjusts sceneRect when template changes
    """
    component_dropped = Signal(object, QPointF)
    selectionChanged = Signal()
    def __init__(self, scene_rect, tab, parent=None):
        super().__init__(scene_rect, parent) 
        self.tab = tab 
        self._template = tab.template
        self._scene_rect = scene_rect
        print(f"Template Item boundingRect set to {self._scene_rect}")
        self.setSceneRect(self._scene_rect)
        # self.setBackgroundBrush(QBrush(QColor(100, 100, 255))) # A clear blue, for testing
        # Or even a checkerboard pattern for transparency debugging
        # self.setBackgroundBrush(QBrush(Qt.lightGray, Qt.Dense6Pattern))

    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect)
        self.draw_grid(painter, rect)

    def draw_grid(self, painter, rect):
        print("Draw to grid has been called")
        if not getattr(self.parent(), "show_grid", True):
            return

        unit = self.tab.settings.unit
        levels = sorted(MEASURE_INCREMENT[unit].keys(), reverse=True)
        num_levels = len(levels)

        # Gray from lightest (level 3) to darkest (level 1)
        gray_range = LIGHTEST_GRAY - DARKEST_GRAY

        for i, level in enumerate(levels):
            spacing = self.get_grid_spacing(level)

            gray_value = LIGHTEST_GRAY - int(i * (gray_range / max(1, num_levels - 1)))
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


    def get_grid_spacing(self, level: int) -> int:
        unit = self.tab.settings.unit
        dpi = self.tab.settings.dpi
        base = parse_dimension("1 " + unit, dpi)
        increment = MEASURE_INCREMENT[unit].get(level)
        if increment is None:
            raise ValueError(f"Invalid grid level {level} for unit '{unit}'")
        return int(round(base * increment))

    def snap_to_grid(self, pos: QPointF) -> QPointF:
        if not self.is_snap_to_grid:
            return pos
        spacing = self.get_grid_spacing(level=3)
        x = math.floor(pos.x() / spacing) * spacing
        y = math.floor(pos.y() / spacing) * spacing
        return QPointF(x, y)

    def _on_template_shape_changed(self):
        if not self._template:
            return
        rect = self._template.boundingRect()
        print(f"bounding rect of template item set to: {rect}")
        self.setSceneRect(rect)
        self.update(rect)

    def is_valid_mime_data(self, event: QGraphicsSceneDragDropEvent) -> bool:
        return event.mimeData().hasFormat("application/x-component-pid")

    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent):
        if self.is_valid_mime_data(event):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent):
        if self.is_valid_mime_data(event):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QGraphicsSceneDragDropEvent):
        if self.is_valid_mime_data(event):
            pid = event.mimeData().data("application/x-component-pid").data().decode("utf-8")
            scene_pos = event.scenePos()
            self.tab.registry.get(pid)
            self.component_dropped.emit(pid, scene_pos)
            event.acceptProposedAction()
            print(f"Component pid {pid} successfully dropped.")
        else:
            super().dropEvent(event)
