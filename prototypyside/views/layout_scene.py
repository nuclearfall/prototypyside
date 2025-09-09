from typing import Optional, TYPE_CHECKING
import math

from PySide6.QtWidgets import (
    QGraphicsScene, QGraphicsItem, QGraphicsSceneMouseEvent, QGraphicsSceneDragDropEvent,
    QGraphicsRectItem
)
from PySide6.QtCore import Slot, Qt, QSizeF, QRectF, QPointF, Signal
from PySide6.QtGui import QColor, QPen, QPainter, QBrush, QPixmap, QTransform

from prototypyside.views.layout_view import LayoutView
from prototypyside.config import MEASURE_INCREMENT, LIGHTEST_GRAY, DARKEST_GRAY

if TYPE_CHECKING:
    from prototypyside.views.overlays.incremental_grid import IncrementalGrid
    from prototypyside.models.layout_template import LayoutTemplate


class LayoutScene(QGraphicsScene):
    """
    A QGraphicsScene tailored for LayoutTemplate:
    - Manages a single LayoutTemplateItem
    - Adjusts sceneRect when template changes
    """
    component_dropped = Signal(object, QPointF)

    def __init__(
        self,
        settings,
        *,
        grid: "IncrementalGrid",
        template: "LayoutTemplate",
        parent=None,
    ):
        super().__init__(parent)
        self.settings     = settings
        self._dpi = self.settings.dpi
        self.template  = template  
        self.inc_grid = grid
        self.sync_scene_rect()

    @property     
    def dpi(self):
        return self._dpi

    @dpi.setter
    def dpi(self, new_dpi):
        if new_dpi != self._dpi:
            self._dpi = new_dpi
            self.sync_scene_rect()

    def sync_scene_rect(self):
        """Make the scene rect exactly match the template’s bounding rect."""
        r = self.template.geometry.to("px", dpi=self._dpi).rect
        self.setSceneRect(r)
        self.inc_grid.prepareGeometryChange()
        self.inc_grid.update()
        
    @Slot()
    def _on_template_rect_changed(self):
        """Keep scene and grid in sync when the template is resized."""
        self.sync_scene_rect()
        self.inc_grid.prepareGeometryChange()
        self.inc_grid.update()

    # Public helper for FSM / tools
    def snap_to_grid(self, pos: QPointF, level: int = 3) -> QPointF:
        return self.inc_grid.snap_to_grid(pos, level)

    def select_exclusive(self, item: QGraphicsItem | None):
        blocker = QSignalBlocker(self)   # suppress multiple built-in emissions
        self.clearSelection()
        if item is not None:
            item.setSelected(True)
        del blocker
        self.item_selection_changed.emit()  # your one-shot signal

    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasFormat("application/x-component-pid"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasFormat("application/x-component-pid"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasFormat("application/x-component-pid"):
            pid = event.mimeData().data("application/x-component-pid").data().decode("utf-8")
            scene_pos = event.scenePos()
            self.component_dropped.emit(pid, scene_pos)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def keyPressEvent(self, event):
        if (event.key() == Qt.Key_A) and (event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier)):
            for it in self.items():
                if it.flags() & QGraphicsItem.ItemIsSelectable:
                    it.setSelected(True)
            event.accept(); return
        if event.key() == Qt.Key_Escape:
            self.clearSelection(); event.accept(); return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        item = self.itemAt(event.scenePos(), QTransform())
        if item and (event.modifiers() & Qt.ShiftModifier):
            item.setSelected(not item.isSelected())
            event.accept()
            return
        super().mousePressEvent(event)