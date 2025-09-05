from PySide6.QtWidgets import QGraphicsItem
from PySide6.QtCore import QPointF, QRectF

def has_flag(item, flag):
    return bool(item and item.flags() & flag)

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

def set_rotation(item: QGraphicsItem, angle: float) -> None:
    origin = item.boundingRect().center()
    item.setTransformOriginPoint(origin)
    item.setRotation(angle % 360)

def rotate_by(item: QGraphicsItem, delta: float) -> float:
    """Rotate relatively by delta degrees (normalized)."""
    return set_rotation(item, item.rotation() + delta)

def rotate_every_other(items: list[QGraphicsItem], angle: float = 180) -> None:
    """Rotate every second item in *items* by ``angle`` degrees."""
    for i, obj in enumerate(items):
        if i % 2 == 1:
            rotate_item(obj, angle)
