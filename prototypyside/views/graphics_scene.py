from PySide6.QtWidgets import (
    QGraphicsScene, QGraphicsItem, QGraphicsSceneMouseEvent, QGraphicsSceneDragDropEvent,
    QGraphicsRectItem
)
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QColor, QPen, QPainter, QPixmap, QTransform

from prototypyside.config import MEASURE_INCREMENT, LIGHTEST_GRAY, DARKEST_GRAY
from prototypyside.utils.unit_converter import parse_dimension
from prototypyside.utils.unit_str import UnitStr
from prototypyside.utils.graphics_item_helpers import is_movable
from prototypyside.views.graphics_items import ResizeHandle
from prototypyside.services.undo_commands import MoveElementCommand, ResizeElementCommand, ResizeAndMoveElementCommand

from typing import Optional, TYPE_CHECKING
import math

from prototypyside.utils.qt_helpers import list_to_qrectf
if TYPE_CHECKING:
    from prototypyside.views.main_window import MainDesignerWindow
    from prototypyside.models.component_template import ComponentTemplate
    from prototypyside.models.component_elements import ComponentElement
else:
    MainDesignerWindow = object
    ComponentTemplate = object
    ComponentElement = object


class ComponentGraphicsScene(QGraphicsScene):
    element_dropped = Signal(QPointF, str)
    element_cloned = Signal(ComponentElement, QPointF)
    element_moved = Signal()
    element_resized = Signal()
    selectionChanged = Signal()

    def __init__(self, scene_rect: QRectF, parent, tab):
        super().__init__(scene_rect, parent)
        self.tab = tab
        self._template_width_px = int(scene_rect.width())
        self._template_height_px = int(scene_rect.height())
        self.setBackgroundBrush(QColor(240, 240, 240))

        self._resizing = False
        self._dragging_item = None
        self.resize_handle = None
        self.resizing_element = None
        self.resize_start_item_pos = None
        self.resize_start_item_rect = None
        self._drag_offset = None
        self._dragging_start_pos = None
        self.resize_handle_type = None
        self.is_snap_to_grid = True

        self.selected_item: Optional['ComponentElement'] = None
        self._max_z_value = 0
        self.connecting_line: Optional[QGraphicsRectItem] = None
        self.duplicate_element = None

        self.setSceneRect(0, 0, self._template_width_px, self._template_height_px)

    def scene_from_template_dimensions(self, width_px: int, height_px: int):
        self._template_width_px = width_px
        self._template_height_px = height_px
        new_rect = QRectF(0, 0, width_px, height_px)
        self.setSceneRect(new_rect)
        self.invalidate(new_rect, QGraphicsScene.BackgroundLayer)
        self.update()

    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect)
        template_rect = QRectF(0, 0, self._template_width_px, self._template_height_px)

        main_window: 'MainDesignerWindow' = self.parent()
        if main_window and hasattr(main_window, 'template') and main_window.template:
            template: 'ComponentTemplate' = main_window.template
            if template.background_image_path:
                bg_pixmap = QPixmap(template.background_image_path)
                if not bg_pixmap.isNull():
                    scaled_pixmap = bg_pixmap.scaled(
                        template_rect.size().toSize(),
                        Qt.IgnoreAspectRatio,
                        Qt.SmoothTransformation
                    )
                    painter.drawPixmap(template_rect.topLeft(), scaled_pixmap)
                else:
                    painter.setBrush(QColor(255, 255, 255))
                    painter.setPen(Qt.NoPen)
                    painter.drawRect(template_rect)
            else:
                painter.setBrush(QColor(255, 255, 255))
                painter.setPen(Qt.NoPen)
                painter.drawRect(template_rect)
        else:
            painter.setBrush(QColor(255, 255, 255))
            painter.setPen(Qt.NoPen)
            painter.drawRect(template_rect)

        self.draw_grid(painter, rect)

        border_pen = QPen(Qt.black, 2)
        painter.setPen(border_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(template_rect)

    def draw_grid(self, painter, rect):
        if not getattr(self.parent(), "show_grid", True):
            return

        # Always use canonical unit string (not UnitStr instance)
        unit = self.tab.settings.unit
        dpi = self.tab.settings.dpi
        levels = sorted(MEASURE_INCREMENT[unit].keys(), reverse=True)
        num_levels = len(levels)

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

    def get_grid_spacing(self, level: int) -> float:
        unit = self.tab.settings.unit
        dpi = self.tab.settings.dpi
        increment = MEASURE_INCREMENT[unit].get(level)
        if increment is None:
            raise ValueError(f"Invalid grid level {level} for unit '{unit}'")
        # This is the physical size of the grid interval in unit, convert to px:
        spacing_px = UnitStr(increment, unit=unit, dpi=dpi).to("px", dpi=dpi)
        return spacing_px

    def snap_to_grid(self, pos: QPointF) -> QPointF:
        if self.is_snap_to_grid:
            spacing = self.get_grid_spacing(level=3)
            x = round(pos.x() / spacing) * spacing
            y = round(pos.y() / spacing) * spacing
            return QPointF(x, y)
        return pos

    def apply_snap(self, pos: QPointF, grid_size: float = 10.0) -> QPointF:
        return self.snap_to_grid(pos, grid_size)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        item = self.itemAt(event.scenePos(), self.views()[0].transform())

        if hasattr(item, 'is_handle') and item.is_handle:  # Your ResizeHandle flag
            print("Entering resize event")
            self._resizing = True
            self.resize_handle = item
            self.resizing_element = item.parentItem()
            # Save local position and rect at drag start (not sceneBoundingRect)
            self.resize_start_item_pos = self.resizing_element.pos()
            self.resize_start_item_rect = self.resizing_element.rect
            event.accept()
            return

        # Alt+click duplication
        if event.modifiers() & Qt.AltModifier and is_movable(item):
            # emit both the item to clone and the raw scene‐pos
            self._alt_drag_started = True
            self.element_cloned.emit(item, event.scenePos())
            event.accept()
            return

        if is_movable(item):  # For your item type, using the helper function
            self._dragging_item = item
            self.select_exclusive(self._dragging_item)

            # Calculate the offset from the snapped *item's top-left corner* to the snapped *mouse press position*.
            # The item's position (pos()) is relative to its parent, which for top-level items is the scene's origin (0,0).
            # So, item.pos() is already in scene coordinates for top-level items.
            snapped_item_pos_at_press = self.snap_to_grid(item.pos())
            snapped_mouse_press_pos = self.snap_to_grid(event.scenePos())
            self._drag_offset = snapped_mouse_press_pos - snapped_item_pos_at_press
            self._dragging_start_pos = QPointF(item.x(), item.y()) # Store the item's position before drag
            item.setPos(snapped_item_pos_at_press) # Snap item to grid immediately
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self._resizing and self.resizing_element:
            # Snap the current mouse position to the grid!
            snapped_scene_pos = self.snap_to_grid(event.scenePos())
            starting_scene_pos = self.resizing_element.mapToScene(self.resize_handle.pos())
            delta_scene = snapped_scene_pos - starting_scene_pos

            scene_rect = self.resizing_element.mapRectToScene(self.resizing_element.rect)

            self.resizing_element.resize_from_handle(
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
            new_snapped_pos = snapped_current_mouse_pos - self._drag_offset
            self._dragging_item.setPos(new_snapped_pos)
            event.accept()
            return

        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        # Commit move to undo stack (if needed)
        if self._dragging_item and self._dragging_start_pos is not None:
            # Use the stored start position (already snapped by mousePressEvent)
            old_pos = self._dragging_start_pos
            new_pos = self._dragging_item.pos() # This should already be snapped due to mouseMoveEvent logic
            command = MoveElementCommand(self._dragging_item, new_pos, old_pos)
            self.tab.undo_stack.push(command)
        elif self._resizing and self.resizing_element and self.resize_start_item_rect is not None:
            old_values = (self.resize_start_item_pos, self.resize_start_item_rect)
            new_values = (self.resizing_element.pos(), self.resizing_element.rect)
            command = ResizeAndMoveElementCommand(
                 self.resizing_element, new_values, old_values)
            self.tab.undo_stack.push(command)
            pass  # Implement your undo/redo integration

        # Reset state
        self._resizing = False
        self.resize_handle = None
        self.resizing_element = None
        self.resize_start_item_pos = None
        self.resize_start_item_rect = None
        self._dragging_item = None
        self._drag_offset = None

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
            element_type = event.mimeData().text()
            scene_pos = self.snap_to_grid(event.scenePos())
            self.element_dropped.emit(scene_pos, element_type)
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


    def get_selected_element(self) -> Optional['ComponentElement']:
        """
        Returns the first selected ComponentElement in the scene, if any.
        """
        selected_items = self.selectedItems()
        # Filter for ComponentElement type, assuming it's the primary interactive item
        for item in selected_items:
            if isinstance(item, ComponentElement):
                return item
        return None

    def select_exclusive(self, element: QGraphicsItem):
        """
        Deselect all items except `element`, and select `element`.
        """
        # Deselect all other items
        for item in self.selectedItems():
            if item is not element:
                item.setSelected(False)
        # Select the desired element (if not already)
        if element is not None and not element.isSelected():
            element.setSelected(True)
        # Emit selectionChanged signal if you want property panel, etc. to update
        self.selectionChanged.emit()

