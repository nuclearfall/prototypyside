# text_element.py
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF, QSize, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QPen,
    QBrush,
    QTextDocument,
    QTextOption,
    QPainter,
    QPixmap,
    QPalette,
    QAbstractTextDocumentLayout,
    QTextCursor, 
    QTextBlockFormat
)
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject
from prototypyside.utils.qt_helpers import qfont_from_string
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.units.unit_str_helpers import geometry_with_px_rect, geometry_with_px_pos
from prototypyside.config import HandleType, ALIGNMENT_MAP
from prototypyside.utils.proto_helpers import get_prefix, resolve_pid
from prototypyside.models.component_element import ComponentElement


class TextElement(ComponentElement):
    _subclass_serializable = {
        # maps attribute name -> (dict_key, from_fn, to_fn, default)
        "font": (
            "font",
            qfont_from_string,
            lambda f: f.toString(),
            QFont("Arial", 12)
        )
    }

    def __init__(self, pid, geometry: UnitStrGeometry, tpid = None, 
            parent: Optional[QGraphicsObject] = None, name: str = None):
        super().__init__(pid, geometry, tpid, parent, name)

        self._font = QFont("Arial", 12)
        self._content = "Sample Text"

    # --- Text-specific Property Getters and Setters ---
    @property
    def font(self) -> QFont:
        return self._font

    @font.setter
    def font(self, value: QFont):
        if self._font != value:
            self.prepareGeometryChange() # Font change might change layout/size
            self._font = value
            self.item_changed.emit()
            self.update()

    # --- End Text-specific Property Getters and Setters ---

    def to_dict(self):
        data = super().to_dict()  # ← include base fields
        for attr, (key, _, to_fn, default) in self._subclass_serializable.items():
            val = getattr(self, f"_{attr}", default)
            data[key] = to_fn(val)
        return data

    @classmethod
    def from_dict(cls, data: dict, registry, is_clone=False):
        inst = super().from_dict(data, registry, is_clone)
        inst.pid = resolve_pid("te") if is_clone else data["pid"]
        for attr, (key, from_fn, _, default) in cls._subclass_serializable.items():
            raw = data.get(key, default)
            # We want to set content using the content setter.
            if hasattr(inst, f"{attr}"):
                setattr(inst, f"{attr}", from_fn(raw))
            else:
                setattr(inst, f"_{attr}", from_fn(raw))

        return inst


    # def paint(self, painter, option, widget=None):
    #     painter.save()
    #     # Convert geometry to px at current DPI
    #     rect = self.geometry.to("px", dpi=self.dpi).rect
    #     print(f'Rect dimensions are {self.geometry.px.rect} at {self.dpi}')

    #     # Set font size using DPI scaling
    #     font = QFont(self.font)
    #     font.setPointSize(int(font.pointSizeF() * self.dpi / 72.0))  # Convert pt → px
    #     painter.setFont(font)

    #     # Set color
    #     painter.setPen(QPen(self.color))

    #     # Draw unformatted text
    #     painter.drawText(rect, self.alignment_flags, self.content or "")

    #     painter.restore()


    def paint(self, painter, option, widget=None):
        painter.save()

        # Render geometry as pixels at given DPI
        rect = self.geometry.to("px", dpi=self.dpi).rect

        # Build the document
        doc = QTextDocument()

        # FONT SIZE MUST BE SET IN PIXELS — because painter is scaled to px
        font = QFont(self.font)
        font.setPixelSize(int(font.pointSizeF() * self.dpi / 72.0))  # px = pt * dpi / 72
        doc.setDefaultFont(font)

        # Text styling
        ctx = QAbstractTextDocumentLayout.PaintContext()
        ctx.palette.setColor(QPalette.Text, self.color)
        doc.setDocumentMargin(0)
        doc.setDefaultTextOption(QTextOption(self.alignment_flags))
        doc.setPlainText(self.content or "")
        doc.setTextWidth(rect.width())

        # Clip if text overflows rect
        if doc.size().height() > rect.height():
            painter.setClipRect(rect)

        # Paint at correct position in px space
        painter.translate(rect.topLeft())
        doc.documentLayout().draw(painter, ctx)

        painter.restore()

