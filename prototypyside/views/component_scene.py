# component_graphics_scene.py
from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore    import Qt, QPointF, QRectF, Signal, Slot
from PySide6.QtGui     import QTransform, QPen, QColor
from PySide6.QtWidgets import (
    QGraphicsScene, QGraphicsItem, QGraphicsSceneMouseEvent,
    QGraphicsSceneDragDropEvent, QGraphicsRectItem
)

from prototypyside.services.undo_commands import MoveElementCommand, ChangePropertyCommand
from prototypyside.utils.graphics_item_helpers import is_movable
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.units.unit_str_helpers import geometry_with_px_pos
from prototypyside.models.component_element import ComponentElement

if TYPE_CHECKING:
    from prototypyside.views.overlays.incremental_grid import IncrementalGrid
    from prototypyside.views.overlays.print_lines import PrintLines
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
    create_item_with_dims = Signal(str, object)
    creation_cancelled = Signal()
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
        self.dpi = settings.dpi
        self.unit = "px"
        self.template  = template          # QGraphicsObject, z = −100

        self.sync_scene_rect()
        self.inc_grid = grid
        self.template.template_changed.connect(self._on_template_rect_changed)

        # internal drag / resize bookkeeping
        self._dragging_item       = None
        self._dragging_start_pos  = None
        self._drag_offset         = None
        self._creation_state: str = 'idle'
        self._creation_prefix: str | None = None
        self._creation_start: QPointF | None = None
        self._preview_item: QGraphicsRectItem | None = None

        self.setBackgroundBrush(Qt.lightGray)

    # ---------- Public API ----------

    @Slot(str)
    def arm_element_creation(self, prefix: str):
        """Step 3) Called by the palette -> scene when a type is chosen."""
        # If we were half-way through a previous attempt, kill it.
        if self._creation_state != 'idle':
            self._cancel_creation_internal()
        self._creation_prefix = prefix
        self._creation_state = 'armed'
        self.views()[0].setCursor(Qt.CrossCursor) if self.views() else None

    @Slot()
    def cancel_armed_creation(self):
        """External cancellation hook (tab changes, tool change, etc.)."""
        self._cancel_creation_internal()

    @Slot(object, object, object)
    def on_item_resize_finished(self, item, new_geometry, old_geometry):
        """Creates an undo command when an item signals that its resize is complete."""
        self.item_resized.emit(item, "geometry", new_geometry, old_geometry)

    # Public helper for FSM / tools
    def snap_to_grid(self, pos: QPointF, level: int = 4) -> QPointF:
        return self.inc_grid.snap_to_grid(pos, level)

    def select_exclusive(self, item: QGraphicsItem):
        """Deselect all items except `item`, and select `item`."""
        for other in self.selectedItems():
            if other is not item:
                other.setSelected(False)
        if item is not None and not item.isSelected():
            item.setSelected(True)
        self.selectionChanged.emit()

    # ─────────────────────────── helpers / utils ──────────────────────────
    def sync_scene_rect(self):
        """Make the scene rect exactly match the template’s bounding rect."""
        r = self.template.geometry.to("px", dpi=self.dpi).rect
        if self.template.include_bleed:
            r = self.template.bleed_rect.px.rect
        print(f"Bleed? {self.template.include_bleed} {r}")
        self.setSceneRect(r)
        self.update()

    @Slot()
    def _on_template_rect_changed(self):
        """Keep scene and grid in sync when the template is resized."""
        self.sync_scene_rect()
        self.inc_grid.prepareGeometryChange()
        self.inc_grid.update()

    # ───────────────────────────── mouse events ───────────────────────────
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        # We need the item under the cursor for both your logic and creation logic
        item = self.itemAt(event.scenePos(), self.views()[0].transform()) if self.views() else None

        # --- NEW: creation path (Step 4a / 4b) ---
        if self._creation_state == 'armed':
            # If the user pressed LMB on blank canvas (no ComponentElement), begin creation
            if event.button() == Qt.LeftButton and (item is None or not isinstance(item, ComponentElement)):
                self._creation_state = 'dragging'
                self._creation_start = self.snap_to_grid(event.scenePos()) if hasattr(self, "snap_to_grid") else event.scenePos()
                self._ensure_preview_item()
                self._update_preview(self._creation_start, self._creation_start)
                event.accept()
                return
            # Otherwise (pressed on an element, or not LMB), cancel creation and fall through to normal behavior
            self._cancel_creation_internal()
            # No return here—let your existing logic (dup/move/select...) run

        # Alt+click duplication
        if event.modifiers() & Qt.AltModifier and is_movable(item):
            # emit both the item to clone and the raw scene‐pos
            self._alt_drag_started = True
            self.item_cloned.emit(item, event.scenePos())
            event.accept()
            return

        if is_movable(item):  # For your item type, using the helper function
            self._dragging_item = item
            self.select_exclusive(self._dragging_item)
            snapped_item_pos_at_press = self.snap_to_grid(item.pos())
            snapped_mouse_press_pos   = self.snap_to_grid(event.scenePos())
            self._drag_offset = snapped_mouse_press_pos - snapped_item_pos_at_press
            self._dragging_start_pos = QPointF(item.x(), item.y())  # Store the item's position before drag
            item.setPos(snapped_item_pos_at_press)                  # Snap item to grid immediately
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        # --- NEW: creation preview dragging ---
        if self._creation_state == 'dragging' and self._creation_start is not None:
            current = self.snap_to_grid(event.scenePos()) if hasattr(self, "snap_to_grid") else event.scenePos()
            self._update_preview(self._creation_start, current)
            event.accept()
            return

        # --- YOUR EXISTING LOGIC (unchanged) ---
        if self._dragging_item:
            snapped_current_mouse_pos = self.snap_to_grid(event.scenePos())
            new_snapped_pos = snapped_current_mouse_pos - self._drag_offset
            self._dragging_item.setPos(new_snapped_pos)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        # --- NEW: release to create element (Step 6) ---
        if self._creation_state == 'dragging' and self._creation_start is not None and event.button() == Qt.LeftButton:
            end  = self.snap_to_grid(event.scenePos()) if hasattr(self, "snap_to_grid") else event.scenePos()
            rect = QRectF(self._creation_start, end).normalized()

            if rect.width() >= 1e-6 and rect.height() >= 1e-6:
                # scene is in logical units; build UnitStrGeometry with (0,0,w,h) rect and top-left pos
                geom = UnitStrGeometry(
                    rect=QRectF(0, 0, rect.width(), rect.height()),
                    pos=QPointF(rect.x(), rect.y()),
                    unit=self.unit  # your scene already uses logical display units
                )
                prefix = self._creation_prefix or ""
                self._teardown_preview()
                self._creation_state  = 'idle'
                self._creation_prefix = None
                self._creation_start  = None
                if self.views():
                    self.views()[0].unsetCursor()
                self.create_item_with_dims.emit(prefix, geom)
                event.accept()
                return
            else:
                # trivial rect: cancel and fall through
                self._cancel_creation_internal()

        # --- YOUR EXISTING LOGIC (unchanged) ---
        # Commit move to undo stack (if needed)
        if self._dragging_item and self._dragging_start_pos is not None:
            geom = self._dragging_item.geometry
            old_pos = self._dragging_start_pos
            old = geometry_with_px_pos(geom, old_pos, dpi=self.dpi)
            new_pos = self._dragging_item.pos()
            new = geometry_with_px_pos(geom, new_pos, dpi=self.dpi)

            if old_pos != new_pos:
                self.item_resized.emit(self._dragging_item, "geometry", new, old)
                    
        self._dragging_item = None
        self._drag_offset = None
        self._dragging_start_pos = None

        super().mouseReleaseEvent(event)

    # Cancel on any other “first action” that isn’t a mouse press.
    def keyPressEvent(self, event):
        if self._creation_state == 'armed':
            self._cancel_creation_internal()
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        if self._creation_state == 'armed':
            self._cancel_creation_internal()
        super().wheelEvent(event)

    def focusOutEvent(self, event):
        if self._creation_state == 'armed':
            self._cancel_creation_internal()
        super().focusOutEvent(event)

    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent):
        if self._creation_state == 'armed':
            self._cancel_creation_internal()
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

    # ---------- Helpers ----------
    def _clicked_on_component_element(self, scene_pos: QPointF) -> bool:
        """True if any existing element is under the click."""
        for it in self.items(scene_pos):
            # Ignore our own temporary preview rect if present
            if it is self._preview_item:
                continue
            # If your background/template rect is a known type, you can skip it here as well.

            # Treat any ComponentElement as “occupied”
            if isinstance(it, _ElementBase):
                return True
        return False

    def _ensure_preview_item(self):
        if self._preview_item is None:
            self._preview_item = QGraphicsRectItem()
            pen = QPen(QColor(50, 120, 255))
            pen.setStyle(Qt.DashLine)
            pen.setCosmetic(True)
            self._preview_item.setPen(pen)
            self._preview_item.setBrush(Qt.NoBrush)
            self._preview_item.setZValue(10_000)
            self.addItem(self._preview_item)

    def _update_preview(self, a: QPointF, b: QPointF):
        if self._preview_item:
            self._preview_item.setRect(QRectF(a, b).normalized())

    def _teardown_preview(self):
        if self._preview_item:
            self.removeItem(self._preview_item)
            self._preview_item = None

    def _cancel_creation_internal(self):
        self._teardown_preview()
        self._creation_state  = 'idle'
        self._creation_prefix = None
        self._creation_start  = None
        self.creation_cancelled.emit()
        if self.views():
            self.views()[0].unsetCursor()