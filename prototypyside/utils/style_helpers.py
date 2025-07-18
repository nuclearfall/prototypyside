# style_helpers
from PySide6.QtCore import Qt

def split_alignment(alignment: Qt.AlignmentFlag):
    # mask off just the horizontal bits
    horiz = alignment & (Qt.AlignLeft | Qt.AlignHCenter | Qt.AlignRight)
    # default to left if nothing found
    if not horiz:
        horiz = Qt.AlignLeft

    # mask off just the vertical bits
    vert = alignment & (Qt.AlignTop | Qt.AlignVCenter | Qt.AlignBottom)
    # default to top if nothing found
    if not vert:
        vert = Qt.AlignTop

    return horiz, vert

def combine_alignment(a1, a2):
    if isinstance(a1, Qt.Alignment) and isinstance(a2, Qt.Alignment)
        return a1 | a2
