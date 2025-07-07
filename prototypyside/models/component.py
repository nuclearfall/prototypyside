from typing import Optional
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QStyleOptionGraphicsItem
from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QPageSize, QPainter, QPixmap, QColor, QImage, QPen, QBrush
from prototypyside.utils.unit_converter import from_px
from prototypyside.models.component_template import ComponentTemplate
from prototypyside.models.component_elements import TextElement, ImageElement
from prototypyside.utils.unit_str import UnitStr
from prototypyside.utils.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.ustr_helpers import with_rect, with_pos

class Component:
    update_cache = Signal()
    def __init__(self, pid, slot, template, parent=None, is_static=False, row_data=None):
        super().__init__(parent)
        self._pid = pid
        self._cache_image = None
        self._slot = slot
        self._content = template
        self._dpi = template.dpi
        self._unit = template.unit
        self._geometry = template._geometry
        self.is_static = is_static
        self._cache_image = None
        # Listen to the template's update signal
        self._content.template_changed.connect(self.invalidate_cache)

    # These three methods must be defined for each object.
    def boundingRect(self) -> QRectF:
        return self._geometry.to("px", dpi=self._dpi).rect

    def setRect(self, new_rect: QRectF):
        self.prepareGeometryChange()
        self._geometry = with_rect(self._geometry, new_rect)
        self.template_changed.emit()
        self.update()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        if change == QGraphicsItem.ItemPositionChange:
            self._geometry = with_pos(self._geometry, value)
            self.template_changed.emit()
        return super().itemChange(change, value)

    @property
    def pid(self) -> str:
        return self._pid

    @pid.setter
    def pid(self, value):
        self._pid = value
        self._content_changed.emit()

    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, template):
        self._content = template
        self.render_to_image(dpi=self._dpi)

    def paint(self, painter, option, widget=None):
        if self._cache_image is None:
            self._cache_image = self._render_to_image(dpi=self._dpi)

        painter.drawImage(self.boundingRect(), self._cache_image)

    def _render_to_image(self, dpi):
        rect = self.boundingRect()
        w, h = int(rect.width()), int(rect.height())

        option = QStyleOptionGraphicsItem()
        image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)

        img_painter = QPainter(image)
        img_painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        # Set coordinate system so 1 px in logical unit equals 1 px in image
        img_painter.translate(-rect.topLeft())  # Align drawing to image origin

        # 1. Render the template background + border
        self.content.paint(img_painter, option, widget=None)

        # 2. Render all elements (manual call since they’re not in a scene)
        for element in sorted(self.content.elements, key=lambda e: e.zValue()):
            img_painter.save()
            element.paint(img_painter, option, widget=None)
            img_painter.restore()

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
        self.content.paint(painter, option, widget=None)
        for element in sorted(self.content.elements, key=lambda e: e.zValue()):
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

    def _render_background(self, painter: QPainter):
        """
        Draw the template background color or image.
        This assumes the template may define a background_color or background_image.
        """
        rect = QRectF(0, 0, self._width.to("float"), self._height.to("float"))

        bg_color = getattr(self._content, "background_color", None)
        bg_image_path = getattr(self._content, "background_image", None)

        if bg_color:
            painter.fillRect(rect, QColor(bg_color))

        if bg_image_path:
            pixmap = QPixmap(bg_image_path)
            painter.drawPixmap(rect, pixmap, pixmap.rect())

    def invalidate_cache(self):
        self._cache_image = None
        self.update()

    def merge_csv_row(self):
        """
        Updates elements with values from csv_row, only if their name is a data binding.
        If the element already has static content, it is left unchanged unless overridden by csv data.
        """
        for element in self._content.elements:
            if element.name.startswith("@"):
                col = element.name
                if col in csv_row:
                    value = csv_row[col]
                    setattr(element, "content", value)

    def apply_data(row):
        # Update child elements to use new data
        for element in self.content.elements():
            if hasattr(element, "content",):
                element.update_from_merge_data(merge_data)
        self.update()
