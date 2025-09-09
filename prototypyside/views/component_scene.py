# component_graphics_scene.py
from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore    import Qt, QPointF, QRectF, Signal, Slot
from PySide6.QtGui     import QTransform, QPen, QColor
from PySide6.QtWidgets import (
    QGraphicsScene, QGraphicsItem, QGraphicsSceneMouseEvent,
    QGraphicsSceneDragDropEvent, QGraphicsRectItem
)

from prototypyside.models.component_element import ComponentElement
from prototypyside.services.undo_commands import ChangePropertyCommand
from prototypyside.utils.graphics_item_helpers import is_movable
from prototypyside.utils.units.unit_str_helpers import geometry_with_px_pos
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.services.proto_class import ProtoClass


if TYPE_CHECKING:
    from prototypyside.views.overlays.incremental_grid import IncrementalGrid
    from prototypyside.views.overlays.print_lines import PrintLines

pc = ProtoClass
any_el_type = (pc.CE, pc.TE, pc.IE, pc.VE)

# -------------------------------------------------------------------------
# Scene
# -------------------------------------------------------------------------
class ComponentScene(QGraphicsScene):
    """Scene that hosts one template (background) + grid + user items."""
    # signals used elsewhere in your app
    item_dropped  = Signal(ProtoClass, QPointF)
    item_cloned   = Signal(ComponentElement, UnitStrGeometry)
    create_item_with_dims = Signal(ProtoClass, object)
    creation_cancelled = Signal()
    selectionChanged = Signal()
    selectionChangedEx = Signal()

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


        self.inc_grid = grid
        self.template.template_changed.connect(self._on_template_rect_changed)
        self.sync_scene_rect()
        # internal drag / resize bookkeeping
        self._dup_active: bool = False
        self._dup_source: ComponentElement | None = None
        self._dup_preview: ComponentElement | None = None
        self._dup_offset: QPointF | None = None
        # self._dragging_item       = None
        # self._dragging_start_pos  = None
        # self._drag_offset         = None
        self._creation_state: str = 'idle'
        self._creation_prefix: str | None = None
        self._creation_start: QPointF | None = None
        self._preview_item: QGraphicsRectItem | None = None
        self.setBackgroundBrush(Qt.lightGray)
        self.alt_drag_original_item = None
        self._dup_geom = None

    # ---------- Public API ----------
    def select_exclusive(self, item: QGraphicsItem | None):
        self.clearSelection()
        if item is not None:
            item.setSelected(True)

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

    # @Slot(object, object, object)
    # def on_item_resize_finished(self, item, new_geometry, old_geometry):
    #     """Creates an undo command when an item signals that its resize is complete."""
    #     self.item_resized.emit(item, "geometry", new_geometry, old_geometry)

    # Public helper for FSM / tools
    def snap_to_grid(self, pos: QPointF, level: int = 4) -> QPointF:
        return self.inc_grid.snap_to_grid(pos, level)

    # ─────────────────────────── helpers / utils ──────────────────────────
    def sync_scene_rect(self):
        """Make the scene rect exactly match the template’s and real content bounds."""
        # Start with the template's own bounding rect (which should already
        # account for include_bleed if your template's boundingRect does).
        rect = self.template.boundingRect()

        # Collect only content items (skip grid, overlays, helpers, hidden items)
        for item in self.items():
            if not item.isVisible():
                continue
            if item is self.inc_grid:
                continue
            # If you have other overlays like page outlines or bleed visuals, skip them too:
            if getattr(item, "_is_overlay", False) or item.data(0) == "overlay":
                continue
            rect = rect.united(item.sceneBoundingRect())

        # Only react if the rect actually changes
        if rect != self.sceneRect():
            # If your grid's boundingRect depends on sceneRect, notify it
            if getattr(self, "inc_grid", None) is not None:
                self.inc_grid.prepareGeometryChange()
            self.setSceneRect(rect)
            if getattr(self, "inc_grid", None) is not None:
                self.inc_grid.update()

    @Slot()
    def _on_template_rect_changed(self):
        """Keep scene and grid in sync when the template is resized."""
        self.sync_scene_rect()
        self.inc_grid.prepareGeometryChange()
        self.inc_grid.update()

    # ───────────────────────────── mouse events ───────────────────────────
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        pos = event.scenePos()
        item = self.itemAt(pos, QTransform())

        # Shift-click toggle keeps existing behavior
        if item and (event.modifiers() & Qt.ShiftModifier):
            item.setSelected(not item.isSelected())
            event.accept()
            return

        # Alt-drag duplication (only when pressed over a ComponentElement)
        is_component = pc.isproto(item, any_el_type)
        if (event.modifiers() & Qt.AltModifier) and is_component:
            if hasattr(self, "select_exclusive"):
                self.select_exclusive(item)
            self._begin_alt_dup(item, pos)
            self.alt_drag_original_item = item
            event.accept()
            return

        # --- Creation logic ---
        has_selection = bool(self.selectedItems())
        over_selectable = self._clicked_over_selectable(pos)  # see helper below


        should_begin_creation = (
            event.button() == Qt.LeftButton
            and self._creation_state == "armed"
            and not has_selection
            and not over_selectable
            and not (event.modifiers() & (Qt.ShiftModifier | Qt.AltModifier))
        )

        if should_begin_creation:
            self._creation_state = "dragging"
            self._creation_start = pos
            # If you show a preview rect, initialize it here:
            event.accept()
            return

        # Fall back to default handling
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self._dup_active:
            self._update_alt_dup(event.scenePos())
            event.accept()
            return

        if self._creation_state == 'dragging' and self._creation_start is not None:
            current = self.snap_to_grid(event.scenePos()) if hasattr(self, "snap_to_grid") else event.scenePos()
            self._ensure_preview_item()
            self._update_preview(self._creation_start, current)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        # Finish alt-dup preview
        if self._dup_active:
            commit = (event.button() == Qt.LeftButton)
            scene_pos = event.scenePos()
            self._end_alt_dup(event.scenePos(), commit)
            event.accept()
            return

        # --- NEW: release to create element (Step 6) ---
        if self._creation_state == 'dragging' and self._creation_start is not None and event.button() == Qt.LeftButton:
            end  = self.snap_to_grid(event.scenePos()) if hasattr(self, "snap_to_grid") else event.scenePos()
            rect = QRectF(self._creation_start, end).normalized()

            if rect.width() >= 1e-6 and rect.height() >= 1e-6:
                # scene is in logical units; build ProtoClass.UG with (0,0,w,h) rect and top-left pos
                geom = ProtoClass.UG.new(
                    rect=QRectF(0, 0, rect.width(), rect.height()),
                    pos=QPointF(rect.x(), rect.y()),
                    unit=self.unit  # your scene already uses logical display units
                )
                prefix = self._creation_prefix or ""
                proto = ProtoClass.from_prefix(prefix)
                if proto:
                    self.create_item_with_dims.emit(proto, geom)
                self._teardown_preview()
                self._creation_state  = 'idle'
                self._creation_prefix = None
                self._creation_start  = None
                if self.views():
                    self.views()[0].unsetCursor()


                event.accept()
                return

        super().mouseReleaseEvent(event)


    def keyPressEvent(self, event):
        if (event.key() == Qt.Key_A) and (event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier)):
            for it in self.items():
                if it.flags() & QGraphicsItem.ItemIsSelectable:
                    it.setSelected(True)
            event.accept(); return
        if event.key() == Qt.Key_Escape:
            self.clearSelection(); event.accept(); return
        super().keyPressEvent(event)

    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent):
        if self._creation_state == 'armed':
            self._cancel_creation_internal()
        if event.mimeData().hasFormat('text/plain'):
            event.acceptProposedAction()
            print(f"Entering the scene")
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasFormat('text/plain'):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasFormat('text/plain'):
            prefix = event.mimeData().text()
            proto = ProtoClass.from_prefix(prefix)
            scene_pos = self.snap_to_grid(event.scenePos())
            event.acceptProposedAction()
            if proto:
                self.item_dropped.emit(proto, scene_pos)
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
    def _begin_alt_dup(self, source: "ComponentElement", mouse_scene_pos: QPointF):
        """Create a non-registered preview clone and start tracking."""
        if self._dup_active:
            return
        # deep clone, but do NOT register
        clone = self.template.registry.clone(source, register=False)
        # stylistic preview: higher Z, semi-transparent, not selectable
        clone.setOpacity(0.6)
        clone.setZValue(9_999)
        clone.setFlag(QGraphicsItem.ItemIsSelectable, False)
        clone.setFlag(QGraphicsItem.ItemIsMovable, False)

        # compute offset so the item sticks under the cursor as you grabbed it
        snap = self.snap_to_grid if hasattr(self, "snap_to_grid") else (lambda p: p)
        snapped_mouse = snap(mouse_scene_pos)
        snapped_item_pos = snap(source.pos())
        self._dup_offset = snapped_mouse - snapped_item_pos
        # place at the current item position to start
        clone.geometry = geometry_with_px_pos(clone.geometry, snapped_item_pos)
        self._dup_preview = clone
        self._dup_geom = clone.geometry
        # add into the scene but NOT into any registry
        self.addItem(clone)

        self._dup_source  = source
        self._dup_preview = clone
        self._dup_active  = True

    def _update_alt_dup(self, mouse_scene_pos: QPointF):
        if not self._dup_active or self._dup_preview is None or self._dup_offset is None:
            return
        snap = self.snap_to_grid if hasattr(self, "snap_to_grid") else (lambda p: p)
        snapped_mouse = snap(mouse_scene_pos)
        self._dup_preview.setPos(snapped_mouse - self._dup_offset)
        self._dup_geom = self._dup_preview.geometry

    def _end_alt_dup(self, mouse_scene_pos, commit: bool):
        """Finish preview; optionally emit item_cloned. Always clear preview."""
        new_item = None
        if not self._dup_active:
            return
        try:
            if commit and self._dup_preview is not None:
                snap = self.snap_to_grid if hasattr(self, "snap_to_grid") else (lambda p: p)
                snapped_mouse = snap(mouse_scene_pos)
                self._dup_geom = geometry_with_px_pos(self._dup_geom, snapped_mouse - self._dup_offset)
                # Emit your existing signal that upper layers already use.
                # Your signal signature is: item_cloned(object, UnitStrGeometry)
                # (declared in your scene) :contentReference[oaicite:1]{index=1}
                self.item_cloned.emit(self._dup_source, self._dup_geom)

        finally:
            # Remove the unregistered preview from the scene either way
            if self._dup_preview is not None:
                self.removeItem(self._dup_preview)
            self._dup_active  = False
            self._dup_source  = None
            self._dup_preview = None
            self._dup_offset  = None

    def _clicked_over_selectable(self, scene_pos) -> bool:
        """True if the click is over any selectable, non-preview item."""
        for it in self.items(scene_pos):
            if it is self._preview_item:
                continue
            # If you want to restrict to your element types, keep your pc.isproto check:
            # if not pc.isproto(it, (pc.CE, pc.TE, pc.IE, pc.VE)):
            #     continue
            if it.flags() & QGraphicsItem.ItemIsSelectable:
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