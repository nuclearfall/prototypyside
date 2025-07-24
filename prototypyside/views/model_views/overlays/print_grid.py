from PySide6.QtWidgets import QGraphicsItem
from PySide6.QtGui     import QPainter, QPen, QColor
from PySide6.QtCore    import QRectF, Qt

from prototypyside.utils.units.unit_str import UnitStr

# You’ll need your UnitStr class in scope:
# from yourpackage.unit_str import UnitStr

class PrintLines(QGraphicsItem):
    def __init__(
        self,
        bleed_size: UnitStr = UnitStr("0.125in", dpi=300),
        bleed_color: QColor = QColor(0, 0, 0, 127),      # 50%-alpha black
        cut_color:   QColor = QColor(Qt.red),
        safe_color:  QColor = QColor(Qt.yellow),
        parent:      QGraphicsItem = None
    ):
        super().__init__(parent)
        self.bleed_size   = bleed_size
        self.bleed_color  = bleed_color
        self.cut_color    = cut_color
        self.safe_color   = safe_color

        self.show_bleed     = True
        self.show_cut_line  = True
        self.show_safe_area = True

        # draw on top of everything in the component
        self.setZValue( 1e6 )

    def boundingRect(self) -> QRectF:
        """Expand the parent’s rect by the bleed on all sides"""
        pr = self.parentItem().boundingRect()
        dpi = getattr(self.parentItem(), "dpi", 300)
        bleed_px = float(self.bleed_size.to("px", dpi=dpi))
        return pr.adjusted(-bleed_px, -bleed_px, bleed_px, bleed_px)

    def paint(self, painter: QPainter, option, widget=None):
        pr = self.parentItem().boundingRect()
        dpi = getattr(self.parentItem(), "dpi", 300)
        bpx = float(self.bleed_size.to("px", dpi=dpi))

        # 1) Bleed boundary (outer rect)
        if self.show_bleed:
            bleed_rect = pr.adjusted(-bpx, -bpx, bpx, bpx)
            pen = QPen(self.bleed_color)
            pen.setWidthF(1.0)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(bleed_rect)

        # 2) Cut line (component edge)
        if self.show_cut_line:
            pen = QPen(self.cut_color)
            pen.setWidthF(1.0)
            painter.setPen(pen)
            painter.drawRect(pr)

        # 3) Safe-print area (inner dotted)
        if self.show_safe_area:
            safe_rect = pr.adjusted(bpx, bpx, -bpx, -bpx)
            pen = QPen(self.safe_color)
            pen.setStyle(Qt.DotLine)
            pen.setWidthF(1.0)
            painter.setPen(pen)
            painter.drawRect(safe_rect)

    # ——— Toggle methods ———

    def toggle_bleed(self, show: bool = None):
        """Show/hide the bleed outline."""
        self.show_bleed = (not self.show_bleed) if show is None else show
        self.update()

    def toggle_cut_line(self, show: bool = None):
        """Show/hide the cut (red) line."""
        self.show_cut_line = (not self.show_cut_line) if show is None else show
        self.update()

    def toggle_safe_area(self, show: bool = None):
        """Show/hide the safe (dotted yellow) area."""
        self.show_safe_area = (not self.show_safe_area) if show is None else show
        self.update()
