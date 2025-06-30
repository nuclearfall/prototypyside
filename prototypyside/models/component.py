from typing import Optional
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QStyleOptionGraphicsItem
from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QPageSize, QPainter, QPixmap, QColor, QImage, QPen, QBrush
from prototypyside.utils.unit_converter import from_px
from prototypyside.models.component_template import ComponentTemplate
from prototypyside.models.component_elements import TextElement, ImageElement
from prototypyside.utils.unit_str import UnitStr

class Component(ComponentTemplate):
    update_cache = Signal()
    def __init__(self, pid, slot, template, parent=None, static=False, row_data=None):
        super().__init__(parent)
        self._pid = pid
        self._cache_image = None
        self._slot = slot
        self._template = template
        self._dpi = self._template.dpi
        self._unit = self._template.unit
        self._width = self._template.width
        self._height = self._template.height
        self.static = static
        self._rect = self.boundingRect()
        self._cache_image = None 
        # Listen to the template's update signal
        self._template.template_changed.connect(self.invalidate_cache)

    def boundingRect(self):
        return QRectF(0, 0, self.width_px, self.height_px)

    @property
    def pid(self) -> str:
        return self._pid

    @pid.setter
    def pid(self, value):
        self._pid = value
        self._template_changed.emit()

    @property
    def width_px(self) -> float:
        return self.width.to("px", dpi=self._dpi)

    @property
    def height_px(self) -> float:
        return self.height.to("px", dpi=self._dpi)

    @property
    def width(self) -> UnitStr:
        return self._width

    @width.setter
    def width(self, value):
        if isinstance(value, UnitStr):
            self._width = value
        else:
            self._width = UnitStr(value, dpi=self._dpi)
        self._template_changed.emit()

    @property
    def height(self) -> UnitStr:
        return self._height

    @height.setter
    def height(self, value):
        if isinstance(value, UnitStr):
            self._height = value
        else:
            self._height = UnitStr(value, dpi=self._dpi)
        self._template_changed.emit()

    @property
    def content(self) -> Optional[str]:
        return self._content

    @content.setter
    def content(self, content: str):
        self._content = content
        # self.element_changed.emit()
        self.update()

    @property
    def unit(self):
        return self._unit

    @property
    def rect(self):
        # Always returns rect in px, local coordinates (0,0)
        return QRectF(
            0, 0,
            self._width.to("px", self._dpi),
            self._height.to("px", self._dpi)
        )

    @rect.setter
    def rect(self, qrectf: QRectF):
        # Accepts a QRectF in px; updates logical size, but never position!
        self.prepareGeometryChange()
        self._width = UnitStr(qrectf.width() / self._dpi, unit="in", dpi=self._dpi)
        self._height = UnitStr(qrectf.height() / self._dpi, unit="in", dpi=self._dpi)
        self.element_changed.emit()
        self.update() 

    def paint(self, painter, option, widget=None):
        print("Time to start painting")
        if self._cache_image is None:
            self._cache_image = self._render_to_image(dpi=self._dpi)

        # self.rect is QRectF(x, y, width, height) in logical units (e.g., inches)
        painter.drawImage(self.rect, self._cache_image)
            
    def _render_to_image(self, dpi):
        w = self._width.to("px", dpi)
        h = self._height.to("px", dpi)
        image = QImage(int(w), int(h), QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)

        img_painter = QPainter(image)
        img_painter.scale(dpi, dpi)  # So child items also use logical units
        self._render_elements(img_painter)  # All done in logical units
        img_painter.end()

        return image


    # ---------------------------------------------------------------------
    # private helpers
    # ---------------------------------------------------------------------
    def _render_elements(self, painter: QPainter) -> None:
        """
        Paint every element that lives in ``self.elements`` onto *painter*.

        * The painter has already been scaled so that **1 logical unit
          (inch, mm, etc.) == 1 DPI-scaled pixel**, therefore element
          coordinates/rects can be used directly. :contentReference[oaicite:0]{index=0}
        * Elements must be drawn in z-order (lowest first) to match what the
          live QGraphicsScene does. :contentReference[oaicite:1]{index=1}
        * Each element’s own ``paint`` routine is reused so we don’t have to
          re-implement text/image logic here.  A throw-away
          ``QStyleOptionGraphicsItem`` is sufficient for most custom
          QGraphicsItems.

        Parameters
        ----------
        painter : QPainter
            The QPainter already set up by ``_render_to_image``.
        """
        # A single option object is fine – its values are rarely inspected by
        # custom items, but create one per element if you need per-item state.
        option = QStyleOptionGraphicsItem()

        # 1.  Render back-to-front, exactly like the scene does.
        for element in sorted(self.template.elements, key=lambda e: e.zValue()):
            painter.save()

            # 2.  Position & orientation (both expressed in logical units).
            pos = element.pos()              # QPointF
            painter.translate(pos.x(), pos.y())

            rotation = getattr(element, "rotation", lambda: 0)()
            if rotation:
                painter.rotate(rotation)

            # 3.  Delegate the actual drawing to the element itself.
            element.paint(painter, option, widget=None)

            painter.restore()

    def invalidate_cache(self):
        self._cache_image = None
        self.update()

    def merge_csv_row(self):
        """
        Updates elements with values from csv_row, only if their name is a data binding.
        If the element already has static content, it is left unchanged unless overridden by csv data.
        """
        for element in self._template.elements:
            if element.name.startswith("@"):
                col = element.name
                if col in csv_row:
                    value = csv_row[col]
                    setattr(element, "content", value)


    
