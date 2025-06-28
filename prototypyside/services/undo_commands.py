from PySide6.QtGui import QUndoCommand
from PySide6.QtCore import QPointF, QRectF

from prototypyside.utils.unit_converter import pos_to_unit_str
from prototypyside.utils.unit_str import UnitStr

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

class AddElementCommand(QUndoCommand):
    def __init__(self, prefix, scene_pos, tab, description="Add Element"):
        super().__init__(description)
        self.prefix = prefix
        self.tab = tab
        self.scene_pos = scene_pos

        self.element = None

    def redo(self):
        if self.element is None:
            unit = self.tab.settings.unit or "in"
            dpi = self.tab.settings.dpi or 300
            logical_x, logical_y = pos_to_unit_str(self.scene_pos, unit, dpi)
            

            # Convert default width/height (in inches) to the current logical unit
            default_w_in = 0.5
            default_h_in = 0.5

            if unit == "in":
                w_physical = default_w_in
                h_physical = default_h_in
            elif unit == "mm":
                w_physical = default_w_in * 25.4
                h_physical = default_h_in * 25.4
            elif unit == "cm":
                w_physical = default_w_in * 2.54
                h_physical = default_h_in * 2.54
            elif unit == "pt":
                w_physical = default_w_in * 72.0
                h_physical = default_h_in * 72.0
            else:
                w_physical = default_w_in
                h_physical = default_h_in

            # Build the QRectF in logical units
            new_rect = QRectF(0, 0, w_physical, h_physical)
            self.element = self.tab.registry.create(
                self.prefix,
                rect=new_rect,
                pos = self.scene_pos,
                template_pid = self.tab.template_pid,
                parent=self.tab.template,
                name=None
            )
            self.tab.template.add_element(self.element)

        elif self.element is not None and self.tab.registry.is_orphan(self.element.pid):
            self.tab.registry.reinsert(self.element.pid)

        if self.element.scene() is None:
            self.tab.scene.addItem(self.element)

        # Snap to grid if enabled (in px, so reconvert)
        if self.tab.snap_to_grid:
            self.scene_pos = self.tab.scene.snap_to_grid(self.scene_pos)

        # For QGraphicsItem, setPos always uses px
        visual_offset = self.element.boundingRect().topLeft()
        self.element.setPos(self.scene_pos - visual_offset)
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
        self.element.rect = self.old_rect

    def redo(self):
        self.element.rect = self.new_rect

class ResizeAndMoveElementCommand(QUndoCommand):
    def __init__(self, element, new_values, old_values, description="Resize/Move Element"):
        super().__init__(description)
        self.element = element
        self.new_pos, self.new_rect = new_values
        self.old_pos, self.old_rect = old_values

    def undo(self):
        self.element.rect = self.old_rect
        self.element.setPos(self.old_pos)

    def redo(self):
        print(f"Placing rect in undo stack with dimensions {self.new_rect} at position {self.new_pos}")
        self.element.rect = self.new_rect
        self.element.setPos(self.new_pos)

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
    def __init__(self, template, new_width: 'UnitStr', new_height: 'UnitStr', description="Resize Template"):
        super().__init__(description)
        self.template = template
        # Defensive copy of the old values
        self.old_width = template.width
        self.old_height = template.height
        self.new_width = new_width
        self.new_height = new_height

    def redo(self):
        self.template.width = self.new_width
        self.template.height = self.new_height

    def undo(self):
        self.template.width = self.old_width
        self.template.height = self.old_height