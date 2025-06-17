from PySide6.QtGui import QUndoCommand
from PySide6.QtCore import QPointF, QRectF


class AddElementCommand(QUndoCommand):
    def __init__(self, prefix, scene_pos, tab, description="Add Element"):
        super().__init__(description)
        self.prefix = prefix
        self.tab = tab
        self.scene_pos = scene_pos
        self.element = None

    def redo(self):

        if self.element is None:

            new_rect = QRectF(0, 0, 150, 120)
            self.element = self.tab.registry.create(
                self.prefix,
                name=None,
                rect=new_rect,
                parent_qobject=self.tab.current_template
            )
            
        elif self.element is not None and self.tab.registry.is_orphan(self.element.pid):
            self.tab.registry.reinsert(self.element.pid)

        if self.element.scene() is None:
            self.tab.scene.addItem(self.element)
        if self.tab.snap_to_grid:
            self.scene_pos = self.tab.scene.snap_to_grid(self.scene_pos)

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
        self.old_pos = element.pos()
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
        print(f"{self.prop} has been changed to {self.new_value} from {self.old_value}")
        setattr(self.element, self.prop, self.new_value)

class ResizeTemplateCommand(QUndoCommand):
    def __init__(self, element, new_pos: QPointF, description="Move Element"):
        super().__init__(description)