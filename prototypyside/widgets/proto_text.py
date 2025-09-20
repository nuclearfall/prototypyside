# proto_text_item.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QObject, QRectF, QPointF, Qt
# --- NEW: Import QTextDocument for reliable height calculation ---
from PySide6.QtGui import QPainter, QTextOption, QTextLayout, QFontMetricsF, QTextDocument, QTextCursor, QTextCharFormat, QBrush
from PySide6.QtWidgets import QGraphicsObject
from prototypyside.config import HMAP, VMAP, HMAP_REV, VMAP_REV
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.units.unit_str_font import UnitStrFont


class VAlignOffset:
    _MAP = {
        Qt.AlignTop:      lambda ch, h: 0.0,
        Qt.AlignVCenter:  lambda ch, h: (ch - h) * 0.5,
        Qt.AlignBottom:   lambda ch, h: (ch - h),
        Qt.AlignBaseline: lambda ch, h: (ch - h),  # treat as Bottom; adjust if desired
    }

    @classmethod
    def _vertical_flag(cls, align: Qt.Alignment) -> Qt.Alignment:
        # Mask out horizontal bits; default to AlignTop if unknown
        vflag = Qt.Alignment(int(align) & int(Qt.AlignVertical_Mask))
        return vflag if vflag in cls._MAP else Qt.AlignTop

    @classmethod
    def fn_for(cls, align: Qt.Alignment):
        """Return the (clip_h, content_h) -> y_offset function for this vertical alignment."""
        return cls._MAP[cls._vertical_flag(align)]

    @classmethod
    def offset(cls,
               align: Qt.Alignment,
               clip_rect_or_h,
               content_height: float,
               *,
               clamp: bool = False) -> float:
        """
        Compute y-offset inside clip for the given vertical alignment.
        - clip_rect_or_h: QRectF or float height (px)
        - content_height: height of the content (px)
        - clamp: if True, prevents negative/overflow offsets (pins within [0, clip_h - content_h])
        """
        clip_h = clip_rect_or_h.height() if isinstance(clip_rect_or_h, QRectF) else float(clip_rect_or_h)
        off = cls.fn_for(align)(clip_h, float(content_height))
        if clamp:
            # keep content top/bottom inside the clip if it's smaller than the clip
            low = 0.0
            high = max(0.0, clip_h - content_height)
            off = min(max(off, low), high)
        return float(off)

    # Convenience accessors (optional)
    @classmethod
    def top(cls): return cls._MAP[Qt.AlignTop]
    @classmethod
    def center(cls): return cls._MAP[Qt.AlignVCenter]
    @classmethod
    def bottom(cls): return cls._MAP[Qt.AlignBottom]
    @classmethod
    def baseline(cls): return cls._MAP[Qt.AlignBaseline]

@dataclass
class TextDocResult:
    document: QTextDocument         # the document returned
    doc_geom: UnitStrGeometry   # the natural (laid-out) geom
    has_overflow: bool          


class ProtoText(QGraphicsObject):
    @staticmethod
    def is_expanded(geometry: "UnitStrGeometry", text_doc_result: "TextDocResult") -> bool:
        """
        Return True if the given geometry matches the overset geometry,
        i.e. caller is treating the text element as expanded.
        """
        return geometry == text_doc_result.doc_geom

    @classmethod
    def document(cls, text_element: ComponentTextElement, ctx) -> TextRenderResult:
        dpi, unit = ctx.dpi, ctx.unit

        geom = text_element.geometry
        frame_h, frame_w = geom.size_tuple()
        frame_x, frame_y = geom.pos_tuple()

        content = text_element.content or else ""
        doc = QTextDocument(content)

        # ---- Build font & options ----
        qfont = text_element.font.to(unit, dpi=dpi).qfont
        doc.setDefaultFont(qfont)

        # Convert padding to px for the document margin
        pad_px = text_element.padding.to("px", dpi=dpi) if text_element.padding else 0.0
        doc.setDocumentMargin(pad_px)

        opt = QTextOption()
        opt.setWrapMode(text_element.wrap_mode)   # e.g., QTextOption.WordWrap
        opt.setAlignment(text_element.h_align)    # Qt.AlignLeft/Right/Center
        doc.setDefaultTextOption(opt)

        # Apply text color to entire document (plain text path)
        cursor = QTextCursor(doc)
        cursor.select(QTextCursor.Document)
        fmt = QTextCharFormat()
        fmt.setForeground(QBrush(text_element.color))
        cursor.mergeCharFormat(fmt)

        # ---- Convert width for QTextDocument layout ----
        frame_w_px = frame_w.to("px", dpi=dpi)
        # we use these exactly once to set the frame_width and compare height
        doc.setTextWidth(frame_w_px)

        # ---- Convert QTextDocument height back to UnitStr immediately ----
        natural_h = UnitStr(doc.size().height(), unit="px", dpi=dpi)
        # compare UnitStr values. All values are compared in physical inches
        has_overflow = natural_h > frame_h

        if has_overflow:
            frame_h = natural_h

        doc_geom = UnitStrGeometry(
            width=frame_w,
            height=frame_h,
            x=frame_x,
            y=frame_y,
            dpi=dpi
        )

        return TextDocResult(
            document=doc,
            geom=doc_geom,
            has_overflow=has_overflow
        )
