from typing import List, Any
from PySide6.QtGui import QUndoCommand
from PySide6.QtCore import QPointF, QRectF

# from prototypyside.models.component_template import ComponentTemplate
from prototypyside.utils.units.unit_str_helpers import geometry_with_px_rect, geometry_with_px_pos
from prototypyside.utils.unit_converter import pos_to_unit_str
from prototypyside.services.proto_class import ProtoClass

class BatchPropertyChangeCommand(QUndoCommand):
    """
    Undoable command that changes one property across multiple items.

    - items: List of model/graphics objects
    - prop:  Property/attribute name (e.g., "geometry", "rotation", "color")
    - new_value: The value to apply to each item
    - old_values: Old values aligned with 'items' (len(old_values) == len(items))
    """
    def __init__(
        self,
        items: List[object],
        prop: str,
        new_value: Any,
        old_values: List[Any],
        text: "Change Property for Selected Items"
    ):
        super().__init__(text or f'Change "{prop}" for {len(items)} item(s)')
        assert len(items) == len(old_values), "items and old_values must be same length"
        self._items = items
        self._prop = prop
        self._new = new_value
        self._olds = old_values

    def redo(self):
        for it in self._items:
            setattr(it, self._prop, value)

    def undo(self):
        for it, old in zip(self._items, self._olds):
            setattr(it, old)

class MoveSelectionCommand(QUndoCommand):
    def __init__(self, items, starts, ends, text="Move Items"):
        super().__init__(text)
        # Keep strong refs so items don’t get GC’d during undo/redo history
        self._items = list(items)
        self._starts = starts  # dict[item, QPointF]
        self._ends = ends      # dict[item, QPointF]

    def undo(self):
        for it in self._items:
            it.geometry = geometry_with_px_pos(it.geometry, self._starts[it])
            it.setPos(self._starts[it])

    def redo(self):
        for it in self._items:
            it.geometry = geometry_with_px_pos(it.geometry, self._ends[it])
            it.setPos(self._ends[it])

class AddSlotCommand(QUndoCommand):
    def __init__(self, registry, template):
        self.template = template
        self.registry = registry
        self.item = None

    def undo(self):
        self.registry.deregister(self.item.pid)

    def redo(self):
        if item is None:
            self.item = self.registry.create(ProtoClass.LS)
        else:
            self.registry.reinsert(self.item)

class AddElementCommand(QUndoCommand):
    def __init__(self, proto, tab, geometry=None, description="Add Element"):
        super().__init__(description)
        self.proto = proto
        self.registry = tab.registry
        self.tab = tab
        self.geometry = geometry

        self.item = None

    def redo(self):
        if self.item is None:
            # Create a brand-new element. IMPORTANT: do NOT pass tpid for fresh elements.
            self.item = self.registry.create(
                proto=self.proto,
                geometry=self.geometry,
                parent=self.tab.template
            )
            # Add to model and scene
            self.tab.template.add_item(self.item)
            # self.item.setParentItem(self.tab.template)

        elif self.item is not None and self.tab.registry.is_orphan(self.item.pid):
            # Reinsert an orphan on redo
            self.tab.registry.reinsert(self.item.pid)

        # Ensure it is in the scene
        if self.item.scene() is None:
            self.tab.scene.addItem(self.item)

        scene_pos = self.item.pos()
        # Snap to grid if enabled (in px, so reconvert)
        if self.tab._snap_grid:
            self.item.setPos(self.tab.scene.snap_to_grid(scene_pos))

        # For QGraphicsItem, setPos always uses px
        visual_offset = self.item.geometry.px.rect.topLeft()
        self.item.setPos(scene_pos - visual_offset)
        self.item.setSelected(True)
        self.tab.update_layers_panel()

    def undo(self):
        self.tab.registry.deregister(self.item.pid)
        self.tab.scene.removeItem(self.item)
        self.tab.update_layers_panel()

## prototypyside/services/undo_commands.py

class CloneElementCommand(QUndoCommand):
    def __init__(self, item, tab, description="Clone Element"):
        super().__init__(description)
        print(f"We've made it to the undo Command")
        self.item = item
        self.tab = tab
        self.registry = tab.registry
        self.clone = None

    def redo(self):
        if self.clone is None:
            # create it once
            print("Preparing to create clone...")
            self.clone = self.tab.template.registry.clone(self.item)
            # NOTE: clone is already registered by registry.clone()
        else:
            # put it back into active store if you use an orphan bucket
            self.tab.registry.reinsert(self.clone.pid)
            
        # Add to the data model (template's internal list)
        self.tab.template.add_item(self.clone)

        # **[SOLUTION]** Add the clone to the scene graph by parenting it.
        # This is the crucial step that was missing from the command.
        if self.clone.scene() is None:
            self.clone.setParentItem(self.tab.template)
        
        self.clone.show()
        self.tab.update_layers_panel() # Move panel update here

    def undo(self):
        # Your existing undo logic is mostly correct.
        # It correctly removes the item from the template model and the scene.
        self.tab.template.remove_item(self.clone)

        if self.clone.scene():
            self.tab.scene.removeItem(self.clone)

        self.tab.update_layers_panel()

class RemoveElementsCommand(QUndoCommand):
    def __init__(self, items, tab, description="Remove Element"):
        super().__init__(description)
        self.items = items
        self.tab = tab

    def redo(self):
        for item in self.items:
            self.tab.template.remove_item(item)
            self.tab.scene.removeItem(item)
        self.tab.update_layers_panel()

    def undo(self):
        print(self.items)
        for item in self.items:
            self.tab.template.add_item(self.item)
            self.tab.scene.addItem(self.item)
            self.tab.update_layers_panel()

class MoveElementCommand(QUndoCommand):
    def __init__(self, item, new_pos: QPointF, old_pos: QPointF = None, description="Move Element"):
        super().__init__(description)
        self.item = item
        self.old_pos = old_pos
        if old_pos is not None:
            self.old_pos = old_pos
        self.new_pos = new_pos

    def undo(self):
        self.item.setPos(self.old_pos)

    def redo(self):
        self.item.setPos(self.new_pos)

class ResizeElementCommand(QUndoCommand):
    def __init__(self, item, new_rect: QRectF, old_rect: QRectF = None, description="Resize Element"):
        super().__init__(description)
        self.item = item
        self.old_rect = item.rect
        if old_rect:
            self.old_rect = old_rect
        self.new_rect = new_rect

    def undo(self):
        # Prevent re-entrancy when setting the item's geometry
        self.item.blockSignals(True)
        self.item.geometry = self.old_geometry
        self.item.blockSignals(False)

    def redo(self):
        # Prevent re-entrancy when setting the item's geometry
        self.item.blockSignals(True)
        self.item.geometry = self.new_geometry
        self.item.blockSignals(False)

class ChangePropertyCommand(QUndoCommand):
    def __init__(self, item, prop, new_value, old_value, description="Change Item Property"):
        super().__init__(description)
        self.item = item
        self.prop = prop 
        self.new_value = new_value
        self.old_value = old_value

    def undo(self):
        if self.new_value != self.old_value:
            setattr(self.item, self.prop, self.old_value)

    def redo(self):
        # print(f"[UNDO_COMMAND] Something is attempting to change {self.prop} from {self.old_value} to {self.new_value}")
        setattr(self.item, self.prop, self.new_value)

class ResizeTemplateCommand(QUndoCommand):
    def __init__(self, template, new_geometry, old_geometry, description="Resize Template"):
        super().__init__(description)
        self.template = template
        self.old_geometry = old_geometry
        self.new_geometry = new_geometry

    def redo(self):
        self.template.geometry = self.new_geometry

    def undo(self):
        self.template.geometry = self.old_geometry

class CloneComponentTemplateToSlotCommand(QUndoCommand):
    """
    Place a clone of a ComponentTemplate into a specific LayoutSlot.
    - registry: ProtoRegistry
    - template: LayoutTemplate  (the page)
    - item:      ComponentTemplate (the source to clone)
    - slot:      LayoutSlot (target position on the page)
    """
    def __init__(self, registry, template, item, slot, description="Place Component into Slot"):
        super().__init__(description)
        self.registry = registry
        self.layout   = template          # LayoutTemplate
        self.source   = item              # ComponentTemplate (to clone)
        self.slot     = slot              # LayoutSlot (target)
        self.clone    = None
        self.clone_pid = None
        self._prev_content = getattr(slot, "content", None)

    def redo(self):
        if self.clone is None:
            self.clone = self.registry.clone(self.source)  # registered
            self.clone_pid = self.clone.pid
        else:
            self.registry.reinsert(self.clone_pid)          # move back from orphans

        self.slot.content = self.clone

    def undo(self):
        # restore what was there before
        self.slot.content = self._prev_content
        # park the clone in orphans so redo can reinsert
        if self.clone_pid:
            self.registry.deregister(self.clone_pid)

class ClearSlotsCommand(QUndoCommand):
    """
    Clear (set content=None) for the provided LayoutSlots only.
    - Slots whose content is a cloned ComponentTemplate are deregistered on redo
      and reinserted on undo so the clone lifecycle remains correct.
    """
    def __init__(self, registry, slots, description="Clear Selected Slots"):
        super().__init__(description)
        self.registry = registry
        # Keep stable order + exact prior contents for perfect undo fidelity
        self._pairs = [(slot, getattr(slot, "content", None)) for slot in slots]

    def redo(self):
        for slot, content in self._pairs:
            if content is not None:
                # Park the clone so redo/undo works like your other commands
                pid = getattr(content, "pid", None)
                if pid:
                    self.registry.deregister(pid)
            slot.content = None

    def undo(self):
        for slot, content in self._pairs:
            if content is not None:
                pid = getattr(content, "pid", None)
                if pid:
                    self.registry.reinsert(pid)
            slot.content = content

from PySide6.QtGui import QUndoCommand

class ClearSelectedSlotsCommand(QUndoCommand):
    """
    Clear (slot.content = None) for a set of LayoutSlots, optionally filtered
    to those whose content.pid == filter_pid.

    - registry: for deregister()/reinsert() of per-slot clones
    - slots: iterable of LayoutSlot objects
    - filter_pid: if provided, only clear slots whose current content pid matches
    """
    def __init__(self, registry, slots, filter_pid: str | None = None, description="Clear Selected Slots"):
        super().__init__(description)
        self.registry = registry
        self.filter_pid = filter_pid

        # Capture exact prior content for perfect undo
        pairs = []
        for s in slots:
            c = s.content
            pairs.append((s, c))
        self._pairs = pairs  # only the ones we will actually clear

    def redo(self):
        for slot, content in self._pairs:
            if hasattr(content, "pid"):
                pid = getattr(content, "pid", None)
                if pid:
                    self.registry.deregister(pid)  # park clone in orphans
                    slot.content = None
            slot.update()

    def undo(self):
        for slot, content in self._pairs:
            pid = getattr(content, "pid", None)
            if pid:
                self.registry.reinsert(pid)     # pull clone back from orphans
            slot.content = content
            slot.update()

class CloneComponentToEmptySlotsCommand(QUndoCommand):
    """
    Fill all empty LayoutSlots in a LayoutTemplate with clones of a ComponentTemplate.
    """
    def __init__(self, registry, template, comp, description="Autofill Empty Slots"):
        super().__init__(description)
        self.registry = registry
        self.layout   = template          # LayoutTemplate
        self.source   = comp              # ComponentTemplate to clone
        # remember original contents (exact restore on undo)
        self._orig_contents = [slot.content for slot in self.layout.items]
        # pairs we actually created on first redo: (slot_ref, clone_ref)
        self._filled_pairs = []

    def redo(self):
        if not self._filled_pairs:
            # first execution: create clones for empty slots and assign
            for slot in self.layout.items:
                if slot.content is None:
                    clone = self.registry.clone(self.source)  # registered
                    self._filled_pairs.append((slot, clone))
                    slot.content = clone
        else:
            # redo after undo: reinsert and reattach previous clones
            for slot, clone in self._filled_pairs:
                self.registry.reinsert(clone.pid)
                slot.content = clone

        # optional: if your layout has a 'content' field that tracks the source template id:
        # self.layout.content = self.source.pid

    def undo(self):
        # clear only what we created, and deregister those clones
        for slot, clone in self._filled_pairs:
            slot.content = None
            self.registry.deregister(clone.pid)

        # restore original slot contents exactly
        for slot, old in zip(self.layout.items, self._orig_contents):
            slot.content = old

class AssignTemplateToSelectedSlotsCommand(QUndoCommand):
    """
    Assign `template_pid` to a set of LayoutSlots.
    - Skips any slot that already contains a clone of `template_pid`.
    - Replaces other content (deregistering the old clone), then registers a new clone.
    - Undo restores original content precisely (reinsert old clone if it existed).
    Requirements:
      - registry.get(pid) -> template object
      - template.clone() -> new component instance (with fresh pid)
      - registry.register(obj) / registry.deregister(pid) / registry.reinsert(pid)
    """
    def __init__(self, registry, tpid: str, slots, description="Add to Selected Slots"):
        super().__init__(description)
        self.registry = registry
        self.tpid = tpid

        # Build worklist: only slots that are not already populated by this template
        self._items = []
        for s in slots:
            content = getattr(s, "content", None)
            # If already same template, skip
            if content is not None and getattr(content, "tpid", None) == tpid:
                continue
            # Record prior content (for undo) and placeholder for new clone pid
            self._items.append({
                "slot": s,
                "old": content,
                "new_pid": None,
            })


    def redo(self):
        for it in self._items:
            slot = it["slot"]
            old  = it["old"]

            # Remove old content if any
            if old is not None:
                old_pid = getattr(old, "pid", None)
                if old_pid:
                    self.registry.deregister(old_pid)

            # Make/register a fresh clone of the desired template
            template = self.registry.global_get(self.tpid)
            clone = self.registry.clone(template)
            it["new_pid"] = getattr(clone, "pid", None)
            slot.content = clone

    def undo(self):
        for it in self._items:
            slot = it["slot"]
            old  = it["old"]
            new_pid = it["new_pid"]

            # Remove new clone
            if new_pid:
                self.registry.deregister(new_pid)

            # Restore old content (reinsert if it had a pid)
            if old is not None:
                old_pid = getattr(old, "pid", None)
                if old_pid:
                    self.registry.reinsert(old_pid)
            slot.content = old

class ChangePropertiesCommand(QUndoCommand):
    def __init__(self, item, props, new_values, old_values,
                 description="Change Item Property"):
        super().__init__(description)
        self.item = item
        # store tuples of (item, prop_name, new, old)
        self._commands = list(zip(props, new_values, old_values))

    def undo(self):
        for prop, new, old in self._commands:
            # only restore if it’s out of sync
            if getattr(self.item, prop) != old:
                setattr(self.item, prop, old)

    def redo(self):
        for prop, new, old in self._commands:
            # only apply if it’s out of sync
            if getattr(self.item, prop) != new:
                setattr(self.item, prop, new)
