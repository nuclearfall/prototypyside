# proto_text_item.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QObject, QRectF, QPointF, Qt
# --- NEW: Import QTextDocument for reliable height calculation ---

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
    document: QTextDocument     # the document to be rendered
    overset_rect: QRectF        # the natural (laid-out) rect; height may exceed frame
    has_overflow: bool


class ProtoText(QGraphicsObject):
    """
    Paints and (optionally) lets an external overlay edit the SAME QTextDocument.
    - Persistent QTextDocument lives here.
    - `content` is plain-text (use toHtml/toPlainText directly on .document if needed).
    - Horizontal alignment, wrap, padding, color, max_lines are respected.
    """
    def __init__(
        self,
        font: UnitStrFont,
        geometry: UnitStrGeometry,
        h_align: Qt.AlignmentFlag = Qt.AlignLeft,
        v_align: Qt.AlignmentFlag = Qt.AlignTop,
        padding: UnitStr = UnitStr(0),
        wrap_mode: QTextOption.WrapMode = QTextOption.WrapAtWordBoundaryOrAnywhere,
        max_lines: Optional[int] = None,
        content: str = None,
        color: Optional[QColor] = Qt.black,
        context: Optional[bool] = None
    ) -> None:
        super().__init__()
        self._font: UnitStrFont = font
        self.ctx = context
        self._padding: UnitStr = padding or UnitStr("0 pt", dpi=context.dpi)
        self._color: Optional[QColor] = color
        self._v_align = v_align
        self._h_align = h_align
        self._wrap_mode = wrap_mode

        self._is_expanded = False
        self._has_overflow = False
        self.overset_rect: Optional[QRectF] = None

        # Plain-text content (mirrors the doc; property below writes to _doc)
        self._content_cache = ""  # for fast change checks

    # ------------------ public API ------------------

    @property
    def document(self) -> QTextDocument:
        """Expose the SAME document used for rendering; attach this to your editor."""
        return self._doc

    @property
    def content(self) -> str:
        """Plain-text content of the document."""
        return self._doc.toPlainText()

    @content.setter
    def content(self, text: str) -> None:
        text = text or ""
        if text != self._doc.toPlainText():
            self._doc.setPlainText(text)
            self._content_cache = text
            # content change may affect layout height
            # (no need to mark typography/options dirty)
        # If color is active, reapply so new text uses it.

    @property
    def font(self) -> UnitStrFont:
        return self._font

    @font.setter
    def font(self, value: UnitStrFont) -> None:
        self._font = value

    @property
    def padding(self) -> UnitStr:
        return self._padding

    @padding.setter
    def padding(self, val: UnitStr) -> None:
        self._padding = val
        self._typography_dirty = True  # affects document margin

    @property
    def padding_px(self) -> float:
        return self._padding.to("px", dpi=self.dpi)

    @property
    def wrap_mode(self) -> QTextOption.WrapMode:
        return self._wrap_mode

    @wrap_mode.setter
    def wrap_mode(self, mode: QTextOption.WrapMode) -> None:
        if mode != self._wrap_mode:
            self._wrap_mode = mode
            self._options_dirty = True

    @property
    def h_align(self) -> Qt.AlignmentFlag:
        return self._h_align

    @h_align.setter
    def h_align(self, align: Qt.AlignmentFlag) -> None:
        if align != self._h_align:
            self._h_align = align
            self._options_dirty = True

    @property
    def v_align(self) -> Qt.AlignmentFlag:
        return self._v_align

    @v_align.setter
    def v_align(self, align: Qt.AlignmentFlag) -> None:
        self._v_align = align  # used at paint time only

    @property
    def color(self) -> Optional[QColor]:
        return self._color

    @color.setter
    def color(self, c: Optional[QColor]) -> None:
        self._color = c
        self._color_dirty = True

    @property
    def max_lines(self) -> Optional[int]:
        return self._max_lines

    @max_lines.setter
    def max_lines(self, n: Optional[int]) -> None:
        self._max_lines = n

    @property
    def has_overflow(self) -> bool:
        if self.frame:
            frame = self.frame
            frame_w = max(0.0, float(frame.width()))
            frame_h = max(0.0, float(frame.height()))

            # --- Natural laid-out height (may exceed frame) ---
            natural_h = float(self.doc.size().height())

            # --- Overflow detection is against the element-sized frame ---
            return (natural_h > frame_h) or self.is_expanded

    # @has_overflow.setter
    # def has_overflow(self, state: bool) -> None:
    #     self._has_overflow = bool(state)

    @property
    def is_expanded(self) -> bool:
        return self._is_expanded

    @is_expanded.setter
    def is_expanded(self, state: bool) -> None:
        self._is_expanded = bool(state)

    @property
    def can_expand(self):
        return self.has_overflow and not self.is_expanded

    @property
    def text_option(self) -> QTextOption:
        """Optional: expose for toolbars to mirror wrap/alignment."""
        return self._opts

    # ------------------ internal helpers ------------------

    def _apply_options_if_needed(self):
        if not self._options_dirty:
            return
        self._opts.setWrapMode(self._wrap_mode)
        self._opts.setAlignment(self._h_align)
        self._doc.setDefaultTextOption(self._opts)
        self._options_dirty = False

    def _apply_color_if_needed(self):
        if not self._color_dirty or self._color is None:
            return
        cursor = QTextCursor(self._doc)
        cursor.select(QTextCursor.Document)
        fmt = QTextCharFormat()
        fmt.setForeground(QBrush(self._color))
        cursor.mergeCharFormat(fmt)
        self._color_dirty = False

    # --- core ---------------------------------------------------------------
    def render(self, painter, obj, ctx) -> TextRenderResult:
        """
        Layout & paint plain text into `frame` (local coords). Returns geometry info:
          - If not expanded, we CLIP to `frame` and cap drawing height to frame_h.
          - If expanded, we DO NOT clip (outline should pass overset frame) and we draw full natural height (or max_lines cap).
          - overset_rect always reports the natural laid-out height at the frame's x,y.
        """
        # --- Build document & font (use your px path) ---
        self.frame = obj.geometry

        # --- Layout to the frame width ---
        frame_w = frame.to(ctx.unit, dpi=ctx.dpi).size.width()
        frame_h = frame.to(ctx.unit, dpi=ctx.dpi).size.width()
        pos = frame_geom.to(ctx.unit, dpi=ctx.dpi).pos
        self.doc.setTextWidth(frame_w)

        natural_h = float(self.doc.size().height())
        # Setting width and height to pc.USG creates a local rect without a position
        if natural_h > frame_w:
            self.overflow = True
        paint_geom = frame_geom
        # --- Decide painted height & clipping based on is_expanded ---
        else:
            # Respect element bounds strictly: cap to frame_h and clip.
            painted_h = min(natural_h_capped, frame_h)
            do_clip = True

        # --- Vertical alignment inside the *frame* (not overset origin) ---
        # v_off = VAlignOffset.offset(self.v_align, frame.height(), painted_h, clamp=False)

        # --- Drawing rect (x managed by QTextOption; y offset here) ---
        paint_rect = QRectF(0, 0, frame_w, painted_h)
        painter.setClipRect(frame)
        self.overset_rect = QRectF(0, 0, frame_w, natural_h)
        # paint_rect = frame
        # paint_rect = frame
        # paint_rect = QRectF(0, 0, frame_w, painted_h)
        # --- Paint ---
        # If caller explicitly set clip_overflow, honor it too (but is_expanded wins)

        # --- Report overset (natural) rect aligned at the frame's origin ---
        self.overset_rect = QRectF(frame.x(), frame.y(), frame_w, natural_h)

        return TextRenderResult(
            document = self.document,
            overset_rect=self.overset_rect,
            has_overflow=self._has_overflow,
        )
