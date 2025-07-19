from PySide6.QtGui import QUndoCommand
from PySide6.QtCore import QPointF, QRectF

from prototypyside.models.component_template import ComponentTemplate
from prototypyside.utils.unit_converter import pos_to_unit_str
from prototypyside.utils.proto_helpers import issue_pid, get_prefix 
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
            self.item = self.registry.create("ls", tpid=self.template.pid, cpid=None, parent=self.template)
        else:
            self.registry.reinsert(self.item)


# This method doesn't require adding the template to the scene.
# Instead when dropped, it also creates a ComponentInstance which will Render
# and adds that to the scene. The ComponentInstance renders the Template.
# # class CreateComponentCommand(QUndoCommand):
# #     def __init__(self, component, tab, item, description="Clone Element"):
# #         super().__init__(description)
# #         self.tab = tab
# #         self.component = component
# #         self.registry = tab.registry
# #         self.scene = tab.scene
# #         self.item = item

# #         self.clone = None
# #         self.clone_items = []

# #     def redo(self):
# #         if self.clone is None:
# #             self.clone = self.registry.clone(self.component)
# #             self.clone.setParentItem(self.item)

# #             self.clone_items = self.registry.clone_all(self.component.items)

# #             for ce in self.clone_items:
# #                 self.clone.add_item(ce)
# #                 ce.setParentItem(self.clone)
# #                 self.scene.addItem(ce)
# #         else:
# #             self.registry.reinsert(self.clone.pid)
# #             for item in self.clone_elemnts:
# #                 self.registry.reinsert(item.pid)

#     def undo(self):
#         for ce in self.clone_items:
#             self.registry.deregister(ce.pid)
#             self.scene.removeItem(ce)

#         self.item.content = None
#         self.registry.deregister(self.clone.pid)
#         self.scene.removeItem(self.clone)

class AddTemplateToLayoutCommand(QUndoCommand):
    def __init__(self, component, layout, description="Add Element"):
        super().__init__(description)
        self.component = component
        self.clone = None
        self.layout = layout

    def redo(self):
        if self.item is None:
            self.clone = self.layout.registry.clone(self.component)
            self.layout.content = self.clone

        elif self.clone is not None and self.layout.registry.is_orphan(self.clone.pid):
            self.layout.registry.reinsert(self.clone.pid)
            self.layout.content.append(self.clone)

    def undo(self):
        self.layout.deregister(self.clone)
        self.layout.content.pop(self.clone)

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
        if self.tab.snap_to_grid:
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
        self.tab.registry.deregister(self.item.pid)
        self.tab.scene.removeItem(self.item)
        self.tab.update_layers_panel()

    def undo(self):
        self.tab.registry.reinsert(self.item.pid)
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

class ResizeAndMoveElementCommand(QUndoCommand):
    pass
    # def __init__(self, item, new_geometry, old_geometry, description="Resize/Move Element"):
    #     super().__init__(description)
    #     geom = item.geometry
    #     print(f"Element rect and pos prior to move and resize: {geom.px.rect} at {geom.px.pos}.")
    #     self.item = item
    #     self.new_geometry = new_geometry
    #     self.old_geometry = old_geometry

    # def undo(self):
    #     # Prevent re-entrancy when setting the item's geometry
    #     self.item.geometry = self.old_geometry

    # def redo(self):
    #     # Prevent re-entrancy when setting the item's geometry
    #     self.item.geometry = self.new_geometry


<<<<<<< Updated upstream
class ChangePropertyCommand(QUndoCommand):
    def __init__(self, item, prop, new_value, old_value, description="Change Element Property"):
=======
class ChangeItemPropertyCommand(QUndoCommand):
    def __init__(self, item, prop, new_value, old_value, description="Change Item Property"):
>>>>>>> Stashed changes
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

# class CloneComponentTemplateToSlotCommand(QUndoCommand):
#     def __init__(self, registry, template, item, description="Add Template to Slot"):
#         super().__init__(description)
#         self.registry = registry
#         self.item = item
#         self.template = template
#         self.clone = None
#         self.clone_pid = None

#     def redo(self):
#         if self.clone is None:
#             self.clone = self.registry.clone(self.template)
#             self.clone_pid = self.clone.pid
#             setattr(self.item, "content", self.clone)
#         else:
#             self.registry.reinsert(self.clone_pid)
#             self.item.content = self.clone

#     def undo(self):
#         self.deregister(self.clone_pid)
#         self.item.content = None

class CloneComponentTemplateToSlotCommand(QUndoCommand):
    def __init__(self, registry, template, item, mail_room, description="Add Template to Slot"):
        super().__init__(description)
        self.registry = registry
        self.item = item
        self.template = template
        self.mail_room = mail_room
        self.clone = None
        self.clone_pid = None
        self.previous_content = item.content
        self.previous_content_pid = getattr(self.previous_content, "pid", None)

    def redo(self):
        # Clone the template and set as content
        if self.clone is None:
            self.clone = self.registry.clone(self.template)
            self.clone_pid = self.clone.pid
        else:
            self.registry.reinsert(self.clone_pid)
        # Build packet
        packet = {
            "action": "clone_and_insert",
            "template_pid": self.template.pid,
            "slot_pid": self.item.pid,
            "clone_pid": self.clone_pid,
            "previous_content_pid": self.previous_content_pid,
        }
        self.mail_room.send_packet(
            sender_pid=self.template.pid,
            target_pid=self.item.pid,
            packet=packet
        )

    def undo(self):
        # Build packet to restore previous content
        packet = {
            "action": "restore_previous_content",
            "slot_pid": self.item.pid,
            "clone_pid": self.clone_pid,
            "previous_content_pid": self.previous_content_pid,
        }
        self.mail_room.send_packet(
            sender_pid=self.template.pid,
            target_pid=self.item.pid,
            packet=packet
        )

        
class PropertyChangeCommand:
    def __init__(self, sender_pid, target_pid, packet, mail_room):
        self.sender_pid = sender_pid
        self.target_pid = target_pid
        self.packet = packet
        self.mail_room = mail_room
        self.undo_packet = generate_undo_packet(packet)

    def redo(self):
        self.mail_room.send_packet(self.sender_pid, self.target_pid, self.packet)

    def undo(self):
        self.mail_room.send_packet(self.sender_pid, self.target_pid, self.undo_packet)



def generate_undo_packet(packet: dict) -> dict:
    # Make a shallow copy so we don't mutate the original packet
    undo_packet = packet.copy()
    # Swap new and old values
    undo_packet["new"], undo_packet["old"] = packet["old"], packet["new"]
    return undo_packet

