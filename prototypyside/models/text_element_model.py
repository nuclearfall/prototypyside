# from PySide6.QtCore import Qt, QRectF, QPointF, QSize, Signal, QObject
# from PySide6.QtGui import (QColor, QFont, QPen, QBrush, QTextDocument, QTextOption, QPainter, QPixmap, QPalette,
#             QAbstractTextDocumentLayout)
# from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject

from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry

from prototypyside.models.component_element import ComponentElement

class TextElement(ComponentElement):
    font: str 
    content:str
    super().__init__(self, pid, geometry)




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
        for attr, (key, from_fn, _, default) in cls._subclass_serializable.items():
            raw = data.get(key, default)
            # We want to set content using the content setter.
            if hasattr(inst, f"{attr}"):
                setattr(inst, f"{attr}", from_fn(raw))
            else:
                setattr(inst, f"_{attr}", from_fn(raw))
        return inst

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)

        rect = self.geometry.to(self.unit, dpi=self.dpi).rect
        painter.save()

        # 1) build the document
        doc = QTextDocument()
        doc.setDefaultFont(self.font)

        # force text color
        ctx = QAbstractTextDocumentLayout.PaintContext()
        ctx.palette.setColor(QPalette.Text, self.color)

        doc.setDocumentMargin(0)
        doc.setDefaultTextOption(QTextOption(self.alignment_flags))
        doc.setPlainText(self.content or "")
        doc.setTextWidth(rect.width())

        # 2) clip if needed
        if doc.size().height() > rect.height():
            painter.setClipRect(rect)

        # 3) translate into position and draw
        painter.translate(rect.topLeft())
        doc.documentLayout().draw(painter, ctx)

        painter.restore()