from PySide6.QtWidgets import QGraphicsItem

def has_flag(item: QGraphicsItem, flag: QGraphicsItem.GraphicsItemFlag) -> bool:
    return bool(item.flags() & flag)

def set_flag(item: QGraphicsItem, flag: QGraphicsItem.GraphicsItemFlag, enabled: bool = True):
    item.setFlag(flag, enabled)

def is_movable(item: QGraphicsItem) -> bool:
    return has_flag(item, QGraphicsItem.ItemIsMovable)

def is_selectable(item: QGraphicsItem) -> bool:
    return has_flag(item, QGraphicsItem.ItemIsSelectable)

def is_focusable(item: QGraphicsItem) -> bool:
    return has_flag(item, QGraphicsItem.ItemIsFocusable)

def is_resizable(item: QGraphicsItem) -> bool:
    return has_flag(item, QGraphicsItem.ItemSendsGeometryChanges)

def set_movable(item: QGraphicsItem, movable: bool = True):
    set_flag(item, QGraphicsItem.ItemIsMovable, movable)

def set_selectable(item: QGraphicsItem, selectable: bool = True):
    set_flag(item, QGraphicsItem.ItemIsSelectable, selectable)

def set_focusable(item: QGraphicsItem, focusable: bool = True):
    set_flag(item, QGraphicsItem.ItemIsFocusable, focusable)

def set_clips_children(item: QGraphicsItem, clips: bool = True):
    set_flag(item, QGraphicsItem.ItemClipsChildrenToShape, clips)
