from PySide6.QtGui import QUndoCommand
from PySide6.QtCore import QPointF, QRectF

from prototypyside.models.component_template import ComponentTemplate
from prototypyside.utils.unit_converter import pos_to_unit_str
from prototypyside.utils.proto_helpers import resolve_pid, get_prefix 
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry

class AddSlotCommand(QUndoCommand):
    def __init__(self, registry, template):
        self.template = template
        self.registry = registry
        self.item = None

    def undo(self):
        self.registry.deregister(self.item.pid)

    def redo(self):
        if item is None:
            self.item = self.registry.create("ls", tpid=self.template.pid, registry=self.registry, parent=self.template)
        else:
            self.registry.reinsert(self.item)

class AddElementCommand(QUndoCommand):
    def __init__(self, prefix, tab, geometry, description="Add Element"):
        super().__init__(description)
        self.prefix = prefix
        self.registry = tab.registry
        self.tab = tab
        self.geometry = geometry
        self.item = None

    def redo(self):
        if self.item is None:
            # Convert default width/height (in inches) to the current logical unit
            self.item = self.tab.registry.create(
                self.prefix,
                geometry=self.geometry,
                registry=self.registry,
                tpid = self.tab.template.pid,
                parent=self.tab.template,
                name=None
            )
            # self.item.setRect(self.geometry.px.rect)
            self.tab.template.add_item(self.item)
            self.item.setParentItem(self.tab.template)

        elif self.item is not None and self.tab.registry.is_orphan(self.item.pid):
            self.tab.registry.reinsert(self.item.pid)

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

class CloneElementCommand(QUndoCommand):
    def __init__(self, item, tab, description="Clone Element"):
        super().__init__(description)
        self.item = item
        self.clone = None
        self.tab = tab

    def redo(self):
        if self.clone is None:
            self.clone = self.tab.registry.clone(self.item)
        else:
            self.tab.registry.reinsert(self.clone.pid)
        if self.clone.scene() is None:
            self.tab.scene.addItem(self.clone)
        self.tab.update_layers_panel()

    def undo(self):
        self.tab.registry.deregister(self.clone.pid)
        self.tab.scene.removeItem(self.clone)
        self.tab.update_layers_panel()

class RemoveElementCommand(QUndoCommand):
    def __init__(self, item, tab, description="Remove Element"):
        super().__init__(description)
        self.item = item
        self.tab = tab

    def redo(self):
        self.tab.template.remove_item(self.item)
        self.tab.scene.removeItem(self.item)
        self.tab.update_layers_panel()

    def undo(self):
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
        print(f"[UNDO] Target ID: {id(self.item)}, Prop: {self.prop}, New: {self.new_value}")
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
    def __init__(self, registry, template, item, description="Add Template to Slot"):
        super().__init__(description)
        self.registry = registry
        self.item = item
        self.template = template
        self.clone = None
        self.clone_pid = None

    def redo(self):
        if self.clone is None:
            self.clone = self.registry.clone(self.template)
            self.clone_pid = self.clone.pid
            setattr(self.item, "content", self.clone)
        else:
            self.registry.reinsert(self.clone_pid)
            self.item.content = self.clone

    def undo(self):
        self.deregister(self.clone_pid)
        self.item.content = None

class CloneComponentToEmptySlotsCommand(QUndoCommand):
    def __init__(self, registry, template, comp, description="Autofill Template with Component"):
        super().__init__(description)
        self.registry = registry
        self.template = template
        self.comp = comp
        # Save initial state
        self.old_items = [row[:] for row in template.items]  # deep-ish copy
        self.old_content = template.content
        self.old_slot_contents = [slot.content for row in template.items for slot in row]
        # This will be filled with new clones (only once)
        self.new_clones = []

    def redo(self):
        flat_slots = [slot for row in self.template.items for slot in row]

        if not self.new_clones:
            # First execution: generate clones and assign
            self.new_clones = []
            for slot in flat_slots:
                clone = self.registry.clone(self.comp)
                slot.content = clone
                self.new_clones.append(clone)
        else:
            # Redo after undo: reinsert and reassign
            for clone, slot in zip(self.new_clones, flat_slots):
                self.registry.reinsert(clone.pid)
                slot.content = clone

        # Set template-level CSV reference
        self.template.content = self.comp.pid
        print(f"CLONED: Slots are {[s.pid for row in self.template.items for s in row]}")

    def undo(self):
        flat_slots = [slot for row in self.template.items for slot in row]

        # Deregister and clear slot content
        for slot, clone in zip(flat_slots, self.new_clones):
            self.registry.deregister(clone.pid)
            slot.content = None

        # Restore old content per slot
        for slot, old in zip(flat_slots, self.old_slot_contents):
            slot.content = old

        # Restore previous template-wide content ref
        self.template.content = self.old_content
        self.template.items = [row[:] for row in self.old_items]



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
