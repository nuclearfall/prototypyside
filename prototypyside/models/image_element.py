# image_element.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPixmap, QPen, QPainterPath
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsSceneDragDropEvent,
)
from prototypyside.models.component_element import ComponentElement
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.units.unit_str_font import UnitStrFont
from prototypyside.utils.valid_path import ValidPath

class ImageElement(ComponentElement):
    _subclass_serializable = {
        "keep_aspect": ("keep_aspect",
                        lambda x: bool(x),
                        lambda b: b,
                        True),
    }

    def __init__(self,
            proto: ProtoClass,
            pid: str, 
            registry: "ProtoRegistry", 
            geometry: UnitStrGeometry,
            name: Optional[str] = None,  
            parent: Optional[QGraphicsObject] = None
    ):
        super().__init__(
            proto=proto,
            pid=pid,
            registry=registry, 
            geometry=geometry,
            name=name,
            parent=parent
        )
        
        self._pixmap: Optional[QPixmap] = None
        # # _content is handled by ComponentElement
        # self.content = None
        self._v_align = Qt.AlignVCenter
        self._h_align = Qt.AlignHCenter
        
        # Image-specific properties
        self._keep_aspect = True
        self.showPlaceholderText = True

        self.setAcceptDrops(True)

    # --- Image-specific Property Getters and Setters ---
    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, new_content: Optional[str]):
        # Validate/normalize; may return None if invalid/missing
        norm = ValidPath.file(new_content, must_exist=True)

        if not norm:
            # Only clear when content is actually being set to "no image"
            self._content = None
            self._pixmap = None
        else:
            # If the path changed or pixmap isn't loaded yet, (re)load it
            if norm != self._content or self._pixmap is None:
                pm = QPixmap(norm)
                self._pixmap = pm if not pm.isNull() else None
            # Always keep _content in sync with the normalized path
            self._content = norm

        self.item_changed.emit()
        self.update()

    @property
    def keep_aspect(self) -> bool:
        return self._keep_aspect

    @keep_aspect.setter
    def keep_aspect(self, value: bool):
        if self._keep_aspect != value:
            self._keep_aspect = value
            self.item_changed.emit()
            self.update()

    def render_with_context(self, painter: QPainter, context: RenderContext):
        """Render image with the given context"""
        rect = self.geometry.to("px", dpi=self.dpi).rect
        
        # Rounded-rect clipping
        if hasattr(self, "corner_radius") and self.corner_radius.to("px", dpi=self.dpi) > 0:
            cr = self.corner_radius.to("px", dpi=self.dpi)
            path = QPainterPath()
            path.addRoundedRect(rect, cr, cr)
            painter.setClipPath(path)
        
        # Draw image
        if self._pixmap:
            if self._keep_aspect:
                scaled = self._pixmap.scaled(
                    rect.width(), rect.height(), 
                    Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                # Calculate alignment offsets
                dx = 0
                dy = 0
                
                if self.h_align & Qt.AlignHCenter:
                    dx = (rect.width() - scaled.width()) / 2.0
                elif self.h_align & Qt.AlignRight:
                    dx = rect.width() - scaled.width()
                
                if self.v_align & Qt.AlignVCenter:
                    dy = (rect.height() - scaled.height()) / 2.0
                elif self.v_align & Qt.AlignBottom:
                    dy = rect.height() - scaled.height()
                
                painter.drawPixmap(rect.topLeft() + QPointF(dx, dy), scaled)
            else:
                painter.drawPixmap(
                    rect.topLeft(),
                    self._pixmap.scaled(rect.size().toSize(), 
                                       Qt.IgnoreAspectRatio, 
                                       Qt.SmoothTransformation)
                )
        elif self.showPlaceholderText and context.is_gui:
            # Draw placeholder text
            painter.save()
            painter.setPen(QPen(Qt.darkGray))
            font = UnitStrFont(family="Arial", size=10, italic=True)
            font = font.scale(ldpi=72, dpi=self.dpi).pt.qfont
            painter.setFont(font)
            painter.drawText(rect, (self.h_align | self.v_align), 
                            "Drop Image\nor Double Click to Set")
            painter.restore()
        
        # Remove clipping
        painter.setClipping(False)
        
        # Draw border if needed
        if hasattr(super(), 'paint_border'):
            super().paint_border(painter, rect)

    def paint(self, painter: QPainter, option, widget=None):
        """
        Paints an image inside the bounding rect, respecting aspect ratio and logical units.
        Always draws the border *after* the content so it sits on top.
        """
        rect = self.geometry.to("px", dpi=self.dpi).rect
        size = self.geometry.to("px", dpi=self.dpi).size
        w, h = size.width(), size.height()

        # Rounded-rect clipping (independent of border)
        if hasattr(self, "corner_radius") and self.corner_radius.to("px", dpi=self.dpi) > 0:
            cr = self.corner_radius.to("px", dpi=self.dpi)
            path = QPainterPath()
            path.addRoundedRect(rect, cr, cr)
            painter.setClipPath(path)

        # --- Image ---
        if self._pixmap:
            if self._keep_aspect:
                scaled = self._pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)

                # Horizontal offset by h_align
                if self.h_align & Qt.AlignHCenter:
                    dx = (rect.width() - scaled.width()) / 2.0
                elif self.h_align & Qt.AlignRight:
                    dx = rect.width() - scaled.width()
                else:  # default / AlignLeft
                    dx = 0.0

                # Vertical offset by v_align
                if self.v_align & Qt.AlignVCenter:
                    dy = (rect.height() - scaled.height()) / 2.0
                elif self.v_align & Qt.AlignBottom:
                    dy = rect.height() - scaled.height()
                else:  # default / AlignTop
                    dy = 0.0

                painter.drawPixmap(rect.topLeft() + QPointF(dx, dy), scaled)
            else:
                painter.drawPixmap(
                    rect.topLeft(),
                    self._pixmap.scaled(size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                )

        # --- Placeholder text (before border) ---
        elif self.showPlaceholderText:
            painter.save()
            painter.setPen(QPen(Qt.darkGray))
            #font = painter.font()
            ustr_font = UnitStrFont(family="Arial", size=10, italic=True)
            font = ustr_font.scale(ldpi=72, dpi=self.dpi).pt.qfont
            # font.setPixelSize(int(10 * self._dpi / self.ldpi))
            font.setItalic(True)

            painter.setFont(font)

            painter.drawText(rect, (self.h_align | self.v_align), 
                "Drop Image\nor Double Click to Set")
            painter.restore()

        # Remove clipping before drawing border
        painter.setClipping(False)

        # --- Border on top (if any) ---
        super().paint(painter, option, widget)


    def to_dict(self):
        data = super().to_dict()  # ← include base fields
        for attr, (key, _, to_fn, default) in self._subclass_serializable.items():
            val = getattr(self, f"_{attr}", default)
            data[key] = to_fn(val)

        return data
        
    @classmethod
    def from_dict(cls, data: dict, registry):
        inst = super().from_dict(data, registry=registry)
        for attr, (key, from_fn, _, default) in cls._subclass_serializable.items():
            raw = data.get(key, default)
            if hasattr(inst, f"{attr}"):
                setattr(inst, f"{attr}", from_fn(raw))
            else:
                setattr(inst, f"_{attr}", from_fn(raw))
        content = data.get("content", None)
        inst.content = content
        return inst

   
    def render_content(self, painter: QPainter, context: RenderContext, rect: QRectF):
        """
        Render image content based on the rendering context
        """
        # Apply rounded rect clipping if needed
        if hasattr(self, "corner_radius") and self.corner_radius.to("px", dpi=self.dpi) > 0:
            cr = self.corner_radius.to("px", dpi=self.dpi)
            path = QPainterPath()
            path.addRoundedRect(rect, cr, cr)
            painter.setClipPath(path)
        
        # Draw image or placeholder
        if self._pixmap:
            self._draw_image(painter, rect)
        elif context.is_gui and self.showPlaceholderText:
            self._draw_placeholder(painter, rect)
        
        # Remove clipping
        painter.setClipping(False)
    
    def _draw_image(self, painter: QPainter, rect: QRectF):
        """
        Draw the actual image with proper alignment and aspect ratio
        """
        if self._keep_aspect:
            scaled = self._pixmap.scaled(
                rect.width(), rect.height(), 
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            
            # Calculate alignment offsets
            dx = 0
            dy = 0
            
            if self.h_align & Qt.AlignHCenter:
                dx = (rect.width() - scaled.width()) / 2.0
            elif self.h_align & Qt.AlignRight:
                dx = rect.width() - scaled.width()
            
            if self.v_align & Qt.AlignVCenter:
                dy = (rect.height() - scaled.height()) / 2.0
            elif self.v_align & Qt.AlignBottom:
                dy = rect.height() - scaled.height()
            
            painter.drawPixmap(rect.topLeft() + QPointF(dx, dy), scaled)
        else:
            painter.drawPixmap(
                rect.topLeft(),
                self._pixmap.scaled(rect.size().toSize(), 
                                   Qt.IgnoreAspectRatio, 
                                   Qt.SmoothTransformation)
            )
    
    def _draw_placeholder(self, painter: QPainter, rect: QRectF):
        """
        Draw placeholder text
        """
        painter.save()
        painter.setPen(QPen(Qt.darkGray))
        font = UnitStrFont(family="Arial", size=10, italic=True)
        font = font.scale(ldpi=72, dpi=self.dpi).pt.qfont
        painter.setFont(font)
        painter.drawText(rect, (self.h_align | self.v_align), 
                        "Drop Image\nor Double Click to Set")
        painter.restore()

    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0]
            file_path = url.toLocalFile()
            if file_path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif")):
                self.content = file_path
            event.acceptProposedAction()

    def mouseDoubleClickEvent(self, event):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(None, "Select Image", "", "Images (*.png *.jpg *.bmp *.gif)")
        if path:
            self.content = path
            
