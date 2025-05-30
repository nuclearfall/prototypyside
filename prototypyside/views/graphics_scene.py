# prototypyside/views/graphics_scene.py

from PySide6.QtWidgets import QGraphicsScene, QGraphicsItem, QApplication, QGraphicsSceneMouseEvent, QGraphicsSceneDragDropEvent, QGraphicsRectItem # Ensure QGraphicsRectItem is imported for connecting_line
from PySide6.QtCore import Qt, QPointF, QRectF, Signal # Removed QDataStream, QIODevice as they are not directly used in this file's logic
from PySide6.QtGui import QColor, QPen, QPainter, QPixmap, QTransform # Added QTransform for robust itemAt handling


from prototypyside.config import MEASURE_INCREMENT
from prototypyside.utils.unit_converter import parse_dimension, format_dimension
# For type hinting MainDesignerWindow and GameComponentTemplate
from typing import Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from prototypyside.views.main_window import MainDesignerWindow
    from prototypyside.models.game_component_template import GameComponentTemplate
    from prototypyside.models.game_component_elements import GameComponentElement # Import for type hinting GameComponentElement
else:
    MainDesignerWindow = object
    GameComponentTemplate = object
    GameComponentElement = object # Define GameComponentElement for runtime when TYPE_CHECKING is False


class GameComponentGraphicsScene(QGraphicsScene):
    element_dropped = Signal(QPointF, str) # Signal to emit when an element is dropped on the scene
    selectionChanged = Signal() # Re-added the scene's own selectionChanged signal (Qt provides one, but we often re-emit for consistency)

    def __init__(self, initial_width_px: int = 400, initial_height_px: int = 400, parent=None):
        super().__init__(parent)
        self.setBackgroundBrush(QColor(240, 240, 240)) # Light gray background for the overall scene
        self.measure_by = "in"
        self.is_snap_to_grid = True
        self._template_width_px = initial_width_px
        self._template_height_px = initial_height_px

        self.selected_item: Optional['GameComponentElement'] = None # Tracker for the single selected item
        self._max_z_value = 0 # To manage Z-order for selected items (increment this when item is brought to front)
        self.connecting_line: Optional[QGraphicsRectItem] = None # Placeholder for a potential future feature
        self.drag_offset = None 
        self._dragging_item = None
        # Set the sceneRect immediately with the initial dimensions
        self.setSceneRect(0, 0, self._template_width_px, self._template_height_px)


    def set_template_dimensions(self, width_px: int, height_px: int):
        self._template_width_px = width_px
        self._template_height_px = height_px

        new_rect = QRectF(0, 0, width_px, height_px)
        self.setSceneRect(new_rect)

        # Force update of all items and the background
        self.invalidate(new_rect, QGraphicsScene.BackgroundLayer)
        self.update()

    def drawBackground(self, painter: QPainter, rect: QRectF):
        # Always call the base class implementation first (for the overall background brush)
        super().drawBackground(painter, rect)

        template_rect = QRectF(0, 0, self._template_width_px, self._template_height_px)

        # 1. Draw the background image IF available
        # The parent of the scene is MainDesignerWindow, which holds current_template
        main_window: 'MainDesignerWindow' = self.parent() # Cast to MainDesignerWindow for type hints
        if main_window and hasattr(main_window, 'current_template') and main_window.current_template:
            template: 'GameComponentTemplate' = main_window.current_template
            if template.background_image_path:
                bg_pixmap = QPixmap(template.background_image_path)
                if not bg_pixmap.isNull():
                    # Scale pixmap to fit the entire template area, ignoring aspect ratio to fill
                    scaled_pixmap = bg_pixmap.scaled(
                        template_rect.size().toSize(),
                        Qt.IgnoreAspectRatio,
                        Qt.SmoothTransformation
                    )
                    painter.drawPixmap(template_rect.topLeft(), scaled_pixmap)
                    # If an image is present, we fill the template area with it, no need for solid white
                else:
                    # If image failed to load or path is invalid, fall back to white
                    painter.setBrush(QColor(255, 255, 255)) # White for the template area
                    painter.setPen(Qt.NoPen)
                    painter.drawRect(template_rect)
            else:
                # If no background image path is set, fill the template area with white
                painter.setBrush(QColor(255, 255, 255)) # White for the template area
                painter.setPen(Qt.NoPen)
                painter.drawRect(template_rect)
        else:
            # Fallback if no main_window or template is accessible (shouldn't happen in normal operation)
            painter.setBrush(QColor(255, 255, 255))
            painter.setPen(Qt.NoPen)
            painter.drawRect(template_rect)


        self.draw_grid(painter, rect)

        # 3. Draw the fixed template border in black (on top of everything)
        border_pen = QPen(Qt.black, 2)
        painter.setPen(border_pen)
        painter.setBrush(Qt.NoBrush) # Ensure no fill for the border rect
        painter.drawRect(template_rect) # Draw the border around the template area

    def draw_grid(self, painter, rect):
        if not getattr(self.parent(), "show_grid", True):
            return

        unit = getattr(self.parent(), "current_unit", "in")
        dpi = 72
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

    def snap_to_grid(self, pos: QPointF, grid_size: float = 10.0) -> QPointF:
        if not self.is_snap_to_grid:
            return pos
        x = round(pos.x() / grid_size) * grid_size
        y = round(pos.y() / grid_size) * grid_size
        return QPointF(x, y)

    def apply_snap(self, pos: QPointF, grid_size: float = 10.0) -> QPointF:
        if not self.is_snap_to_grid:
            return pos
        x = round(pos.x() / grid_size) * grid_size
        y = round(pos.y() / grid_size) * grid_size
        return QPointF(x, y)


    # --- REVISED MOUSE EVENT HANDLERS ---

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        super().mouseMoveEvent(event)

        if hasattr(self, '_dragging_item') and self._dragging_item:
            new_pos = event.scenePos() - self._drag_offset
            if self.snap_to_grid:
                new_pos = self.apply_snap(new_pos)
            self._dragging_item.setPos(new_pos)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        # Call super() first to allow Qt's default item selection and drag handling.
        # This is CRITICAL for drag-and-drop from external sources (like your palette).
        super().mousePressEvent(event)

        # After super() has processed, we can apply our single-selection logic.
        if event.button() == Qt.LeftButton:
            # Check what item is under the mouse at the press point.
            # Use self.views()[0].transform() for scene-to-view mapping if views exist,
            # otherwise QTransform() as a fallback for robustness.
            item_at_pos = self.itemAt(event.scenePos(), self.views()[0].transform() if self.views() else QTransform())

            # If the click was on the background (no item hit by itemAt), clear selection.
            # This ensures clicking empty space always deselects items.
            # This is safe here because super().mousePressEvent would have already
            # initiated any drag if an item was clicked.
            if not item_at_pos:
                self.clearSelection() # Deselects all items in the scene
            if item_at_pos and (item_at_pos.flags() & QGraphicsItem.ItemIsMovable):
                self._dragging_item = item_at_pos
                self._drag_offset = event.scenePos() - item_at_pos.pos()
            # Keep track of the GameComponentElement that was pressed, if any.
            # This helps in mouseReleaseEvent to confirm selection after potential drag/move.
            if isinstance(item_at_pos, GameComponentElement):
                self.selected_item = item_at_pos
            else:
                self.selected_item = None


    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        # Always call super() first to finalize any drag/move operations Qt might have handled.
        super().mouseReleaseEvent(event)
        self._dragging_item = None 
        self._drag_offset = None 

        if self.snap_to_grid:
            item = self.get_selected_element()
            if item:
                snapped_pos = self.snap_to_grid(item.pos())
                item.setPos(snapped_pos)

        # After super() completes, and if it was a LeftButton release:
        if event.button() == Qt.LeftButton:
            # Get the current list of selected items in the scene.
            selected_items_in_scene = self.selectedItems()

            if len(selected_items_in_scene) > 1:
                # If multiple items are selected (e.g., from rubber-band selection if enabled),
                # enforce single selection by picking the first GameComponentElement found
                # and deselecting all others.
                first_game_component_selected = None
                for item in selected_items_in_scene:
                    if isinstance(item, GameComponentElement):
                        first_game_component_selected = item
                        break
                
                if first_game_component_selected:
                    # Temporarily block signals from the item to prevent recursion during clear/set.
                    # This specific part is generally handled by the item's `itemChange`
                    # but explicit blocking can prevent issues if item selection changes are complex.
                    # However, QGraphicsScene.clearSelection() and setSelected() are robust.
                    self.clearSelection() # Clear all items
                    first_game_component_selected.setSelected(True) # Re-select just the desired one
                    self.selected_item = first_game_component_selected
                else: # Only non-GameComponentElement items were selected, or nothing after filter
                    self.clearSelection()
                    self.selected_item = None
            elif len(selected_items_in_scene) == 1 and isinstance(selected_items_in_scene[0], GameComponentElement):
                # Exactly one GameComponentElement is selected. Update our internal tracker.
                self.selected_item = selected_items_in_scene[0]
            else:
                # No GameComponentElement is selected (either empty scene, or only non-GameComponentElement items selected).
                # Ensure our internal tracker is cleared if no relevant item is selected.
                self.selected_item = None
                # If nothing was selected by Qt's default mechanisms after a click on background,
                # ensure explicit clear (redundant if mousePressEvent already cleared, but safe).
                if not selected_items_in_scene: # This case means a click on empty space with no previous selection.
                    self.clearSelection() # Final assurance that nothing is selected


    # --- DRAG AND DROP EVENT HANDLERS ---
    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent):
        # Check if the mime data contains plain text, which we expect from the palette
        if event.mimeData().hasFormat('text/plain'):
            event.acceptProposedAction() # Indicate that a drop is possible
        else:
            # If not our expected format, let the base class handle it (or ignore)
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent):
        # As the drag moves, continually accept the proposed action to show feedback (e.g., green plus cursor)
        if event.mimeData().hasFormat('text/plain'):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QGraphicsSceneDragDropEvent):
        # When the item is dropped, process it
        if event.mimeData().hasFormat('text/plain'):
            element_type = event.mimeData().text()
            scene_pos = event.scenePos() # Get the drop position in scene coordinates
            self.element_dropped.emit(scene_pos, element_type) # Emit our custom signal
            event.acceptProposedAction() # Confirm that the drop was handled
        else:
            super().dropEvent(event) # Fallback for other drop types

    def get_selected_element(self) -> Optional['GameComponentElement']:
        """Returns the currently selected GameComponentElement, or None if no such element is selected."""
        selected_items = self.selectedItems()
        print(selected_items)
        # Ensure only a single GameComponentElement is considered selected for simplicity.
        # The mouseReleaseEvent should mostly enforce this.
        if selected_items and isinstance(selected_items[0], GameComponentElement):
            return selected_items[0]
        return None
