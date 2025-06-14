# undo_manager.py
from typing import List, Optional

class Command:
    def undo(self):
        raise NotImplementedError

    def redo(self):
        raise NotImplementedError


class UndoManager:
    def __init__(self, registry):
        self._registry = registry
        self._stack: List[Command] = []
        self._pointer: int = -1

    def execute(self, command: Command):
        # Remove future commands if pointer is not at the top
        del self._stack[self._pointer + 1:]
        self._stack.append(command)
        self._pointer += 1
        command.redo()

    def undo(self):
        if self._pointer >= 0:
            command = self._stack[self._pointer]
            command.undo()
            self._pointer -= 1

    def redo(self):
        if self._pointer + 1 < len(self._stack):
            self._pointer += 1
            command = self._stack[self._pointer]
            command.redo()

class MoveElementCommand(Command):
    def __init__(self, element, old_pos, new_pos):
        self.element = element
        self.old_pos = old_pos
        self.new_pos = new_pos

    def undo(self):
        self.element.setPos(self.old_pos)

    def redo(self):
        self.element.setPos(self.new_pos)

class ResizeElementCommand(Command):
    def __init__(self, element, old_rect, new_rect):
        self.element = element
        self.old_rect = old_rect
        self.new_rect = new_rect

    def undo(self):
        self.element.setRect(self.old_rect)

    def redo(self):
        self.element.setRect(self.new_rect)

class AddElementCommand(Command):
    def __init__(self, prefix, template_pid):
        self.registry = registry
        self.prefix = prefix
        self.template_pid = template_pid
        self.element = None

    def redo(self):
        if not self.element:
            # First-time creation
            self.element = self.registry.create(self.prefix, template_pid=self.template_pid)
        else:
            # Reinsert previously created element
            self.registry.reinsert(self.element.pid)

    def undo(self):
        self.registry.deregister(self.element.pid)


class RemoveElementCommand(Command):
    def __init__(self, element):
        self.element = element

    def undo(self):
        self._registry.reinsert(self.element.pid)

    def redo(self):
        self._registry.deregister(self.element.pid)

class CloneElementCommand(Command):
    def __init__(self, registry, element):
        self.registry = registry
        self.original_element = element
        self.clone_element = None

    def redo(self):
        if not self.clone_element:
            # Create clone, using the original element's template_pid
            self.clone_element = self.registry.clone(self.original_element)
        else:
            # Reinsert previously cloned element
            self.registry.reinsert(self.clone_element.pid)

    def undo(self):
        if self.clone_element:
            self.registry.deregister(self.clone_element.pid)





