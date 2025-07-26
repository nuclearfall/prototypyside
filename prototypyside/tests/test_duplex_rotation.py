import os
import sys

# Offscreen platform for Qt
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtWidgets import QApplication, QGraphicsRectItem

from prototypyside.utils.graphics_item_helpers import rotate_item, rotate_every_other

app = QApplication(sys.argv)

def test_rotate_item_sets_rotation():
    item = QGraphicsRectItem(0, 0, 10, 10)
    rotate_item(item, 180)
    assert int(item.rotation()) == 180

def test_rotate_every_other_rotates_second():
    first = QGraphicsRectItem(0, 0, 5, 5)
    second = QGraphicsRectItem(0, 0, 5, 5)
    rotate_every_other([first, second])
    assert int(first.rotation()) == 0
    assert int(second.rotation()) == 180
