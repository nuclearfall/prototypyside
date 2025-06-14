from prototypyside.services.undo_manager import MoveElementCommand, ResizeElementCommand

class GeometrySetter:
    def __init__(self, undo_manager):
        self.undo_manager = undo_manager

    def set_rect(self, element, new_rect):
        old_rect = element.rect()
        if old_rect != new_rect:
            element.setRect(new_rect)
            if self.undo_manager:
                self.undo_manager.push(ResizeElementCommand(element, old_rect, new_rect))

    def set_pos(self, element, new_pos):
        old_pos = element.pos()
        if old_pos != new_pos:
            element.setPos(new_pos)
            if self.undo_manager:
                self.undo_manager.push(MoveElementCommand(element, old_pos, new_pos))
