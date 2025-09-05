# unit_str_font.py  — drop-in replacement (dataclass-safe, UnitStr-based)

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, replace, field
from typing import Iterable, Optional, Tuple, Union, Literal, Protocol
import re

from PySide6.QtGui import QFont, QFontMetricsF, QGuiApplication

# Keep imports aligned with your project layout
from prototypyside.utils.units.unit_str import UnitStr

DEFAULT_DPI = 300.0

_NATURAL_RE = re.compile(
    r"""
    ^\s*
    (?P<family>[^,0-9]+?)                # family name up to a comma/number
    (?:\s*,\s*(?P<fallbacks>[^0-9]+))?   # optional comma-separated fallbacks blob
    \s*
    (?:
        (?P<size>-?\d+(?:\.\d+)?)        # numeric size
        \s*
        (?P<unit>pt|px|in|mm|cm|em)?     # optional unit (added em)
    )?
    (?:\s+(?P<style>italic|oblique))?
    (?:\s+(?P<weight>thin|extra[-\s]?light|light|regular|normal|medium|semi[-\s]?bold|demi[-\s]?bold|bold|extra[-\s]?bold|black))?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

_WEIGHT_MAP = {
    "thin": QFont.Thin,
    "extra light": QFont.ExtraLight,
    "extralight": QFont.ExtraLight,
    "light": QFont.Light,
    "regular": QFont.Normal,
    "normal": QFont.Normal,
    "medium": QFont.Medium,
    "semi bold": QFont.DemiBold,
    "semibold": QFont.DemiBold,
    "demi bold": QFont.DemiBold,
    "demibold": QFont.DemiBold,
    "bold": QFont.Bold,
    "extra bold": QFont.ExtraBold,
    "extrabold": QFont.ExtraBold,
    "black": QFont.Black,
}

Number = Union[int, float, str, UnitStr]


def _enum_to_int(x, default) -> int:
    """
    Return an int for x whether it's already an int or a Python Enum.
    `default` may itself be an Enum or an int.
    """
    if isinstance(x, Enum):
        return int(x.value)
    try:
        return int(x)
    except Exception:
        if isinstance(default, Enum):
            return int(default.value)
        return int(default)

@dataclass(frozen=True)
class FontOTMetrics:
    upem: int                       # unitsPerEm
    typo_ascender: int              # OS/2 sTypoAscender (>=0)
    typo_descender: int             # OS/2 sTypoDescender (<=0)
    typo_line_gap: int              # OS/2 sTypoLineGap (>=0)
    cap_height: Optional[int] = None  # OS/2 capHeight (optional)
    x_height: Optional[int] = None    # OS/2 sxHeight (optional)

class FontMetricsBackend(Protocol):
    def load_metrics(self, family: str, weight: int, italic: bool) -> FontOTMetrics: ...

# FEATURE: consistent leading computation (cap/x/em modes)

LeadingMode = Literal["cap", "x", "em"]

def compute_consistent_leading_px(
    *,
    point_size: float,                 # font size in pt
    dpi: float,                        # working dpi for px conversion
    metrics: FontOTMetrics,
    mode: LeadingMode = "cap",
    k: float = 1.4,                    # target multiple of the chosen base
    fallback_cap_ratio: float = 0.70,  # used if capHeight missing
    fallback_x_ratio: float = 0.50,    # used if xHeight missing
    min_leading_px: float = 0.0        # floor to avoid negative/too-tight
) -> tuple[float, float, float]:
    """
    Returns (leading_px, target_line_px, content_px).
    - leading_px: extra space to add between baselines
    - target_line_px: desired baseline distance
    - content_px: ascent+descent using typo metrics
    """

    # 1) Convert points to pixels (1pt = 1/72 in)
    size_px = (point_size / 72.0) * dpi

    upem = float(metrics.upem)
    asc_px = size_px * (metrics.typo_ascender / upem)
    desc_px = size_px * (abs(metrics.typo_descender) / upem)
    content_px = asc_px + desc_px

    # 2) Choose normalization base
    if mode == "cap":
        cap_u = metrics.cap_height if metrics.cap_height and metrics.cap_height > 0 else int(fallback_cap_ratio * metrics.upem)
        base_px = size_px * (cap_u / upem)
    elif mode == "x":
        x_u = metrics.x_height if metrics.x_height and metrics.x_height > 0 else int(fallback_x_ratio * metrics.upem)
        base_px = size_px * (x_u / upem)
    else:  # "em"
        base_px = size_px  # em == full nominal size

    # 3) Target baseline distance and leading
    target_line_px = k * base_px
    leading_px = max(min_leading_px, target_line_px - content_px)
    return leading_px, target_line_px, content_px

# FEATURE: optional top/bottom trim computation (for neat visual boxes)
# This centers the cap (or x) band inside the line box. Useful if your layout
# draws text into rectangles and you want predictable top/bottom padding.

def compute_trims_px(
    *,
    point_size: float,
    dpi: float,
    metrics: FontOTMetrics,
    mode: LeadingMode = "cap",
    k: float = 1.4,
    fallback_cap_ratio: float = 0.70,
    fallback_x_ratio: float = 0.50
) -> tuple[float, float, float]:
    """
    Returns (top_trim_px, bottom_trim_px, line_height_px).
    Trims are amounts to remove from the top/bottom of the default typo box
    so that the chosen visual band (cap/x) is vertically centered.
    """
    size_px = (point_size / 72.0) * dpi
    upem = float(metrics.upem)

    asc_px = size_px * (metrics.typo_ascender / upem)
    desc_px = size_px * (abs(metrics.typo_descender) / upem)

    # chosen visual band
    if mode == "cap":
        band_u = metrics.cap_height if metrics.cap_height and metrics.cap_height > 0 else int(fallback_cap_ratio * metrics.upem)
    elif mode == "x":
        band_u = metrics.x_height if metrics.x_height and metrics.x_height > 0 else int(fallback_x_ratio * metrics.upem)
    else:
        band_u = metrics.upem  # em

    band_px = size_px * (band_u / upem)

    # default typo box height without extra leading
    content_px = asc_px + desc_px
    line_height_px = k * band_px

    # space above cap band inside content box
    top_space_px = max(0.0, asc_px - band_px)
    bottom_space_px = max(0.0, desc_px)

    # We want the band centered within the final line height.
    # Distribute the difference as trims against the default content box.
    extra_px = max(0.0, line_height_px - content_px)  # this is also "leading"
    target_top = (top_space_px + extra_px / 2.0)
    target_bottom = (bottom_space_px + extra_px / 2.0)

    top_trim = top_space_px - target_top
    bottom_trim = bottom_space_px - target_bottom
    # (top_trim, bottom_trim) are typically negative numbers (i.e., "add padding"),
    # but you can apply them as offsets in your layout engine.

    return top_trim, bottom_trim, line_height_px

# FEATURE: bridge for UnitStrFont → leading UnitStr (GUI-agnostic)

def consistent_leading_for(
    usf: "UnitStrFont",
    backend: FontMetricsBackend,
    *,
    mode: LeadingMode = "cap",
    k: float = 1.4,
) -> "UnitStr":
    """
    Compute a UnitStr leading for the given UnitStrFont that normalizes across families.
    """
    m = backend.load_metrics(usf.family, usf.weight, usf.italic)
    pt = usf.size.to("pt", dpi=usf.dpi)
    leading_px, _, _ = compute_consistent_leading_px(
        point_size=pt,
        dpi=usf.dpi,
        metrics=m,
        mode=mode,
        k=k,
    )
    # store in px at the font's working dpi so downstream 'to("pt")' etc. just work
    return UnitStr(leading_px, unit="px", dpi=usf.dpi)


class _UnitStrFontView:
    """
    Read-only “view” over a UnitStrFont at a specific output unit + dpi,
    mirroring UnitStrGeometry's .px/.pt/... pattern.
    """
    __slots__ = ("_base", "_unit", "_dpi")

    def __init__(self, base: "UnitStrFont", unit: str, dpi: float):
        self._base = base
        self._unit = unit
        self._dpi = float(dpi)

    @property
    def qfont(self):
        return self._base.qfont(unit=self._unit, dpi=self._dpi)

    @property
    def leading(self):
        return self._base.leading.to(self._unit, dpi=self._dpi)

    @property
    def size(self) -> float:
        return float(self._base.size.to(self._unit, dpi=self._dpi))

    @property
    def font_str(self) -> str:
        return self.qfont.toString()

    def __repr__(self) -> str:
        return f"UnitStrFontView(unit={self._unit!r}, size={self.size:.3f}, dpi={self._dpi})"


@dataclass(frozen=True)
class UnitStrFont:
    # --- simple (immutable) defaults are safe:
    family: str = "Arial"
    fallbacks: Tuple[str, ...] = ()
    weight: int = QFont.Normal
    italic: bool = False
    stretch: int = QFont.Unstretched
    underline: bool = False
    strikeout: bool = False
    kerning: bool = True
    capitalization: QFont.Capitalization = QFont.MixedCase
    style_strategy: QFont.StyleStrategy = QFont.PreferDefault
    hinting_preference: QFont.HintingPreference = QFont.PreferDefaultHinting
    fixed_pitch: bool = False
    dpi: float = DEFAULT_DPI

    # --- UnitStr fields must NOT use mutable defaults: set in __init__
    size: UnitStr = field(init=False, repr=False)
    leading: UnitStr = field(init=False, repr=False)

    # ---------- Constructors ----------
    def __init__(
        self,
        first: Union["UnitStrFont", QFont, str, None] = None,
        *,
        family: Optional[str] = None,
        name: Optional[str] = None,
        size: Optional[Number] = None,
        unit: Optional[str] = None,
        dpi: Optional[float] = None,
        fallbacks: Optional[Iterable[str]] = None,
        weight: Optional[int] = None,
        italic: Optional[bool] = None,
        stretch: Optional[int] = None,
        underline: Optional[bool] = None,
        strikeout: Optional[bool] = None,
        kerning: Optional[bool] = None,
        capitalization: Optional[QFont.Capitalization] = None,
        leading: Optional[Number] = None,
        style_strategy: Optional[QFont.StyleStrategy] = None,
        hinting_preference: Optional[QFont.HintingPreference] = None,
        fixed_pitch: Optional[bool] = None,
    ):
        # base, simple assignments
        object.__setattr__(self, "dpi", float(dpi) if dpi is not None else DEFAULT_DPI)
        object.__setattr__(self, "family", "Arial")
        object.__setattr__(self, "fallbacks", tuple())
        object.__setattr__(self, "weight", QFont.Normal)
        object.__setattr__(self, "italic", False)
        object.__setattr__(self, "stretch", QFont.Unstretched)
        object.__setattr__(self, "underline", False)
        object.__setattr__(self, "strikeout", False)
        object.__setattr__(self, "kerning", True)
        object.__setattr__(self, "capitalization", QFont.MixedCase)
        object.__setattr__(self, "style_strategy", QFont.PreferDefault)
        object.__setattr__(self, "hinting_preference", QFont.PreferDefaultHinting)
        object.__setattr__(self, "fixed_pitch", False)
        object.__setattr__(self, "leading", UnitStr("0px@300"))

        # resolve base from `first`
        base: Optional[UnitStrFont] = None
        if isinstance(first, UnitStrFont):
            base = first
        elif isinstance(first, QFont):
            base = UnitStrFont.from_qfont(first, dpi=self.dpi)
        elif isinstance(first, str):
            base = UnitStrFont.from_string(first, dpi=self.dpi)
        elif first is not None:
            raise TypeError(f"Unsupported initializer for UnitStrFont: {type(first)}")

        if base is not None:
            for field_name in (
                "family","fallbacks","weight","italic","stretch","underline",
                "strikeout","kerning","capitalization","style_strategy",
                "hinting_preference","fixed_pitch","dpi"
            ):
                object.__setattr__(self, field_name, getattr(base, field_name))

        # Helper to resolve 'em' values into a UnitStr
        def _resolve_em(value: Number, reference_size: UnitStr) -> Optional[UnitStr]:
            if isinstance(value, str):
                val_str = value.strip().lower()
                if val_str.endswith("em"):
                    try:
                        numeric_part = float(val_str[:-2])
                        return reference_size * numeric_part
                    except (ValueError, TypeError):
                        return None  # Failed to parse
            return None

        # Determine the reference size for 'em' calculations for the font size itself
        base_size_for_em = getattr(base, 'size', UnitStr(12, unit="pt", dpi=self.dpi))

        # --- size (UnitStr), with 'em' handling ---
        new_size = None
        if size is not None:
            new_size = _resolve_em(size, base_size_for_em)
            if new_size is None:
                if isinstance(size, UnitStr):
                    new_size = UnitStr(size, dpi=self.dpi)
                else:
                    if isinstance(size, (int, float)) or (isinstance(size, str) and re.match(r"^\s*-?\d+(\.\d+)?\s*$", size)):
                        eff_unit = unit if unit else "px"
                        new_size = UnitStr(size, unit=eff_unit, dpi=self.dpi)
                    else:
                        new_size = UnitStr(size, unit=unit or None, dpi=self.dpi)

        if new_size is None:
            # Fallback to base size or default
            new_size = getattr(base, 'size', UnitStr(12, unit="pt", dpi=self.dpi))

        object.__setattr__(self, "size", new_size)

        # --- size (UnitStr), default 12pt unless overridden ---
        if size is not None:
            if isinstance(size, UnitStr):
                new_size = UnitStr(size, dpi=self.dpi)  # copy w/ target dpi
            else:
                # numeric or unitless string → default to provided unit or px
                if isinstance(size, (int, float)) or (
                    isinstance(size, str) and re.match(r"^\s*-?\d+(\.\d+)?\s*$", size)
                ):
                    eff_unit = unit if unit else "px"
                    new_size = UnitStr(size, unit=eff_unit, dpi=self.dpi)
                else:
                    # full token like "12pt" or "12px@300" → let UnitStr parse
                    new_size = UnitStr(size, unit=unit or None, dpi=self.dpi)
            object.__setattr__(self, "size", new_size)

            # --- family / fallbacks / other scalar flags ---
            eff_family = family if family is not None else name
            if eff_family:
                object.__setattr__(self, "family", str(eff_family))
            if fallbacks is not None:
                object.__setattr__(self, "fallbacks", tuple(fallbacks))
            if weight is not None:
                object.__setattr__(self, "weight", int(weight))
            if italic is not None:
                object.__setattr__(self, "italic", bool(italic))
            if stretch is not None:
                object.__setattr__(self, "stretch", int(stretch))
            if underline is not None:
                object.__setattr__(self, "underline", bool(underline))
            if strikeout is not None:
                object.__setattr__(self, "strikeout", bool(strikeout))
            if kerning is not None:
                object.__setattr__(self, "kerning", bool(kerning))
            if capitalization is not None:
                object.__setattr__(self, "capitalization", capitalization)
            if style_strategy is not None:
                object.__setattr__(self, "style_strategy", style_strategy)
            if hinting_preference is not None:
                object.__setattr__(self, "hinting_preference", hinting_preference)
            if fixed_pitch is not None:
                object.__setattr__(self, "fixed_pitch", bool(fixed_pitch))
            if dpi is not None:
                object.__setattr__(self, "dpi", float(dpi))  # already used above

            # --- leading (UnitStr): explicit override OR default to 1.5× size ---
            if leading is not None:
                # --- leading (UnitStr), with 'em' handling ---
                # 'em' for leading is relative to the *final* size we just calculated.
                new_leading = None
                if leading is not None:
                    new_leading = _resolve_em(leading, self.size) # Use self.size as reference
                    if new_leading is None:
                        if isinstance(leading, UnitStr):
                            new_leading = UnitStr(leading, dpi=self.dpi)
                        else:
                            if isinstance(leading, (int, float)) or (isinstance(leading, str) and re.match(r"^\s*-?\d+(\.\d+)?\s*$", leading)):
                                new_leading = UnitStr(leading, unit=(unit or "px"), dpi=self.dpi)
                            else:
                                new_leading = UnitStr(leading, unit=unit or None, dpi=self.dpi)

                if new_leading is None:
                    # Fallback to base leading or default to 1.5 * size
                    new_leading = getattr(base, 'leading', self.size * 1.5)

                object.__setattr__(self, "leading", new_leading)

                if isinstance(leading, UnitStr):
                    new_leading = UnitStr(leading, dpi=self.dpi)
                else:
                    if isinstance(leading, (int, float)) or (
                        isinstance(leading, str) and re.match(r"^\s*-?\d+(\.\d+)?\s*$", leading)
                    ):
                        new_leading = UnitStr(leading, unit=(unit or "px"), dpi=self.dpi)
                    else:
                        new_leading = UnitStr(leading, unit=unit or None, dpi=self.dpi)
            else:
                new_leading = self.size * 1.5
            object.__setattr__(self, "leading", new_leading)

            # guard: clamp any invalid size (non-positive)
            if self.to_value("px") <= 0 or self.to_value("pt") <= 0:
                object.__setattr__(self, "size", UnitStr(0.01, unit="pt", dpi=self.dpi))
                # keep leading proportional
                object.__setattr__(self, "leading", UnitStr(0.015, unit="pt", dpi=self.dpi))

    # ---------- Parsing helpers ----------
    @classmethod
    def from_qfont(cls, qf: QFont, *, dpi: float = DEFAULT_DPI, fallbacks: Optional[Iterable[str]] = None) -> "UnitStrFont":
        # QFont rule: one of pointSizeF/pixelSize is negative when the other is set.
        ps = qf.pointSizeF()
        px = qf.pixelSize()
        if (ps is not None and ps > 0) and (px is not None and px > 0):
            size = UnitStr(ps, unit="pt", dpi=dpi)     # prefer physical
        elif ps is not None and ps > 0:
            size = UnitStr(ps, unit="pt", dpi=dpi)
        elif px is not None and px > 0:
            size = UnitStr(px, unit="px", dpi=dpi)
        else:
            size = UnitStr(12, unit="pt", dpi=dpi)
        leading = size * 1.4
        fam = qf.family() or "Arial"
        fb = tuple(fallbacks) if fallbacks else tuple()
        return cls(
            None,
            name=fam,
            size=size,
            dpi=dpi,
            fallbacks=fb,
            weight=qf.weight(),
            italic=qf.italic(),
            stretch=qf.stretch(),
            underline=qf.underline(),
            strikeout=qf.strikeOut(),
            kerning=qf.kerning(),
            capitalization=qf.capitalization(),
            leading=leading,
            style_strategy=qf.styleStrategy(),
            hinting_preference=qf.hintingPreference(),
            fixed_pitch=qf.fixedPitch(),
        )

    @classmethod
    def from_string(cls, s: str, *, dpi: float = DEFAULT_DPI, fallbacks: Optional[Iterable[str]] = None) -> "UnitStrFont":
        # Try native QFont format first
        qf = QFont()
        if qf.fromString(s):
            return cls.from_qfont(qf, dpi=dpi, fallbacks=fallbacks)

        m = _NATURAL_RE.match(s)
        if not m:
            return cls(None, name=s.strip(), dpi=dpi, fallbacks=fallbacks)

        family = (m.group("family") or "Arial").strip()
        size_token = m.group("size")
        unit_token = (m.group("unit") or "").lower() or None
        style_tok = (m.group("style") or "").lower()
        weight_tok = (m.group("weight") or "").lower().replace("-", " ").strip()

        size_us = UnitStr(12, unit="pt", dpi=dpi)
        if size_token is not None:
            # --- START MODIFICATION ---
            if unit_token == "em":
                # For string parsing, assume 1em is relative to a default size (e.g., 12pt)
                base_size_for_em = UnitStr(12, unit="pt", dpi=dpi)
                try:
                    em_value = float(size_token)
                    size_us = base_size_for_em * em_value
                except ValueError:
                    # Fallback if size_token is not a valid float
                    pass  # Keep the default size_us
            else:
                # Default to px if caller wrote a bare number w/o unit; else use provided token
                size_us = UnitStr(size_token, unit=unit_token or "px", dpi=dpi)

        weight = _WEIGHT_MAP.get(weight_tok, QFont.Normal)
        italic = style_tok in ("italic", "oblique")
        leading = size_us * 1.5
        return cls(
            None,
            name=family,
            size=size_us,
            dpi=dpi,
            fallbacks=(tuple(x.strip() for x in (m.group("fallbacks") or "").split(",")) if m.group("fallbacks") else ()),
            weight=weight,
            italic=italic,
            leading=leading
        )

    # ---------- Conversions & views ----------
    @property
    def px(self) -> _UnitStrFontView:
        return _UnitStrFontView(self, "px", self.dpi)

    @property
    def pt(self) -> _UnitStrFontView:
        return _UnitStrFontView(self, "pt", self.dpi)

    @property
    def inch(self) -> _UnitStrFontView:
        return _UnitStrFontView(self, "in", self.dpi)

    @property
    def mm(self) -> _UnitStrFontView:
        return _UnitStrFontView(self, "mm", self.dpi)

    @property
    def cm(self) -> _UnitStrFontView:
        return _UnitStrFontView(self, "cm", self.dpi)

    def to(self, unit: str = "pt", dpi: float | None = None) -> _UnitStrFontView:
        return _UnitStrFontView(self, unit, self.dpi if dpi is None else dpi)

    def to_value(self, unit: str = "pt", dpi: float | None = None) -> float:
        return float(self.size.to(unit, dpi=self.dpi if dpi is None else dpi))

    @property
    def leading_px(self) -> float:
        return self.leading.to("px", dpi=self.dpi)

    @property
    def leading_pt(self) -> float:
        return self.leading.to("pt", dpi=self.dpi)

    @property
    def font_str(self) -> str:
        return self.qfont(unit="pt", dpi=self.dpi).toString()

    # Alias
    def scale(self, *, scale_factor: float | None = None, ldpi: float | None = None, dpi: float | None = None) -> "UnitStrFont":
        return self.font_scale(scale_factor=scale_factor, ldpi=ldpi, dpi=dpi)

    def qfont(self, *, unit: Optional[str] = None, dpi: Optional[float] = None) -> QFont:
        qf = QFont(self.family)

        qf.setWeight(QFont.Weight(_enum_to_int(self.weight, QFont.Weight.Normal)))
        qf.setItalic(bool(self.italic))
        qf.setStretch(int(self.stretch))
        qf.setUnderline(bool(self.underline))
        qf.setStrikeOut(bool(self.strikeout))
        qf.setKerning(bool(self.kerning))
        qf.setCapitalization(QFont.Capitalization(_enum_to_int(self.capitalization, QFont.MixedCase)))
        qf.setStyleStrategy(QFont.StyleStrategy(_enum_to_int(self.style_strategy, QFont.PreferDefault)))
        qf.setHintingPreference(QFont.HintingPreference(_enum_to_int(self.hinting_preference, QFont.PreferDefaultHinting)))
        qf.setFixedPitch(bool(self.fixed_pitch))

        out_unit = (unit or "pt").lower()
        out_dpi = float(dpi if dpi is not None else self.dpi)
        if out_unit == "px":
            qf.setPixelSize(int(round(self.size.to("px", dpi=out_dpi))))
        else:
            qf.setPointSizeF(self.size.to("pt", dpi=out_dpi))
        return qf

    # ---------- Scaling ----------
    def font_scale(
        self,
        *,
        scale_factor: Optional[float] = None,
        ldpi: Optional[float] = None,
        dpi: Optional[float] = None,
    ) -> "UnitStrFont":
        """
        Scale font for display. Provide EITHER scale_factor OR ldpi.
        - scale_factor: direct multiplier applied to size
        - ldpi: logical/source DPI. Effective factor = (dpi or self.dpi) / ldpi
        The returned font has its dpi set to (dpi or self.dpi).
        """
        if (scale_factor is None) == (ldpi is None):
            raise ValueError("Provide exactly one of scale_factor or ldpi.")
        target_dpi = float(dpi if dpi is not None else self.dpi)
        factor = float(scale_factor if scale_factor is not None else (target_dpi / float(ldpi)))
        new_size = self.size * factor  # UnitStr supports scalar *
        return self.with_overrides(size=new_size, dpi=target_dpi)

    # ---------- Utilities ----------
    def with_overrides(self, **kw) -> "UnitStrFont":
        """
        Return a new UnitStrFont based on this instance with selected fields overridden.
        Avoids dataclasses.replace() so we can override fields declared with init=False
        (e.g., size, leading) without tripping over the dataclass constraint.
        """
        # Normalize overrides to UnitStr where appropriate
        eff_dpi = kw.get("dpi", self.dpi)

        if "size" in kw and not isinstance(kw["size"], UnitStr):
            sz = kw["size"]
            if isinstance(sz, (int, float)) or (isinstance(sz, str) and re.match(r"^\s*-?\d+(\.\d+)?\s*$", sz)):
                kw["size"] = UnitStr(sz, unit="px", dpi=eff_dpi)
            else:
                kw["size"] = UnitStr(sz, dpi=eff_dpi)

        if "leading" in kw and not isinstance(kw["leading"], UnitStr):
            ld = kw["leading"]
            if isinstance(ld, (int, float)) or (isinstance(ld, str) and re.match(r"^\s*-?\d+(\.\d+)?\s*$", ld)):
                kw["leading"] = UnitStr(ld, unit="px", dpi=eff_dpi)
            else:
                kw["leading"] = UnitStr(ld, dpi=eff_dpi)

        # Create a new instance by using the custom __init__ path that accepts all overrides.
        # Passing `self` as the first arg clones all current fields; explicit kwargs then override them.
        return UnitStrFont(self, **kw)

    def clone(self) -> "UnitStrFont":
        return UnitStrFont(self)

    def __mul__(self, k: Union[int, float]) -> "UnitStrFont":
        if not isinstance(k, (int, float)):
            return NotImplemented
        return self.with_overrides(size=self.size * k, leading=self.leading * k)

    # ---------- Dict I/O ----------
    def to_dict(self) -> dict:
        return {
            "family": self.family,
            "fallbacks": list(self.fallbacks),
            "size": self.size.to_dict(),
            "weight": _enum_to_int(self.weight, QFont.Weight.Normal),
            "italic": bool(self.italic),
            "stretch": int(self.stretch),
            "underline": bool(self.underline),
            "strikeout": bool(self.strikeout),
            "kerning": bool(self.kerning),
            "capitalization": _enum_to_int(self.capitalization, QFont.MixedCase),
            "leading": self.leading.to_dict(),
            "style_strategy": _enum_to_int(self.style_strategy, QFont.PreferDefault),
            "hinting_preference": _enum_to_int(self.hinting_preference, QFont.PreferDefaultHinting),
            "fixed_pitch": bool(self.fixed_pitch),
            "dpi": float(self.dpi),
        }

    @classmethod
    def from_dict(cls, blob: dict) -> "UnitStrFont":
        dpi = float(blob.get("dpi", DEFAULT_DPI))

        weight = QFont.Weight(_enum_to_int(blob.get("weight", QFont.Weight.Normal), QFont.Weight.Normal))
        capitalization = QFont.Capitalization(_enum_to_int(blob.get("capitalization", QFont.MixedCase), QFont.MixedCase))
        style_strategy = QFont.StyleStrategy(_enum_to_int(blob.get("style_strategy", QFont.PreferDefault), QFont.PreferDefault))
        hinting_pref = QFont.HintingPreference(_enum_to_int(blob.get("hinting_preference", QFont.PreferDefaultHinting), QFont.PreferDefaultHinting))

        size = (
            UnitStr.from_dict(blob["size"]) if isinstance(blob.get("size"), dict)
            else UnitStr(blob.get("size", "12pt"), dpi=dpi)
        )
        leading = (
            UnitStr.from_dict(blob["leading"]) if isinstance(blob.get("leading"), dict)
            else size * 1.5
        )

        return cls(
            None,
            name=blob.get("family") or "Arial",
            fallbacks=blob.get("fallbacks") or (),
            size=size,
            weight=weight,
            italic=bool(blob.get("italic", False)),
            stretch=int(blob.get("stretch", QFont.Unstretched)),
            underline=bool(blob.get("underline", False)),
            strikeout=bool(blob.get("strikeout", False)),
            kerning=bool(blob.get("kerning", True)),
            capitalization=capitalization,
            leading=leading,
            style_strategy=style_strategy,
            hinting_preference=hinting_pref,
            fixed_pitch=bool(blob.get("fixed_pitch", False)),
            dpi=dpi,
        )

    # ---------- Convenience classmethods ----------
    @classmethod
    def from_pt(cls, family: str, pt: float, *, dpi: float = DEFAULT_DPI, **styles) -> "UnitStrFont":
        return cls(None, name=family, size=UnitStr(pt, unit="pt", dpi=dpi), dpi=dpi, **styles)

    @classmethod
    def from_px(cls, family: str, px: float, *, dpi: float = DEFAULT_DPI, **styles) -> "UnitStrFont":
        return cls(None, name=family, size=UnitStr(px, unit="px", dpi=dpi), dpi=dpi, **styles)

    @classmethod
    def from_in(cls, family: str, inch: float, *, dpi: float = DEFAULT_DPI, **styles) -> "UnitStrFont":
        return cls(None, name=family, size=UnitStr(inch, unit="in", dpi=dpi), dpi=dpi, **styles)

    # ---------- Equality & debug ----------
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, UnitStrFont):
            return NotImplemented
        return (
            self.family == other.family
            and self.fallbacks == other.fallbacks
            and round(self.size.to("in", dpi=self.dpi), 6) == round(other.size.to("in", dpi=other.dpi), 6)
            and self.weight == other.weight
            and self.italic == other.italic
            and self.stretch == other.stretch
            and self.underline == other.underline
            and self.strikeout == other.strikeout
            and self.kerning == other.kerning
            and round(self.leading.to("in", dpi=self.dpi), 6) == round(other.leading.to("in", dpi=other.dpi), 6)
            and self.capitalization == other.capitalization
            and self.style_strategy == other.style_strategy
            and self.hinting_preference == other.hinting_preference
            and self.fixed_pitch == other.fixed_pitch
            and round(self.dpi, 3) == round(other.dpi, 3)
        )

    def __hash__(self) -> int:
        return hash((
            self.family, self.fallbacks,
            round(self.size.to("in", dpi=self.dpi), 6),
            _enum_to_int(self.weight, QFont.Weight.Normal),
            self.italic, self.stretch,
            self.underline, self.strikeout, self.kerning,
            _enum_to_int(self.capitalization, QFont.MixedCase),
            round(self.leading.to("in", dpi=self.dpi), 6),
            _enum_to_int(self.style_strategy, QFont.PreferDefault),
            _enum_to_int(self.hinting_preference, QFont.PreferDefaultHinting),
            self.fixed_pitch,
            int(round(self.dpi)),
        ))

    def __repr__(self) -> str:
        return (f"UnitStrFont(family={self.family!r}, size={self.size.to('pt', dpi=self.dpi):.3f}pt, "
                f"dpi={self.dpi}, weight={self.weight}, italic={self.italic})")


# # unit_str_font.py
# from __future__ import annotations
# from enum import Enum
# from dataclasses import dataclass, replace
# from typing import Iterable, Optional, Tuple, Union
# import re

# from PySide6.QtGui import QFont, QFontMetricsF, QGuiApplication

# # Keep imports aligned with your project layout
# from prototypyside.utils.units.unit_str import UnitStr

# DEFAULT_DPI = 300.0

# _NATURAL_RE = re.compile(
#     r"""
#     ^\s*
#     (?P<family>[^,0-9]+?)            # family name up to a comma/number
#     (?:\s*,\s*(?P<fallbacks>[^0-9]+))?   # optional comma-separated fallbacks blob
#     \s*
#     (?:
#         (?P<size>-?\d+(?:\.\d+)?)    # numeric size
#         \s*
#         (?P<unit>pt|px|in|mm|cm)?    # optional unit
#     )?
#     (?:\s+(?P<style>italic|oblique))?
#     (?:\s+(?P<weight>thin|extra[-\s]?light|light|regular|normal|medium|semi[-\s]?bold|demi[-\s]?bold|bold|extra[-\s]?bold|black))?
#     \s*$
#     """,
#     re.IGNORECASE | re.VERBOSE,
# )

# _WEIGHT_MAP = {
#     "thin": QFont.Thin,
#     "extra light": QFont.ExtraLight,
#     "extralight": QFont.ExtraLight,
#     "light": QFont.Light,
#     "regular": QFont.Normal,
#     "normal": QFont.Normal,
#     "medium": QFont.Medium,
#     "semi bold": QFont.DemiBold,
#     "semibold": QFont.DemiBold,
#     "demi bold": QFont.DemiBold,
#     "demibold": QFont.DemiBold,
#     "bold": QFont.Bold,
#     "extra bold": QFont.ExtraBold,
#     "extrabold": QFont.ExtraBold,
#     "black": QFont.Black,
# }

# Number = Union[int, float, str, UnitStr]

# def _enum_to_int(x, default) -> int:
#     """
#     Return an int for x whether it's already an int or a Python Enum.
#     `default` may itself be an Enum or an int.
#     """
#     # unwrap enums safely
#     if isinstance(x, Enum):
#         return int(x.value)
#     try:
#         return int(x)
#     except Exception:
#         # unwrap default if it's an Enum
#         if isinstance(default, Enum):
#             return int(default.value)
#         return int(default)

# class _UnitStrFontView:
#     """
#     Read-only “view” over a UnitStrFont at a specific output unit + dpi,
#     mirroring UnitStrGeometry's .px/.pt/... pattern.
#     """
#     __slots__ = ("_base", "_unit", "_dpi")

#     def __init__(self, base: "UnitStrFont", unit: str, dpi: float):
#         self._base = base
#         self._unit = unit
#         self._dpi = float(dpi)

#     @property
#     def qfont(self):
#         # Property returns a ready-to-use QFont in this unit/dpi
#         return self._base.qfont(unit=self._unit, dpi=self._dpi)

#     @property
#     def leading(self):
#         return self._base.leading.to(self._unit, dpi=self._dpi)
#     @property
#     def size(self) -> float:
#         # Numeric size in this view’s unit
#         return float(self._base.size.to(self._unit, dpi=self._dpi))

#     @property
#     def font_str(self) -> str:
#         # String repr of the QFont in this view (e.g., pixel-sized if unit == "px")
#         return self.qfont.toString()

#     def __repr__(self) -> str:
#         return f"UnitStrFontView(unit={self._unit!r}, size={self.size:.3f}, dpi={self._dpi})"


# @dataclass(frozen=True)
# class UnitStrFont:
#     family: str = "Arial"
#     size: UnitStr = UnitStr(12, unit="pt", dpi=DEFAULT_DPI)  # canonical via UnitStr
#     fallbacks: Tuple[str, ...] = ()
#     weight: int = QFont.Normal
#     italic: bool = False
#     stretch: int = QFont.Unstretched
#     underline: bool = False
#     strikeout: bool = False
#     kerning: bool = True
#     capitalization: QFont.Capitalization = QFont.MixedCase
#     leading: UnitStr = UnitStr(0, unit="pt", dpi=DEFAULT_DPI)  # Add this line
#     style_strategy: QFont.StyleStrategy = QFont.PreferDefault
#     hinting_preference: QFont.HintingPreference = QFont.PreferDefaultHinting
#     fixed_pitch: bool = False
#     dpi: float = DEFAULT_DPI  # retained for px conversions

#     # ---------- Constructors ----------
#     def __init__(
#         self,
#         first: Union["UnitStrFont", QFont, str, None] = None,
#         *,
#         family: Optional[str] = None,
#         name: Optional[str] = None,
#         size: Optional[Number] = None,
#         unit: Optional[str] = None,
#         dpi: Optional[float] = None,
#         fallbacks: Optional[Iterable[str]] = None,
#         weight: Optional[int] = None,
#         italic: Optional[bool] = None,
#         stretch: Optional[int] = None,
#         underline: Optional[bool] = None,
#         strikeout: Optional[bool] = None,
#         kerning: Optional[bool] = None,
#         capitalization: Optional[QFont.Capitalization] = None,
#         leading: Optional[Number] = None,
#         style_strategy: Optional[QFont.StyleStrategy] = None,
#         hinting_preference: Optional[QFont.HintingPreference] = None,
#         fixed_pitch: Optional[bool] = None,
#     ):
#         # start from defaults
#         object.__setattr__(self, "dpi", float(dpi) if dpi is not None else DEFAULT_DPI)
#         object.__setattr__(self, "family", "Arial")
#         object.__setattr__(self, "size", UnitStr(12, unit="pt", dpi=self.dpi))
#         object.__setattr__(self, "fallbacks", tuple())
#         object.__setattr__(self, "weight", QFont.Normal)
#         object.__setattr__(self, "italic", False)
#         object.__setattr__(self, "stretch", QFont.Unstretched)
#         object.__setattr__(self, "underline", False)
#         object.__setattr__(self, "strikeout", False)
#         object.__setattr__(self, "kerning", True)
#         object.__setattr__(self, "capitalization", QFont.MixedCase)
#         object.__setattr__(self, "leading", UnitStr(self.size, unit="pt", dpi=dpi) * 1.5)
#         object.__setattr__(self, "style_strategy", QFont.PreferDefault)
#         object.__setattr__(self, "hinting_preference", QFont.PreferDefaultHinting)
#         object.__setattr__(self, "fixed_pitch", False)

#         # Resolve base from `first`
#         base: Optional[UnitStrFont] = None
#         if isinstance(first, UnitStrFont):
#             base = first
#         elif isinstance(first, QFont):
#             base = UnitStrFont.from_qfont(first, dpi=self.dpi)
#         elif isinstance(first, str):
#             base = UnitStrFont.from_string(first, dpi=self.dpi)
#         elif first is None:
#             base = None
#         else:
#             raise TypeError(f"Unsupported initializer for UnitStrFont: {type(first)}")

#         if base is not None:
#             for field in (
#                 "family","size","fallbacks","weight","italic","stretch","underline",
#                 "strikeout","kerning","capitalization","style_strategy","hinting_preference",
#                 "fixed_pitch","dpi"
#             ):
#                 object.__setattr__(self, field, getattr(base, field))

#         # --- UNIT PARAMETER BEHAVIOR (align with UnitStr/Geometry) ---
#         # If `size` is numeric or a unitless string, use provided `unit`, else default to 'px'.
#         if size is not None:
#             if isinstance(size, UnitStr):
#                 new_size = UnitStr(size, dpi=self.dpi)
#             else:
#                 if isinstance(size, (int, float)) or (isinstance(size, str) and re.match(r"^\s*-?\d+(\.\d+)?\s*$", size)):
#                     eff_unit = unit if unit else "px"
#                     new_size = UnitStr(size, unit=eff_unit, dpi=self.dpi)
#                 else:
#                     new_size = UnitStr(size, unit=unit or None, dpi=self.dpi)
#             object.__setattr__(self, "size", new_size)

#         if (family is not None) or (name is not None):
#             eff_family = family if family is not None else name
#             if eff_family:
#                 object.__setattr__(self, "family", str(eff_family))
#         if fallbacks is not None:
#             object.__setattr__(self, "fallbacks", tuple(fallbacks))
#         if weight is not None:
#             object.__setattr__(self, "weight", int(weight))
#         if italic is not None:
#             object.__setattr__(self, "italic", bool(italic))
#         if stretch is not None:
#             object.__setattr__(self, "stretch", int(stretch))
#         if underline is not None:
#             object.__setattr__(self, "underline", bool(underline))
#         if strikeout is not None:
#             object.__setattr__(self, "strikeout", bool(strikeout))
#         if kerning is not None:
#             object.__setattr__(self, "kerning", bool(kerning))
#         # if leading is not None:
#         #     leading = self.size * 1.5
#         #     # if isinstance(leading, UnitStr):
#         #     #     new_leading = UnitStr(leading, dpi=self.dpi)
#         #     # else:
#         #     #     if isinstance(leading, (int, float)) or (isinstance(leading, str) and re.match(r"^\s*-?\d+(\.\d+)?\s*$", leading)):
#         #     #         eff_unit = unit if unit else "px"
#         #     #         new_leading = UnitStr(leading, unit=eff_unit, dpi=self.dpi)
#         #     #     else:
#         #     #         new_leading = UnitStr(leading, unit=unit or None, dpi=self.dpi)
#         #     object.__setattr__(self, "leading", new_leading)
#         if capitalization is not None:
#             object.__setattr__(self, "capitalization", capitalization)
#         if style_strategy is not None:
#             object.__setattr__(self, "style_strategy", style_strategy)
#         if hinting_preference is not None:
#             object.__setattr__(self, "hinting_preference", hinting_preference)
#         if fixed_pitch is not None:
#             object.__setattr__(self, "fixed_pitch", bool(fixed_pitch))
#         if dpi is not None:
#             object.__setattr__(self, "dpi", float(dpi))

#         # guard: clamp any invalid size
#         if self.to_value("px") <= 0 or self.to_value("pt") <= 0:
#             object.__setattr__(self, "size", UnitStr(0.01, unit="pt", dpi=self.dpi))


#     # ---------- Parsing helpers ----------
#     @classmethod
#     def from_qfont(cls, qf: QFont, *, dpi: float = DEFAULT_DPI, fallbacks: Optional[Iterable[str]] = None) -> "UnitStrFont":
#         # QFont rule: one of pointSizeF/pixelSize is negative when the other is set.
#         ps = qf.pointSizeF()
#         px = qf.pixelSize()
#         if (ps is not None and ps > 0) and (px is not None and px > 0):
#             size = UnitStr(ps, unit="pt", dpi=dpi)     # prefer physical
#         elif ps is not None and ps > 0:
#             size = UnitStr(ps, unit="pt", dpi=dpi)
#         elif px is not None and px > 0:
#             size = UnitStr(px, unit="px", dpi=dpi)
#         else:
#             size = UnitStr(12, unit="pt", dpi=dpi)
#         leading = size * 1.4
#         fam = qf.family() or "Arial"
#         fb = tuple(fallbacks) if fallbacks else tuple()
#         return cls(
#             None,
#             name=fam,
#             size=size,
#             dpi=dpi,
#             fallbacks=fb,
#             weight=qf.weight(),
#             italic=qf.italic(),
#             stretch=qf.stretch(),
#             underline=qf.underline(),
#             strikeout=qf.strikeOut(),
#             kerning=qf.kerning(),
#             capitalization=qf.capitalization(),
#             leading=leading,
#             style_strategy=qf.styleStrategy(),
#             hinting_preference=qf.hintingPreference(),
#             fixed_pitch=qf.fixedPitch(),
#         )

#     @classmethod
#     def from_string(cls, s: str, *, dpi: float = DEFAULT_DPI, fallbacks: Optional[Iterable[str]] = None) -> "UnitStrFont":
#         qf = QFont()
#         if qf.fromString(s):
#             return cls.from_qfont(qf, dpi=dpi, fallbacks=fallbacks)

#         m = _NATURAL_RE.match(s)
#         if not m:
#             return cls(None, name=s.strip(), dpi=dpi, fallbacks=fallbacks)

#         family = (m.group("family") or "Arial").strip()
#         size_token = m.group("size")
#         unit_token = (m.group("unit") or "").lower() or None
#         style_tok = (m.group("style") or "").lower()
#         weight_tok = (m.group("weight") or "").lower().replace("-", " ").strip()

#         size_us = UnitStr(12, unit="pt", dpi=dpi)
#         if size_token is not None:
#             size_us = UnitStr(size_token, unit=unit_token or "px", dpi=dpi)  # align default to px

#         weight = _WEIGHT_MAP.get(weight_tok, QFont.Normal)
#         italic = style_tok in ("italic", "oblique")
#         leading = size_us * 1.5
#         return cls(
#             None,
#             name=family,
#             size=size_us,
#             dpi=dpi,
#             fallbacks=(tuple(x.strip() for x in (m.group("fallbacks") or "").split(",")) if m.group("fallbacks") else ()),
#             weight=weight,
#             italic=italic,
#             leading=leading
#         )

#     # ---------- Conversions & views ----------
#     @property
#     def px(self) -> _UnitStrFontView:
#         return _UnitStrFontView(self, "px", self.dpi)

#     @property
#     def pt(self) -> _UnitStrFontView:
#         return _UnitStrFontView(self, "pt", self.dpi)

#     @property
#     def inch(self) -> _UnitStrFontView:
#         return _UnitStrFontView(self, "in", self.dpi)

#     @property
#     def mm(self) -> _UnitStrFontView:
#         return _UnitStrFontView(self, "mm", self.dpi)

#     @property
#     def cm(self) -> _UnitStrFontView:
#         return _UnitStrFontView(self, "cm", self.dpi)

#     def to(self, unit: str = "pt", dpi: float | None = None) -> _UnitStrFontView:
#         """
#         Geometry-style converter: returns a *view object* bound to (unit, dpi),
#         so you can do: usf.to("px", dpi=300).qfont or .font_str or .size
#         """
#         return _UnitStrFontView(self, unit, self.dpi if dpi is None else dpi)

#     def to_value(self, unit: str = "pt", dpi: float | None = None) -> float:
#         """
#         Numeric converter (kept for convenience), analogous to UnitStr.to(...).
#         """
#         return float(self.size.to(unit, dpi=self.dpi if dpi is None else dpi))

#     @property
#     def leading_px(self) -> float:
#         return self.leading.to("px", dpi=self.dpi)

#     @property
#     def leading_pt(self) -> float:
#         return self.leading.to("pt", dpi=self.dpi)

#     @property
#     def font_str(self) -> str:
#         """
#         Default string repr (point-sized, no px lock).
#         Use usf.to('px', dpi=...).font_str to get a px-sized string.
#         """
#         return self.qfont(unit="pt", dpi=self.dpi).toString()

#     # Alais of font_scale
#     def scale(self, *, scale_factor: float | None = None, ldpi: float | None = None, dpi: float | None = None) -> "UnitStrFont":
#         return self.font_scale(scale_factor=scale_factor, ldpi=ldpi, dpi=dpi)

#     def qfont(self, *, unit: Optional[str] = None, dpi: Optional[float] = None) -> QFont:
#         qf = QFont(self.family)

#         qf.setWeight(QFont.Weight(_enum_to_int(self.weight, QFont.Weight.Normal)))
#         qf.setItalic(bool(self.italic))
#         qf.setStretch(int(self.stretch))
#         qf.setUnderline(bool(self.underline))
#         qf.setStrikeOut(bool(self.strikeout))
#         qf.setKerning(bool(self.kerning))
#         qf.setCapitalization(QFont.Capitalization(_enum_to_int(self.capitalization, QFont.MixedCase)))
#         qf.setStyleStrategy(QFont.StyleStrategy(_enum_to_int(self.style_strategy, QFont.PreferDefault)))
#         qf.setHintingPreference(QFont.HintingPreference(_enum_to_int(self.hinting_preference, QFont.PreferDefaultHinting)))
#         qf.setFixedPitch(bool(self.fixed_pitch))

#         out_unit = (unit or "pt").lower()
#         out_dpi = float(dpi if dpi is not None else self.dpi)
#         if out_unit == "px":
#             qf.setPixelSize(int(round(self.size.to("px", dpi=out_dpi))))
#         else:
#             qf.setPointSizeF(self.size.to("pt", dpi=out_dpi))
#         return qf

#     # ---------- Scaling ----------
#     def font_scale(
#         self,
#         *,
#         scale_factor: Optional[float] = None,
#         ldpi: Optional[float] = None,
#         dpi: Optional[float] = None,
#     ) -> "UnitStrFont":
#         """
#         Scale font for display. Provide EITHER scale_factor OR ldpi.
#         - scale_factor: direct multiplier applied to size
#         - ldpi: logical/source DPI. Effective factor = (dpi or self.dpi) / ldpi
#         The returned font has its dpi set to (dpi or self.dpi).
#         """
#         if (scale_factor is None) == (ldpi is None):
#             raise ValueError("Provide exactly one of scale_factor or ldpi.")
#         target_dpi = float(dpi if dpi is not None else self.dpi)
#         factor = float(scale_factor if scale_factor is not None else (target_dpi / float(ldpi)))
#         new_size = self.size * factor  # UnitStr supports scalar *
#         return self.with_overrides(size=new_size, dpi=target_dpi)

#     # ---------- Utilities ----------
#     def with_overrides(self, **kw) -> "UnitStrFont":
#         if "size" in kw and not isinstance(kw["size"], UnitStr):
#             sz = kw["size"]
#             if isinstance(sz, (int, float)) or (isinstance(sz, str) and re.match(r"^\s*-?\d+(\.\d+)?\s*$", sz)):
#                 kw["size"] = UnitStr(sz, unit="px", dpi=kw.get("dpi", self.dpi))
#             else:
#                 kw["size"] = UnitStr(sz, dpi=kw.get("dpi", self.dpi))
#         if "leading" in kw and not isinstance(kw["leading"], UnitStr):
#             # Handle leading similar to size
#             ld = kw["leading"]
#             if isinstance(ld, (int, float)) or (isinstance(ld, str) and re.match(r"^\s*-?\d+(\.\d+)?\s*$", ld)):
#                 kw["leading"] = UnitStr(ld, unit="px", dpi=kw.get("dpi", self.dpi))
#             else:
#                 kw["leading"] = UnitStr(ld, dpi=kw.get("dpi", self.dpi))
#         return replace(self, **(kw or {}))

#     def clone(self) -> "UnitStrFont":
#         return UnitStrFont(self)

#     def __mul__(self, k: Union[int, float]) -> "UnitStrFont":
#         if not isinstance(k, (int, float)):
#             return NotImplemented
#         return self.with_overrides(size=self.size * k, leading=self.leading * k)

#     # ---------- Dict I/O ----------
#     def to_dict(self) -> dict:
#         return {
#             "family": self.family,
#             "fallbacks": list(self.fallbacks),
#             "size": self.size.to_dict(),
#             "weight": _enum_to_int(self.weight, QFont.Weight.Normal),
#             "italic": bool(self.italic),
#             "stretch": int(self.stretch),
#             "underline": bool(self.underline),
#             "strikeout": bool(self.strikeout),
#             "kerning": bool(self.kerning),
#             "capitalization": _enum_to_int(self.capitalization, QFont.MixedCase),
#             "leading": self.leading.to_dict(),
#             "style_strategy": _enum_to_int(self.style_strategy, QFont.PreferDefault),
#             "hinting_preference": _enum_to_int(self.hinting_preference, QFont.PreferDefaultHinting),
#             "fixed_pitch": bool(self.fixed_pitch),
#             "dpi": float(self.dpi),
#         }

#     @classmethod
#     def from_dict(cls, blob: dict) -> "UnitStrFont":
#         dpi = float(blob.get("dpi", DEFAULT_DPI))

#         weight = QFont.Weight(
#             _enum_to_int(blob.get("weight", QFont.Weight.Normal), QFont.Weight.Normal)
#         )
#         capitalization = QFont.Capitalization(
#             _enum_to_int(blob.get("capitalization", QFont.MixedCase), QFont.MixedCase)
#         )
#         style_strategy = QFont.StyleStrategy(
#             _enum_to_int(blob.get("style_strategy", QFont.PreferDefault), QFont.PreferDefault)
#         )
#         hinting_pref = QFont.HintingPreference(
#             _enum_to_int(
#                 blob.get("hinting_preference", QFont.PreferDefaultHinting),
#                 QFont.PreferDefaultHinting
#             )
#         )
#         leading = (
#             UnitStr.from_dict(blob["leading"]) if isinstance(blob.get("leading"), dict)
#             else (
#                 UnitStr.from_dict(blob["size"]) * 1.5 if isinstance(blob.get("size"), dict)
#                 else UnitStr(blob.get("size", "12pt"), dpi=dpi) * 1.5
#             )
#         )
#         return cls(
#             None,
#             name=blob.get("family") or "Arial",
#             fallbacks=blob.get("fallbacks") or (),
#             size=UnitStr.from_dict(blob["size"]) if isinstance(blob.get("size"), dict)
#                  else UnitStr(blob.get("size", "12pt"), dpi=dpi),
#             weight=weight,
#             italic=bool(blob.get("italic", False)),
#             stretch=int(blob.get("stretch", QFont.Unstretched)),
#             underline=bool(blob.get("underline", False)),
#             strikeout=bool(blob.get("strikeout", False)),
#             kerning=bool(blob.get("kerning", True)),
#             capitalization=capitalization,
#             leading=leading,
#             style_strategy=style_strategy,
#             hinting_preference=hinting_pref,
#             fixed_pitch=bool(blob.get("fixed_pitch", False)),
#             dpi=dpi,
#         )

#     # ---------- Convenience classmethods ----------
#     @classmethod
#     def from_pt(cls, family: str, pt: float, *, dpi: float = DEFAULT_DPI, **styles) -> "UnitStrFont":
#         return cls(None, name=family, size=UnitStr(pt, unit="pt", dpi=dpi), dpi=dpi, **styles)

#     @classmethod
#     def from_px(cls, family: str, px: float, *, dpi: float = DEFAULT_DPI, **styles) -> "UnitStrFont":
#         return cls(None, name=family, size=UnitStr(px, unit="px", dpi=dpi), dpi=dpi, **styles)

#     @classmethod
#     def from_in(cls, family: str, inch: float, *, dpi: float = DEFAULT_DPI, **styles) -> "UnitStrFont":
#         return cls(None, name=family, size=UnitStr(inch, unit="in", dpi=dpi), dpi=dpi, **styles)

#     # ---------- Equality & debug ----------
#     def __eq__(self, other: object) -> bool:
#         if not isinstance(other, UnitStrFont):
#             return NotImplemented
#         return (
#             self.family == other.family
#             and self.fallbacks == other.fallbacks
#             and round(self.size.to("in", dpi=self.dpi), 6) == round(other.size.to("in", dpi=other.dpi), 6)
#             and self.weight == other.weight
#             and self.italic == other.italic
#             and self.stretch == other.stretch
#             and self.underline == other.underline
#             and self.strikeout == other.strikeout
#             and self.kerning == other.kerning
#             and round(self.leading.to("in", dpi=self.dpi), 6) == round(other.leading.to("in", dpi=other.dpi), 6)
#             and self.capitalization == other.capitalization
#             and self.style_strategy == other.style_strategy
#             and self.hinting_preference == other.hinting_preference
#             and self.fixed_pitch == other.fixed_pitch
#             and round(self.dpi, 3) == round(other.dpi, 3)
#         )

#     def __hash__(self) -> int:
#         return hash((
#             self.family, self.fallbacks,
#             round(self.size.to("in", dpi=self.dpi), 6),
#             _enum_to_int(self.weight, QFont.Weight.Normal),
#             self.italic, self.stretch,
#             self.underline, self.strikeout, self.kerning,
#             _enum_to_int(self.capitalization, QFont.MixedCase),
#             round(self.leading.to("in", dpi=self.dpi), 6),
#             _enum_to_int(self.style_strategy, QFont.PreferDefault),
#             _enum_to_int(self.hinting_preference, QFont.PreferDefaultHinting),
#             self.fixed_pitch,
#             int(round(self.dpi)),
#         ))

#     def __repr__(self) -> str:
#         return (f"UnitStrFont(family={self.family!r}, size={self.size.to('pt', dpi=self.dpi):.3f}pt, "
#                 f"dpi={self.dpi}, weight={self.weight}, italic={self.italic})")