# component_graphics_scene.py
from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore    import Qt, QPointF, QRectF, Signal, Slot
from PySide6.QtGui     import QTransform
from PySide6.QtWidgets import (
    QGraphicsScene, QGraphicsItem, QGraphicsSceneMouseEvent,
    QGraphicsSceneDragDropEvent
)


from prototypyside.services.undo_commands import MoveElementCommand, ChangeItemPropertyCommand
from prototypyside.utils.graphics_item_helpers import is_movable
from prototypyside.utils.ustr_helpers import geometry_with_px_pos
from prototypyside.models.component_elements import ComponentElement

if TYPE_CHECKING:
    from prototypyside.utils.incremental_grid import IncrementalGrid
    from prototypyside.views.component_tab import ComponentTab  
    from prototypyside.models.component_template import ComponentTemplate

# -------------------------------------------------------------------------
# Scene
# -------------------------------------------------------------------------
class ComponentScene(QGraphicsScene):
    """Scene that hosts one template (background) + grid + user items."""
    # signals used elsewhere in your app
    item_dropped  = Signal(QPointF, str)
    item_cloned   = Signal(ComponentElement, QPointF)
    item_moved    = Signal()
    item_resized  = Signal(object, str, object, object)
    selectionChanged = Signal()

    # ──────────────────────────────── init ────────────────────────────────
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
        #self.tab          = tab
        self.template  = template          # QGraphicsObject, z = −100

        # 1️⃣  scene rect == template rect
        self._sync_scene_rect()

        # 2️⃣  add template + grid
        self.addItem(self.template)

        self.inc_grid = grid

        # React to template-size changes
        if hasattr(self.template, "template_refresh"):
            self.template.template_refresh.connect(self._on_template_rect_changed)

        # internal drag / resize bookkeeping
        self._resizing            = False
        self._dragging_item       = None
        self._dragging_start_pos  = None
        self._drag_offset         = None
        self.resize_handle        = None
        self.resizing_item     = None
        self.resize_start_geom    = None
        self.resize_handle_type   = None

        self.setBackgroundBrush(Qt.lightGray)

    # ─────────────────────────── helpers / utils ──────────────────────────
    def _sync_scene_rect(self):
        """Make the scene rect exactly match the template’s bounding rect."""
        r = self.template.geometry.to("px").rect
        self.setSceneRect(r)

    @Slot()
    def _on_template_rect_changed(self, _pid=None):
        """Keep scene and grid in sync when the template is resized."""
        self._sync_scene_rect()
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
    # ───────────────────────────── mouse events ───────────────────────────
    # (unchanged except calls to self.snap_to_grid keep working)
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        item = self.itemAt(event.scenePos(), self.views()[0].transform())

        if hasattr(item, 'is_handle') and item.is_handle:  # Your ResizeHandle flag
            print("Entering resize event")
            self._resizing = True
            self.resize_handle = item
            self.resizing_item = item.parentItem()
            # Save local position and rect at drag start (not sceneBoundingRect)
            self.resize_start_item_geometry = self.resizing_item.geometry
            # self.resize_start_item_rect = self.resizing_item.geometry.rect
            event.accept()
            return

        # Alt+click duplication
        if event.modifiers() & Qt.AltModifier and is_movable(item):
            # emit both the item to clone and the raw scene‐pos
            self._alt_drag_started = True
            print(f"Item: {item}, event: {event} and scenePos {event.scenePos()}")
            self.item_cloned.emit(item, event.scenePos())
            event.accept()
            return

        if is_movable(item):  # For your item type, using the helper function
            self._dragging_item = item
            self.select_exclusive(self._dragging_item)

            # Calculate the offset from the snapped *item's top-left corner* to the snapped *mouse press position*.
            # The item's position (pos()) is relative to its parent, which for top-level items is the scene's origin (0,0).
            # So, item.pos() is already in scene coordinates for top-level items.
            print(f"Is there any item? {item}")
            print(f"Snap position? {item.pos()}")
            snapped_item_pos_at_press = self.snap_to_grid(item.pos())
            snapped_mouse_press_pos = self.snap_to_grid(event.scenePos())
            self._drag_offset = snapped_mouse_press_pos - snapped_item_pos_at_press
            print (f"On click, snapped item at press: {snapped_item_pos_at_press}, snapped mouse press pos {snapped_mouse_press_pos}, and drag offset {self._drag_offset}")
            self._dragging_start_pos = QPointF(item.x(), item.y()) # Store the item's position before drag
            item.setPos(snapped_item_pos_at_press) # Snap item to grid immediately
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self._resizing and self.resizing_item:
            # Snap the current mouse position to the grid!
            snapped_scene_pos = self.snap_to_grid(event.scenePos())
            starting_scene_pos = self.resizing_item.mapToScene(self.resize_handle.pos())
            delta_scene = snapped_scene_pos - starting_scene_pos
            scene_rect = self.resizing_item.mapRectToScene(self.resizing_item.geometry.px.rect)
            self.resizing_item.resize_from_handle(
                self.resize_handle.handle_type,
                delta_scene,
                scene_rect
            )
            event.accept()
            return

        if self._dragging_item:
            # Calculate the new snapped position for the item based on the snapped mouse position
            # and the stored snapped offset.
            snapped_current_mouse_pos = self.snap_to_grid(event.scenePos())
            print(f"Current drag offset =  {self._drag_offset}")
            new_snapped_pos = snapped_current_mouse_pos - self._drag_offset
            self._dragging_item.setPos(new_snapped_pos)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        # Commit move to undo stack (if needed)
        if self._dragging_item and self._dragging_start_pos is not None:
            geom = self._dragging_item.geometry
            old_pos = self._dragging_start_pos
            old = geometry_with_px_pos(geom, old_pos)
            new_pos = self._dragging_item.pos()
            new = geometry_with_px_pos(geom, new_pos)

            if old_pos != new_pos:
                self.item_resized.emit(self._dragging_item, "geometry", new, old)
                
        elif self._resizing and self.resizing_item and self.resize_start_item_geometry:
            # The new geometry is the current geometry of the item after resizing
            new = self.resizing_item.geometry
            old = self.resizing_item.geometry = self.resize_start_item_geometry
            # The old geometry was saved when the mouse press began
            # Create the command with the CORRECT new_geometry and old_geometry order
            self.item_resized.emit(self.resizing_item, "geometry", new, old)


        # Reset state
        self._resizing = False
        self.resize_handle = None
        self.resizing_item = None
        self.resize_start_item_geometry = None
        self.resize_start_item_rect = None
        self._dragging_item = None
        self._drag_offset = None
        self._dragging_start_pos = None

        super().mouseReleaseEvent(event)


    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasFormat('text/plain'):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasFormat('text/plain'):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasFormat('text/plain'):
            item_type = event.mimeData().text()
            scene_pos = self.snap_to_grid(event.scenePos())
            self.item_dropped.emit(scene_pos, item_type)
            event.acceptProposedAction()
        elif event.mimeData().hasUrls():
            # Let the item at the drop location handle the event
            item = self.itemAt(event.scenePos(), QTransform())
            if item and item.flags() & QGraphicsItem.ItemIsSelectable:
                # Forward the event manually to the item
                item.dropEvent(event)
            else:
                super().dropEvent(event)
        else:
            super().dropEvent(event)

# from PySide6.QtWidgets import (
#     QGraphicsScene, QGraphicsItem, QGraphicsSceneMouseEvent, QGraphicsSceneDragDropEvent,
#     QGraphicsRectItem
# )
# from PySide6.QtCore import Qt, QPointF, QRectF, Signal, Slot
# from PySide6.QtGui import QColor, QPen, QPainter, QPixmap, QTransform

# # from prototypyside.config import MEASURE_INCREMENT, LIGHTEST_GRAY, DARKEST_GRAY
# from prototypyside.utils.unit_str import UnitStr
# from prototypyside.utils.unit_str_geometry import UnitStrGeometry
# from prototypyside.utils.graphics_item_helpers import is_movable
# from prototypyside.views.graphics_items import ResizeHandle
# from prototypyside.services.undo_commands import MoveElementCommand, ChangeItemPropertyCommand, ResizeAndMoveElementCommand

# from typing import Optional, TYPE_CHECKING
# import math

# from prototypyside.utils.qt_helpers import list_to_qrectf
# if TYPE_CHECKING:
#     from prototypyside.views.main_window import MainDesignerWindow
#     from prototypyside.models.component_template import ComponentTemplate
#     from prototypyside.models.component_elements import ComponentElement
# else:
#     MainDesignerWindow = object
#     ComponentTemplate = object
#     ComponentElement = object


# class ComponentGraphicsScene(QGraphicsScene):
#     item_dropped = Signal(QPointF, str)
#     item_cloned = Signal(ComponentElement, QPointF)
#     item_moved = Signal()
#     item_resized = Signal()
#     selectionChanged = Signal()

#     def __init__(self, settings, parent, tab):
#         super().__init__(parent)
#         self.tab = tab
#         self.template = tab.template
#         self._template_width_px = int(scene_rect.width())
#         self._template_height_px = int(scene_rect.height())
#         self.setBackgroundBrush(QColor(240, 240, 240))
#         self.dpi = self.tab.template.dpi
#         self.display_unit = self.tab.settings.display_unit
#         self._resizing = False
#         self._dragging_item = None
#         self.resize_handle = None
#         self.resizing_item = None
#         self.resize_start_item_geometry = None
#         self.resize_start_item_rect = None
#         self._drag_offset = None
#         self._dragging_start_pos = None
#         self.resize_handle_type = None
#         self.is_snap_to_grid = True
#         self.show_grid = True

#         self.selected_item: Optional['ComponentElement'] = None
#         self._max_z_value = 0
#         self.connecting_line: Optional[QGraphicsRectItem] = None
#         self.duplicate_item = None

#         self.setSceneRect(0, 0, self._template_width_px, self._template_height_px)

#     def scene_from_template_dimensions(self, width_px: int, height_px: int):
#         self._template_width_px = width_px
#         self._template_height_px = height_px
#         new_rect = QRectF(0, 0, width_px, height_px)
#         self.setSceneRect(new_rect)
#         self.invalidate(new_rect, QGraphicsScene.BackgroundLayer)
#         self.update()

#     # def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
#     #     painter.save()
#     #     painter.setRenderHint(QPainter.Antialiasing)

#     #     # 1. Template (fills the background)
#     #     if not self._template.isNull():
#     #         painter.drawPixmap(rect, self._template,
#     #                            self._template.rect())  # scaled-to-fit

#     #     # 2. Grid over the template
#     #     if self._show_grid and self._grid_spacing > 0:
#     #         pen = QPen(QColor(0, 0, 0, 50), 0)       # cosmetic, semi-transparent
#     #         painter.setPen(pen)

#     #         step = self._grid_spacing
#     #         left   = int(rect.left())  - (int(rect.left())  % step)
#     #         top    = int(rect.top())   - (int(rect.top())   % step)
#     #         right  = int(rect.right())
#     #         bottom = int(rect.bottom())

#     #         # vertical lines
#     #         x = left
#     #         while x <= right:
#     #             painter.drawLine(x, top, x, bottom)
#     #             x += step

#     #         # horizontal lines
#     #         y = top
#     #         while y <= bottom:
#     #             painter.drawLine(left, y, right, y)
#     #             y += step

#     #     painter.restore()



    # def get_grid_spacing(self, level: int) -> float:
    #     increment = MEASURE_INCREMENT[self.display_unit][level]
    #     # tell UnitStr that `increment` is in the current unit:
    #     spacing_px = UnitStr(increment,
    #                          unit=self.display_unit,
    #                          dpi=self.dpi) \
    #                 .to("px", dpi=self.dpi)
    #     return spacing_px

#     # def snap_to_grid(self, pos: QPointF) -> QPointF:
#     #     if self.is_snap_to_grid:
#     #         spacing = self.get_grid_spacing(level=3)
#     #         x = round(pos.x() / spacing) * spacing
#     #         y = round(pos.y() / spacing) * spacing
#     #         return QPointF(x, y)
#     #     return pos

#     # def apply_snap(self, pos: QPointF, grid_size: float = 10.0) -> QPointF:
#     #     return self.snap_to_grid(pos, grid_size)




#     def get_selected_item(self) -> Optional['ComponentElement']:
#         """
#         Returns the first selected ComponentElement in the scene, if any.
#         """
#         selected_items = self.selectedItems()
#         # Filter for ComponentElement type, assuming it's the primary interactive item
#         for item in selected_items:
#             if isinstance(item, ComponentElement):
#                 return item
#         return None



#     @Slot(str)
#     def on_unit_change(self, unit: str):
#         """
#         Called when the user switches display units.
#         Updates anything in this scene that depends on `self.display_unit`,
#         then forces a redraw of the background (grid).
#         """
#         self.display_unit = unit
#         # force the background (and grid) to repaint
#         self.invalidate(self.sceneRect(), QGraphicsScene.BackgroundLayer)