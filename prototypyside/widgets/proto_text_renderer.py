# proto_text_item.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QObject, QRectF, QPointF, Qt
# --- NEW: Import QTextDocument for reliable height calculation ---
from PySide6.QtGui import QPainter, QTextOption, QTextLayout, QFontMetricsF, QTextDocument, QTextCursor, QTextCharFormat, QBrush
from PySide6.QtWidgets import QGraphicsObject

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
class TextRenderResult:
    frame_rect: QRectF        # the actual rect we painted into (clipped height)
    overset_rect: QRectF      # the natural (laid-out) rect; height may exceed frame
    has_overflow: bool

class ProtoTextRenderer(QObject):
    def __init__(
        self,
        dpi: float,
        ldpi: float,
        font: UnitStrFont,
        h_align: Qt.AlignmentFlag = Qt.AlignLeft,
        v_align: Qt.AlignmentFlag = Qt.AlignTop,
        wrap_mode: QTextOption.WrapMode = QTextOption.WrapAtWordBoundaryOrAnywhere,
        has_overflow: bool = False,
        max_lines: Optional[int] = None,
        color: Optional[QColor] = None
    ) -> None:
        super().__init__()
        self.dpi = float(dpi)
        self.ldpi = float(ldpi)
        self._font: UnitStrFont = font
        self._frame = QRectF(0, 0, 0, 0)
        self.text: str = ""
        self.h_align = h_align
        self.v_align = v_align
        self.wrap_mode = wrap_mode
        self.clip_overflow = None
        self.max_lines = max_lines
        self._color: Optional[QColor] = color
        self.overset_rect = None
        self._has_overflow = has_overflow
        self._is_expanded = False

    # --- properties ---------------------------------------------------------

    @property
    def is_expanded(self):
        return self._is_expanded
        
    @is_expanded.setter
    def is_expanded(self, state):
        self._is_expanded = state
    
    @property
    def has_overflow(self):
        return self._has_overflow

    @has_overflow.setter
    def has_overflow(self, state: bool) -> None:
        self._has_overflow = bool(state)

    @property
    def can_expand(self):
        return self.has_overflow and not self.is_expanded

    @property
    def font(self) -> UnitStrFont:
        return self._font

    @font.setter
    def font(self, value: UnitStrFont) -> None:
        self._font = value

    # --- core ---------------------------------------------------------------
    def render(self, painter: QPainter, frame: QRectF) -> TextRenderResult:
        """
        Layout & paint plain text into `frame` (local coords). Returns geometry info:
          - If not expanded, we CLIP to `frame` and cap drawing height to frame_h.
          - If expanded, we DO NOT clip (outline should pass overset frame) and we draw full natural height (or max_lines cap).
          - overset_rect always reports the natural laid-out height at the frame's x,y.
        """
        # --- Build document & font (use your px path) ---
        painter.save()
        doc = QTextDocument()
        qfont = self.font.scale(ldpi=self.ldpi, dpi=self.dpi).px.qfont
        doc.setDefaultFont(qfont)
        doc.setPlainText(self.text or "")

        # --- Color (plain text) ---
        if self._color is not None:
            cursor = QTextCursor(doc)
            cursor.select(QTextCursor.Document)
            fmt = QTextCharFormat()
            fmt.setForeground(QBrush(self._color))
            cursor.mergeCharFormat(fmt)

        # --- Text options: wrap + horizontal alignment ---
        opt = QTextOption()
        opt.setWrapMode(self.wrap_mode)  # MUST be QTextOption.WrapMode
        if self.h_align & Qt.AlignHCenter:
            opt.setAlignment(Qt.AlignHCenter)
        elif self.h_align & Qt.AlignRight:
            opt.setAlignment(Qt.AlignRight)
        else:
            opt.setAlignment(Qt.AlignLeft)
        doc.setDefaultTextOption(opt)

        # --- Layout to the frame width ---
        frame_w = max(0.0, float(frame.width()))
        frame_h = max(0.0, float(frame.height()))
        doc.setTextWidth(frame_w)

        # --- Natural laid-out height (may exceed frame) ---
        natural_h = float(doc.size().height())

        # --- Optional line cap against natural height ---
        if self.max_lines and self.max_lines > 0:
            fm = QFontMetricsF(qfont)
            line_h = float(fm.lineSpacing())
            natural_h_capped = min(natural_h, self.max_lines * line_h)
        else:
            natural_h_capped = natural_h

        # --- Decide painted height & clipping based on is_expanded ---
        if self.is_expanded:
            # Outline should have passed the overset frame; draw full natural (or capped) height.
            painted_h = natural_h_capped
            do_clip = False
        else:
            # Respect element bounds strictly: cap to frame_h and clip.
            painted_h = min(natural_h_capped, frame_h)
            do_clip = True

        # --- Overflow detection is against the element-sized frame ---
        self.has_overflow = natural_h > frame_h

        # --- Vertical alignment inside the *frame* (not overset origin) ---
        v_off = VAlignOffset.offset(self.v_align, frame.height(), painted_h, clamp=False)

        # --- Drawing rect (x managed by QTextOption; y offset here) ---
        paint_rect = QRectF(frame.x(), frame.y() + v_off, frame_w, painted_h)

        # --- Paint ---
        # If caller explicitly set clip_overflow, honor it too (but is_expanded wins)
        if do_clip or (self.clip_overflow and not self.is_expanded):
            painter.setClipRect(frame)
        doc.drawContents(painter, paint_rect)
        painter.restore()

        # --- Report overset (natural) rect aligned at the frame's origin ---
        self.overset_rect = QRectF(frame.x(), frame.y(), frame_w, natural_h)

        return TextRenderResult(
            frame_rect=paint_rect,
            overset_rect=self.overset_rect,
            has_overflow=self._has_overflow,
        )

    def measure(self, frame: QRectF) -> Tuple[QRectF, bool, float]:
        """
        Layout text for `frame` width only (no painting) and return:
          (overset_rect, has_overflow, natural_height)
        Uses current font/text/wrap/h_align.
        """
        doc = QTextDocument()
        qfont = self.font.scale(ldpi=self.ldpi, dpi=self.dpi).px.qfont
        doc.setDefaultFont(qfont)
        doc.setPlainText(self.text or "")

        opt = QTextOption()
        opt.setWrapMode(self.wrap_mode)
        if self.h_align & Qt.AlignHCenter:
            opt.setAlignment(Qt.AlignHCenter)
        elif self.h_align & Qt.AlignRight:
            opt.setAlignment(Qt.AlignRight)
        else:
            opt.setAlignment(Qt.AlignLeft)
        doc.setDefaultTextOption(opt)

        frame_w = max(0.0, float(frame.width()))
        frame_h = max(0.0, float(frame.height()))
        doc.setTextWidth(frame_w)
        natural_h = float(doc.size().height())

        has_overflow = natural_h > frame_h
        overset = QRectF(frame.x(), frame.y(), frame_w, natural_h)

        # keep these members consistent with render()
        self.overset_rect = overset
        self._has_overflow = has_overflow
        return overset, has_overflow, natural_h



