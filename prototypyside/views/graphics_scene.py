from PySide6.QtWidgets import (
    QGraphicsScene, QGraphicsItem, QGraphicsSceneMouseEvent, QGraphicsSceneDragDropEvent,
    QGraphicsRectItem
)
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QColor, QPen, QPainter, QPixmap, QTransform

from prototypyside.config import MEASURE_INCREMENT
from prototypyside.utils.unit_converter import parse_dimension
from prototypyside.utils.graphics_item_helpers import is_movable
from prototypyside.views.graphics_items import ResizeHandle

from typing import Optional, TYPE_CHECKING
import math

from prototypyside.utils.qt_helpers import list_to_qrectf
if TYPE_CHECKING:
    from prototypyside.views.main_window import MainDesignerWindow
    from prototypyside.models.game_component_template import GameComponentTemplate
    from prototypyside.models.game_component_elements import GameComponentElement
else:
    MainDesignerWindow = object
    GameComponentTemplate = object
    GameComponentElement = object


class GameComponentGraphicsScene(QGraphicsScene):
    element_dropped = Signal(QPointF, str)
    selectionChanged = Signal()

    def __init__(self, scene_rect: QRectF, parent=None, settings=None):
        super().__init__(scene_rect, parent)
        if settings:
            self.settings = settings
        else:
            raise ValueError

        self._template_width_px = int(scene_rect.width())
        self._template_height_px = int(scene_rect.height())
        self.setBackgroundBrush(QColor(240, 240, 240))

        self._alt_drag_duplicate = None
        self._alt_drag_started = False
        self._resizing = False
        self._dragging_item = None
        self._drag_offset = None
        self._was_dragging = False

        self.resize_handle_type = None
        self.resizing_element = None
        self.resize_start_scene_pos = None
        self.resize_start_scene_rect = None
        self.measure_by = "in"
        self.is_snap_to_grid = True

        self.selected_item: Optional['GameComponentElement'] = None
        self._max_z_value = 0
        self.connecting_line: Optional[QGraphicsRectItem] = None
        self._dragging_item = None
        self._drag_offset = None
        self.is_duplicating = False
        self.duplicate_element = None

        self.setSceneRect(0, 0, self._template_width_px, self._template_height_px)

    def set_template_dimensions(self, width_px: int, height_px: int):
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
        if main_window and hasattr(main_window, 'current_template') and main_window.current_template:
            template: 'GameComponentTemplate' = main_window.current_template
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

        unit = self.settings.unit
        dpi = self.settings.dpi
        base = parse_dimension("1 " + unit, dpi)
        spacing = int(round(base * MEASURE_INCREMENT[unit]))

        pen = QPen(QColor(220, 220, 220))
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

    def get_grid_spacing(self) -> int:
        unit = self.settings.unit
        dpi = self.settings.dpi
        base = parse_dimension("1 " + unit, dpi)
        return int(round(base * MEASURE_INCREMENT[unit]))

    def snap_to_grid(self, pos: QPointF) -> QPointF:
        if not self.is_snap_to_grid:
            return pos
        spacing = self.get_grid_spacing()
        x = math.floor(pos.x() / spacing) * spacing
        y = math.floor(pos.y() / spacing) * spacing
        return QPointF(x, y)

    def apply_snap(self, pos: QPointF, grid_size: float = 10.0) -> QPointF:
        return self.snap_to_grid(pos, grid_size)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        item = self.itemAt(event.scenePos(), self.views()[0].transform())

        # Handle resize logic (unchanged)
        if isinstance(item, ResizeHandle):
            self._resizing = True
            self.resize_handle = item
            self.resizing_element = item.parentItem()
            self.resize_start_scene_pos = event.scenePos()
            self.resize_start_scene_rect = self.resizing_element.sceneBoundingRect()
            return

        # Option-key duplication
        if event.modifiers() & Qt.AltModifier and is_movable(item):
            clone = item.clone()
            clone.setPos(item.pos())
            self.addItem(clone)
            self.clearSelection()
            clone.setSelected(True)
            self._dragging_item = clone
            self._drag_offset = event.scenePos() - clone.pos()
        elif is_movable(item):
            self._dragging_item = item
            self._drag_offset = event.scenePos() - item.pos()

        super().mousePressEvent(event)

    def _generate_unique_name(self, template, base_name):
        existing_names = {e.name for e in template.elements}
        if base_name not in existing_names:
            return base_name

        counter = 1
        while f"{base_name}_{counter}" in existing_names:
            counter += 1
        return f"{base_name}_{counter}"

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self._resizing and self.resizing_element:
            delta = event.scenePos() - self.resize_start_scene_pos
            self.resizing_element.resize_from_handle(
                self.resize_handle,
                delta,
                self.resize_start_scene_rect
            )
            return

        elif self._dragging_item:
            if event.modifiers() & Qt.AltModifier and not self._alt_drag_started:
                self._alt_drag_started = True

                if hasattr(self._dragging_item, 'to_dict') and hasattr(self._dragging_item, 'template'):
                    orig_item = self._dragging_item
                    template = orig_item.template

                    element_dict = orig_item.to_dict()
                    element_dict["name"] = self._generate_unique_name(template, element_dict["name"])

                    new_item = type(orig_item).from_dict(element_dict, parent_qobject=template)
                    template.add_element(new_item)

                    new_item.setPos(orig_item.pos() + QPointF(10, 10))  # Offset to visualize the duplication
                    self.clearSelection()
                    new_item.setSelected(True)

                    self._dragging_item = new_item
                    self._was_dragging = True
                    return  # Don't reposition just yet — wait for next move event

            # Regular or post-duplicate dragging
            new_pos = event.scenePos() - self._drag_offset
            if self.is_snap_to_grid:
                new_pos = self.snap_to_grid(new_pos)
            self._dragging_item.setPos(new_pos)
            self._was_dragging = True
            return

        super().mouseMoveEvent(event)



    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        self._dragging_item = None
        self._drag_offset = None
        self._resizing = False
        self.resize_handle = None
        self.resizing_element = None
        self.resize_start_scene_rect = None
        self.resize_start_scene_pos = None
        self._alt_drag_duplicate = None
        self._alt_drag_started = False

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
            scene_pos = event.scenePos()
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


    def get_selected_element(self) -> Optional['GameComponentElement']:
        selected_items = self.selectedItems()
        if selected_items and isinstance(selected_items[0], GameComponentElement):
            self.property_panel.get_all(selected_items[0])
            return selected_items[0]
        return None
