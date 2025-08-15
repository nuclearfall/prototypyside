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
    from prototypyside.models.component_template import ComponentTemplate


class LayoutScene(QGraphicsScene):
    """
    A QGraphicsScene tailored for LayoutTemplate:
    - Manages a single LayoutTemplateItem
    - Adjusts sceneRect when template changes
    """
    component_dropped = Signal(object, QPointF)
    selectionChanged = Signal(str)

    def __init__(
        self,
        settings,
        *,
        grid: "IncrementalGrid",
        template: "ComponentTemplate",
        parent=None,
    ):
        super().__init__(parent)
        self.settings     = settings
        self._dpi = self.settings.dpi
        self.template  = template  
        self.inc_grid = grid       
        self._preview_mode = False
        self._pages = []
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

    def select_exclusive(self, item: QGraphicsItem):
        """Deselect all items except `item`, and select `item`."""
        for other in self.selectedItems():
            if other is not item:
                other.setSelected(False)
        if item is not None and not item.isSelected():
            item.setSelected(True)
        self.selectionChanged.emit()

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        item = self.itemAt(event.scenePos(), QTransform())
        if event.button() == Qt.LeftButton:
            if self._preview_mode:
                # Exit preview
                self.clear()
                for i, layout in enumerate(self._pages):
                    layout.setPos(QPointF(0, i * (layout.boundingRect().height() + 50)))
                    self.addItem(layout)
                self._preview_mode = False
                self.tab.view.fitInView(self.sceneRect(), Qt.KeepAspectRatio)
            else:
                if item in self._pages:
                    # Enter preview
                    self.clear()
                    self.addItem(item)
                    item.setPos(QPointF(0, 0))
                    self._preview_mode = True
                    self.setSceneRect(item.boundingRect())
                    self.tab.view.fitInView(self.sceneRect(), Qt.KeepAspectRatio)
        else:
            super().mousePressEvent(event)
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

    def populate_with_clones(self, count: int, base_template, registry):
        self.clear()
        spacing = 50  # vertical gap between pages, in scene units
        y_offset = 0
        self._pages = []
        for i in range(count):
            layout = registry.clone(base_template)
            layout.setPos(QPointF(0, y_offset))
            self.addItem(layout)
            self._pages.append(layout)
            y_offset += layout.boundingRect().height() + spacing
        self.setSceneRect(0, 0, layout.boundingRect().width(), y_offset)

