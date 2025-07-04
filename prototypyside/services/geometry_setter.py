# prototypyside/services/geometry_setter.py (Updated)
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QUndoStack # Import QUndoStack

# Assuming these are defined in prototypyside.services.undo_manager
from prototypyside.services.undo_commands import MoveElementCommand, ResizeElementCommand
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from prototypyside.models.component_elements import ComponentElement

class GeometrySetter:
    def __init__(self, undo_stack: QUndoStack):
        self.undo_stack = undo_stack

    def set_rect(self, element: 'ComponentElement', new_rect: QRectF):
        old_rect = element.rect
        if old_rect != new_rect:
            # Create and push the command to the undo stack
            command = ResizeElementCommand(element, new_rect, "Resize Element")
            self.undo_stack.push(command)
            # The command's redo() method will call element.setRect(new_rect)
            # which correctly handles emitting element_changed and calling update().

    def set_pos(self, element: 'ComponentElement', new_pos: QPointF):
        old_pos = element.pos
        if old_pos != new_pos:
            # Create and push the command to the undo stack
            command = MoveElementCommand(element, new_pos, "Move Element")
            self.undo_stack.push(command)

    def set_pos_and_rect(self, element, new_pos, new_rect):
        old_geo = element.geometry
        unit = old_geo.unit
        dpi = old_geo.dpi
        new_geo = UnitStrGeometry(rect=new_rect, pos=new_pos, unit=old_geo.unit, dpi=old_geo.dpi)
        command = ResizeAndMoveElementCommand(element, new_geo, old_geo)
        self.undo_stack.push(command)
            # The command's redo() method will call element.setPos(new_pos)
            # which correctly handles emitting element_changed and calling update().