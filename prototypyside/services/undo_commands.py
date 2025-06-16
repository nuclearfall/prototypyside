from PySide6.QtGui import QUndoCommand
from PySide6.QtCore import QPointF, QRectF


class AddElementCommand(QUndoCommand):
    def __init__(self, element, tab, description="Add Element"):
        super().__init__(description)
        self.element = element
        self.tab = tab

    def redo(self):
        self.tab.add_element(self.element)

    def undo(self):
        self.tab.remove_element(self.element)

class RemoveElementCommand(QUndoCommand):
    def __init__(self, element, tab, description="Remove Element"):
        self.element = element
        self.tab = tab

    def redo(self):
        self.tab.remove_element(self.element) 

class MoveElementCommand(QUndoCommand):
    def __init__(self, element, new_pos: QPointF, description="Move Element"):
        super().__init__(description)
        self.element = element
        self.old_pos = element.pos()
        self.new_pos = new_pos

    def undo(self):
        self.element.setPos(self.old_pos)

    def redo(self):
        self.element.setPos(self.new_pos)

class ResizeElementCommand(QUndoCommand):
    def __init__(self, element, new_rect: QRectF, description="Resize Element"):
        super().__init__(description)
        self.element = element
        self.old_rect = element.rect
        self.new_rect = new_rect

    def undo(self):
        self.element.setRect(self.old_rect)

    def redo(self):
        self.element.setRect(self.new_rect)

class ResizeTemplateCommand(QUndoCommand):
    def __init__(self, element, new_pos: QPointF, description="Move Element"):
        super().__init__(description)  