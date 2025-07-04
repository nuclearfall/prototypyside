from PySide6.QtGui import QUndoCommand
from PySide6.QtCore import QPointF, QRectF

from prototypyside.models.component_template import ComponentTemplate
from prototypyside.utils.unit_converter import pos_to_unit_str
from prototypyside.utils.proto_helpers import issue_pid, get_prefix 
from prototypyside.utils.unit_str import UnitStr
from prototypyside.utils.unit_str_geometry import UnitStrGeometry

class AddSlotCommand(QUndoCommand):
    def __init__(self, registry, template):
        self.template = template
        self.registry = registry
        self.slot = None

    def undo(self):
        self.registry.deregister(self.slot.pid)

    def redo(self):
        if slot is None:
            self.slot = self.registry.create("ls", tpid=self.template.pid, cpid=None, parent=self.template)
        else:
            self.registry.reinsert(self.slot)


# This method doesn't require adding the template to the scene.
# Instead when dropped, it also creates a ComponentInstance which will Render
# and adds that to the scene. The ComponentInstance renders the Template.
class CreateComponentCommand(QUndoCommand):
    def __init__(self, component, tab, slot, description="Clone Element"):
        super().__init__(description)
        self.tab = tab
        self.component = component
        self.registry = tab.registry
        self.scene = tab.scene
        self.slot = slot

        self.clone = None
        self.clone_elements = []

    def redo(self):
        if self.clone is None:
            self.clone = self.registry.clone(self.component)
            self.clone.setParentItem(self.slot)

            self.clone_elements = self.registry.clone_all(self.component.elements)

            for ce in self.clone_elements:
                self.clone.add_element(ce)
                ce.setParentItem(self.clone)
                self.scene.addItem(ce)
        else:
            self.registry.reinsert(self.clone.pid)
            for element in self.clone_elemnts:
                self.registry.reinsert(element.pid)

    def undo(self):
        for ce in self.clone_elements:
            self.registry.deregister(ce.pid)
            self.scene.removeItem(ce)

        self.slot.content = None
        self.registry.deregister(self.clone.pid)
        self.scene.removeItem(self.clone)


class AddElementCommand(QUndoCommand):
    def __init__(self, prefix, tab, geometry, description="Add Element"):
        super().__init__(description)
        print(f"Command received geometry {geometry}")
        self.prefix = prefix
        self.registry = tab.registry
        self.tab = tab
        self.geometry = geometry
        self.element = None

    def redo(self):
        if self.element is None:
            # Convert default width/height (in inches) to the current logical unit
            self.element = self.tab.registry.create(
                self.prefix,
                geometry=self.geometry,
                template_pid = self.tab.template.pid,
                parent=self.tab.template,
                name=None
            )
            self.element.setRect(self.geometry.px.rect)
            self.tab.template.add_element(self.element)

        elif self.element is not None and self.tab.registry.is_orphan(self.element.pid):
            self.tab.registry.reinsert(self.element.pid)

        if self.element.scene() is None:
            self.tab.scene.addItem(self.element)

        scene_pos = self.element.pos()
        # Snap to grid if enabled (in px, so reconvert)
        if self.tab.snap_to_grid:
            self.element.setPos(self.tab.scene.snap_to_grid(scene_pos))

        # For QGraphicsItem, setPos always uses px
        visual_offset = self.element.geometry.px.rect.topLeft()
        self.element.setPos(scene_pos - visual_offset)
        self.element.setSelected(True)
        self.tab.update_layers_panel()

    def undo(self):
        self.tab.registry.deregister(self.element.pid)
        self.tab.scene.removeItem(self.element)
        self.tab.update_layers_panel()

class CloneElementCommand(QUndoCommand):
    def __init__(self, element, tab, description="Clone Element"):
        super().__init__(description)
        self.element = element
        self.clone = None
        self.tab = tab

    def redo(self):
        if self.clone is None:
            self.clone = self.tab.registry.clone(self.element)
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
    def __init__(self, element, tab, description="Remove Element"):
        super().__init__(description)
        self.element = element
        self.tab = tab

    def redo(self):
        self.tab.registry.deregister(self.element.pid)
        self.tab.scene.removeItem(self.element)
        self.tab.update_layers_panel()

    def undo(self):
        self.tab.registry.reinsert(self.element.pid)
        self.tab.scene.addItem(self.element)
        self.tab.update_layers_panel()

class MoveElementCommand(QUndoCommand):
    def __init__(self, element, new_pos: QPointF, old_pos: QPointF = None, description="Move Element"):
        super().__init__(description)
        self.element = element
        self.old_pos = old_pos
        if old_pos is not None:
            self.old_pos = old_pos
        self.new_pos = new_pos

    def undo(self):
        self.element.setPos(self.old_pos)

    def redo(self):
        self.element.setPos(self.new_pos)

class ResizeElementCommand(QUndoCommand):
    def __init__(self, element, new_rect: QRectF, old_rect: QRectF = None, description="Resize Element"):
        super().__init__(description)
        self.element = element
        self.old_rect = element.rect
        if old_rect:
            self.old_rect = old_rect
        self.new_rect = new_rect

    def undo(self):
        self.element.setRect(self.old_rect)

    def redo(self):
        self.element.setRect(self.new_rect)

class ResizeAndMoveElementCommand(QUndoCommand):
    def __init__(self, element, new_geometry, old_geometry, description="Resize/Move Element"):
        super().__init__(description)
        self.element = element
        self.new_geometry = new_geometry
        self.old_geometry = old_geometry

    def undo(self):
        self.element._geometry = self.old_geometry

    def redo(self):
        print(f"Preparing to resize and move in Command. New Geometry: {self.new_geometry}")
        self.element._geometry = self.new_geometry

class ChangeElementPropertyCommand(QUndoCommand):
    def __init__(self, element, change, description="Change Element Property"):
        super().__init__(description)
        self.element = element
        self.prop, self.new_value = change
        self.old_value = getattr(element, self.prop)


    def undo(self):
        if self.new_value != self.old_value:
            setattr(self.element, self.prop, self.old_value)

    def redo(self):
        setattr(self.element, self.prop, self.new_value)

class ResizeTemplateCommand(QUndoCommand):
    def __init__(self, template, new_geometry, description="Resize Template"):
        super().__init__(description)
        self.template = template
        self.old_geometry = copy(self.template.geometry)
        self.new_geometry = new_geometry

    def redo(self):
        self.template._geometry = self.new_geometry

    def undo(self):
        self.template._geometry = self.old_geometry