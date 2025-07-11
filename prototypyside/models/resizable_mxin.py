from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtWidgets import QGraphicsItem

from prototypyside.graphics_items import ResizeHandle, HandleType

class ResizableMixin:
    def __init__(self):
        self._handles = {}

    def create_handles(self):
        """Create 8 resize handles and attach them to the parent item."""
        if not isinstance(self, QGraphicsItem):
            raise TypeError("ResizableMixin can only be used with QGraphicsItem subclasses")

        for handle_type in HandleType:
            handle = ResizeHandle(handle_type, self)
            handle.setParentItem(self)
            handle.hide()
            self._handles[handle_type] = handle
        self.update_handle_positions()

    def update_handle_positions(self):
        """Update the position of each handle based on the current rect."""
        rect = self.boundingRect()
        cx = rect.center().x()
        cy = rect.center().y()
        x = rect.x()
        y = rect.y()
        w = rect.width()
        h = rect.height()

        positions = {
            HandleType.TOP_LEFT: QPointF(x, y),
            HandleType.TOP: QPointF(cx, y),
            HandleType.TOP_RIGHT: QPointF(x + w, y),
            HandleType.RIGHT: QPointF(x + w, cy),
            HandleType.BOTTOM_RIGHT: QPointF(x + w, y + h),
            HandleType.BOTTOM: QPointF(cx, y + h),
            HandleType.BOTTOM_LEFT: QPointF(x, y + h),
            HandleType.LEFT: QPointF(x, cy),
        }

        for handle_type, pos in positions.items():
            if handle_type in self._handles:
                self._handles[handle_type].setPos(pos)

    def show_handles(self):
        for handle in self._handles.values():
            handle.show()

    def hide_handles(self):
        for handle in self._handles.values():
            handle.hide()

    def resize_from_handle(self, handle, delta: QPointF, start_rect: QRectF):
        """Resize based on which handle was dragged and by how much."""
        if not isinstance(self, QGraphicsItem):
            return

        rect = QRectF(start_rect)

        if handle.handle_type in {HandleType.TOP_LEFT, HandleType.LEFT, HandleType.BOTTOM_LEFT}:
            rect.setLeft(rect.left() + delta.x())
        if handle.handle_type in {HandleType.TOP_RIGHT, HandleType.RIGHT, HandleType.BOTTOM_RIGHT}:
            rect.setRight(rect.right() + delta.x())
        if handle.handle_type in {HandleType.TOP_LEFT, HandleType.TOP, HandleType.TOP_RIGHT}:
            rect.setTop(rect.top() + delta.y())
        if handle.handle_type in {HandleType.BOTTOM_LEFT, HandleType.BOTTOM, HandleType.BOTTOM_RIGHT}:
            rect.setBottom(rect.bottom() + delta.y())

        # Apply minimum size constraint
        min_size = 0.1
        if rect.width() < min_size:
            rect.setWidth(min_size)
        if rect.height() < min_size:
            rect.setHeight(min_size)

        self.prepareGeometryChange()
        self.setRect(rect)
        self.update_handle_positions()
        self.item_changed.emit()
