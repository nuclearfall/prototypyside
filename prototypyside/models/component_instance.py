from PySide6.QtWidgets import QGraphicsItem
from PySide6.QtCore import Signal


from prototypyside.models.game_component_template import GameComponentTemplate
from prototypyside.models.game_component_elements import TextElement, ImageElement

class GameComponentInstance(QGraphicsItem):
    update_cache = Signal()
    def __init__(self, template, data, rect, parent=None):
        super().__init__(parent)
        self.template = template
        self.data = data  # dict of merged text/image fields, etc.
        self.rect = rect  # QRectF (the slot this fills)
        # Optionally: pre-render or resolve any resources for efficiency
        self._cache_image = None
        # Listen to the template's update signal
        self.template.updated.connect(self.invalidate_cache)

    def boundingRect(self):
        return self.rect

    def paint(self, painter, option, widget=None):
        if self._cache_image is None:
            self._cache_image = self._render_to_image(dpi=self._dpi)

        # self.rect is QRectF(x, y, width, height) in logical units (e.g., inches)
        painter.drawImage(self.rect, self._cache_image)
            
    def _render_to_image(self, dpi):
        w = parse_dimension(self._width_str, dpi)
        h = parse_dimension(self._height_str, dpi)
        image = QImage(int(w), int(h), QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)

        img_painter = QPainter(image)
        img_painter.scale(dpi, dpi)  # So child items also use logical units
        self._render_elements(img_painter)  # All done in logical units
        img_painter.end()

        return image

    def invalidate_cache(self):
        self._cache_image = None
        self.update()

    # Optional: add serialization if needed
    def to_dict(self):
        return {
            "template_pid": self.template.pid,
            "rect": {
                "x": self.rect.x(),
                "y": self.rect.y(),
                "width": self.rect.width(),
                "height": self.rect.height(),
            },
            "data": self.data
        }


