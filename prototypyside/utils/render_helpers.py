from PySide6.QtGui import QPixmap, QImage, QPainter
from PySide6.QtCore import QRectF, QSize

def render_scene_to_pixmap(scene, dpi=300, margin=0) -> QPixmap:
    # Determine scene content size
    rect = scene.itemsBoundingRect().adjusted(-margin, -margin, margin, margin)

    # Convert scene units (assume pt) to pixels based on DPI
    width_px = int(rect.width() * dpi / 72)
    height_px = int(rect.height() * dpi / 72)

    image = QImage(width_px, height_px, QImage.Format_ARGB32)
    image.setDotsPerMeterX(int(dpi / 25.4 * 1000))  # dpi → dots/meter
    image.setDotsPerMeterY(int(dpi / 25.4 * 1000))
    image.fill(0)  # Transparent

    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    scene.render(painter, QRectF(0, 0, width_px, height_px), rect)
    painter.end()

    return QPixmap.fromImage(image)
    

def render_scene_to_image(scene, filename: str, dpi: int = 300, margin: int = 0):
    # Get the scene's bounding rect
    rect = scene.itemsBoundingRect().adjusted(-margin, -margin, margin, margin)
    
    # Convert logical units to pixels
    width_px = int(rect.width() * dpi / 72)
    height_px = int(rect.height() * dpi / 72)
    
    image = QImage(width_px, height_px, QImage.Format_ARGB32)
    image.setDotsPerMeterX(int(dpi / 25.4 * 1000))  # DPI to dots/meter
    image.setDotsPerMeterY(int(dpi / 25.4 * 1000))
    image.fill(0)  # Transparent background

    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # Map scene coordinates to image coordinates
    scene.render(painter, QRectF(0, 0, width_px, height_px), rect)
    painter.end()

    image.save(filename)
