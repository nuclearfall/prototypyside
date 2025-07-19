from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QColor

from prototypyside.utils.unit_converter import to_px, to_px_pos, to_px_qrectf
from prototypyside.services.undo_commands import ChangePropertyCommand

class PropertySetter:
    def __init__(self, undo_stack):
        self.undo_stack = undo_stack

    def set_prop(self, item, change):
        print (f"Transferring {change} to {item.name}")
        command = ChangePropertyCommand(item, change)
        self.undo_stack.push(command)
