# unit_str_geometry.py
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Optional, Union, Tuple

# Qt accessors remain available for current code paths.
from PySide6.QtCore import QRectF, QPointF, QSizeF

# IMPORTANT: this should point to your updated UnitStr with px@DPI semantics.
from prototypyside.utils.units.unit_str import UnitStr, pixels_per_unit

Number = Union[int, float, str, Decimal, UnitStr]

class UnitStrGeometry:
    """
    A physically-accurate geometry container.

    Internals:
      - All six scalars are stored as UnitStr (Decimal inches):
          rect_x, rect_y, width, height (local rect)
          pos_x,  pos_y  (scene/world position)
      - _unit: the *display/output* unit for Qt accessors (default 'in')
      - _dpi:  the object's working/target DPI for pixel conversions
      - _print_dpi: optional print/export DPI hint (passthrough)

    Qt accessors (backward compatible):
      - .rect    -> QRectF in `_unit`
      - .pos     -> QPointF in `_unit`
      - .size    -> QSizeF in `_unit`
      - .scene_rect -> QRectF in `_unit`

    GUI-agnostic tuple accessors (new):
      - .rect_tuple(unit='in', dpi=None)  -> (x, y, w, h) floats
      - .pos_tuple(unit='in', dpi=None)   -> (x, y)
      - .size_tuple(unit='in', dpi=None)  -> (w, h)
      - .scene_rect_tuple(unit='in', dpi=None) -> (x, y, w, h)

    Notes on px@DPI:
      - Inputs like "12px@72" are interpreted with 72 as the SOURCE DPI.
      - A unit string like unit="px@300" (with no explicit dpi= in ctor) is
        taken as the TARGET (working) DPI, per your requested rule.
      - If an explicit dpi= is also supplied, it is the TARGET DPI. Any target
        @dpi in the unit argument that disagrees will raise a ValueError.
    """

    __slots__ = (
        "_rect_x", "_rect_y", "_w", "_h", "_pos_x", "_pos_y",
        "_unit", "_dpi", "_print_dpi", "_cache"
    )

    def __init__(
        self,
        rect: Optional[QRectF] = None,
        pos: Optional[QPointF] = None,
        size: Optional[QSizeF] = None,
        *,
        x:      Number | None = None,
        y:      Number | None = None,
        rect_x: Number | None = None,
        rect_y: Number | None = None,
        width:  Number | None = None,
        height: Number | None = None,
        geom: UnitStrGeometry | None = None,
        dpi:    int | None    = None,
        print_dpi: int        = 300,
        unit:   Optional[str] = None,
    ):
        # Resolve working DPI and output unit for this geometry
        self._dpi = int(dpi) if dpi is not None else 300
        self._print_dpi = int(print_dpi)
        # Normalize unit token (allow quotes for inches)
        self._unit = (unit or "in").lower().replace('"', "in")

        # Unpack Qt types (assumed authored in pixels unless already UnitStr)
        rx = rect.x()     if isinstance(rect, QRectF) else rect_x
        ry = rect.y()     if isinstance(rect, QRectF) else rect_y
        rw = rect.width() if isinstance(rect, QRectF) else width
        rh = rect.height()if isinstance(rect, QRectF) else height

        if isinstance(size, QSizeF):
            rw = size.width()
            rh = size.height()

        px = pos.x() if isinstance(pos, QPointF) else x
        py = pos.y() if isinstance(pos, QPointF) else y

        # Helper: coerce any incoming scalar to UnitStr using the geometry's
        # unit/dpi policy (this passes unit + dpi to UnitStr so px@DPI rules apply)
        def U(v: Number | None) -> UnitStr:
            if isinstance(v, UnitStr):
                # Allow overriding target DPI at geometry level
                return UnitStr(v, dpi=self._dpi)
            # Bare numbers default to geometry.unit; strings may embed units like "px@72"
            return UnitStr(0 if v is None else v, unit=self._unit, dpi=self._dpi)
        if geom:
            u_geom = geom.to(unit, dpi)
            self._rect_x = u_geom.rect_x
            self._rect_y = u_geom.rect_y
            self._w = u_geom.width
            self._h = u_geom.height
            self._pos_x = u_geom.pos_x
            self._pos_y = u_geom.pos_y
        else:
            self._rect_x = U(rx)
            self._rect_y = U(ry)
            self._w      = U(rw)
            self._h      = U(rh)
            self._pos_x  = U(px)
            self._pos_y  = U(py)

        # small per-instance conversion cache (unit,dpi)-> float tuples
        self._cache: dict[tuple[str, int, str], Tuple[float, ...]] = {}

    # ---- basic props --------------------------------------------------------

    @property
    def unit(self) -> str:
        """Current *display* unit for Qt accessors (e.g., 'in', 'mm', 'cm', 'pt', 'px')."""
        return self._unit

    @property
    def dpi(self) -> int:
        """Working/target DPI used when converting to/from pixels."""
        return self._dpi

    @property
    def print_dpi(self) -> int:
        """Optional export DPI hint (serialize & carry through)."""
        return self._print_dpi

    # Scalar access as UnitStr (Decimal inches internally)
    @property
    def rect_x(self) -> UnitStr: return self._rect_x
    @property
    def rect_y(self) -> UnitStr: return self._rect_y
    @property
    def width(self) -> UnitStr:  return self._w
    @property
    def height(self) -> UnitStr: return self._h
    @property
    def pos_x(self) -> UnitStr:  return self._pos_x
    @property
    def pos_y(self) -> UnitStr:  return self._pos_y

    # ---- conversion helpers -------------------------------------------------

    def _val(self, u: UnitStr, unit: Optional[str] = None, dpi: Optional[int] = None) -> float:
        """Convert a UnitStr scalar to a float in the requested unit/dpi (defaults to self._unit/self._dpi)."""
        return u.to(unit or self._unit, dpi if dpi is not None else self._dpi).value

    def ppu(self, unit, dpi):
        pixerls_per_unit(unit, dpi)
    # ---- Qt composite accessors (backward compatible) -----------------------

    @property
    def rect(self) -> QRectF:
        return QRectF(
            self._val(self._rect_x),
            self._val(self._rect_y),
            self._val(self._w),
            self._val(self._h),
        )

    @property
    def pos(self) -> QPointF:
        return QPointF(self._val(self._pos_x), self._val(self._pos_y))

    @property
    def size(self) -> QSizeF:
        return QSizeF(self._val(self._w), self._val(self._h))

    @property
    def scene_rect(self) -> QRectF:
        """Scene rectangle: (pos_x, pos_y, width, height) in current unit."""
        return QRectF(
            self._val(self._pos_x),
            self._val(self._pos_y),
            self._val(self._w),
            self._val(self._h),
        )

    # ---- GUI-agnostic tuple accessors --------------------------------------
    def ustr_tuple(self, unit: str | None = None, dpi: int | None = None) -> Tuple[float, float, float, float]:
        unit = (unit or self._unit).lower().replace('"', "in")
        dpi  = self._dpi if dpi is None else int(dpi)
        geom = self.to(unit, dpi=dpi)
        return [UnitStr(d, unit=unit, dpi=dpi) for d in [
            geom._rect_x, geom._rect_y, geom._w, geom._h, geom._pos_x, geom._pos_y]]

    def rect_tuple(self, unit: str | None = None, dpi: int | None = None) -> Tuple[float, float, float, float]:
        unit = (unit or self._unit).lower().replace('"', "in")
        dpi  = self._dpi if dpi is None else int(dpi)
        key = ("rect", unit, dpi)
        x = self._rect_x.to(unit, dpi).value
        y = self._rect_y.to(unit, dpi).value
        w = self._w.to(unit, dpi).value
        h = self._h.to(unit, dpi).value
        if key in self._cache:
            x, y, w, h = self._cache[key]
            return x, y, w, h
        self._cache[key] = (x, y, w, h)
        return x, y, w, h

    def pos_tuple(self, unit: str | None = None, dpi: int | None = None) -> Tuple[float, float]:
        unit = (unit or self._unit).lower().replace('"', "in")
        dpi  = self._dpi if dpi is None else int(dpi)
        key = ("pos", unit, dpi)
        if key in self._cache:
            x, y = self._cache[key]  # type: ignore[index]
            return x, y
        x = self.pos_x.to(unit, dpi).value
        y = self.pos_y.to(unit, dpi).value
        self._cache[key] = (x, y)
        return x, y

    def size_tuple(self, unit: str | None = None, dpi: int | None = None) -> Tuple[float, float]:
        unit = (unit or self._unit).lower().replace('"', "in")
        dpi  = self._dpi if dpi is None else int(dpi)
        key = ("size", unit, dpi)
        if key in self._cache:
            w, h = self._cache[key]  # type: ignore[index]
            return w, h
        w = self._w.to(unit, dpi).value
        h = self._h.to(unit, dpi).value
        self._cache[key] = (w, h)
        return w, h

    def scene_rect_tuple(self, unit: str | None = None, dpi: int | None = None) -> Tuple[float, float, float, float]:
        unit = (unit or self._unit).lower().replace('"', "in")
        dpi  = self._dpi if dpi is None else int(dpi)
        key = ("scene", unit, dpi)
        if key in self._cache:
            x, y, w, h = self._cache[key]
            return x, y, w, h
        x = self.pos_x.to(unit, dpi).value
        y = self.pos_y.to(unit, dpi).value
        w = self._w.to(unit, dpi).value
        h = self._h.to(unit, dpi).value
        self._cache[key] = (x, y, w, h)
        return x, y, w, h

    # ---- convenience converters --------------------------------------------

    def to(self, unit: str, dpi: int | None = None) -> UnitStrGeometry:
        """Return a new geometry with Qt accessors expressed in the given unit/dpi."""
        unit = (unit or "in").lower().replace('"', "in")
        dpi  = self._dpi if dpi is None else int(dpi)
        return UnitStrGeometry(
            rect_x=self._rect_x.to(unit, dpi),
            rect_y=self._rect_y.to(unit, dpi),
            width=self._w.to(unit, dpi),
            height=self._h.to(unit, dpi),
            x=self._pos_x.to(unit, dpi),
            y=self._pos_y.to(unit, dpi),
            dpi=dpi,
            print_dpi=self._print_dpi,
            unit=unit,
        )

    # Shorthand variants (mirror your UnitStr style)
    @property
    def px(self, dpi: int | None = None) -> UnitStrGeometry: return self.to("px", dpi=dpi)
    @property
    def inch(self) -> UnitStrGeometry: return self.to("in")
    @property
    def mm(self) -> UnitStrGeometry: return self.to("mm")
    @property
    def cm(self) -> UnitStrGeometry: return self.to("cm")
    @property
    def pt(self) -> UnitStrGeometry: return self.to("pt")

    # ---- editing helpers (pure, return new instances) -----------------------

    def with_pos(self, x: Number | None = None, y: Number | None = None) -> UnitStrGeometry:
        return UnitStrGeometry(
            rect_x=self._rect_x, rect_y=self._rect_y, width=self._w, height=self._h,
            x=self._pos_x if x is None else UnitStr(x, unit=self._unit, dpi=self._dpi),
            y=self._pos_y if y is None else UnitStr(y, unit=self._unit, dpi=self._dpi),
            dpi=self._dpi, print_dpi=self._print_dpi, unit=self._unit
        )

    def with_rect(
        self, *, rect_x: Number | None = None, rect_y: Number | None = None,
        width: Number | None = None, height: Number | None = None
    ) -> UnitStrGeometry:
        return UnitStrGeometry(
            rect_x=self._rect_x if rect_x is None else UnitStr(rect_x, unit=self._unit, dpi=self._dpi),
            rect_y=self._rect_y if rect_y is None else UnitStr(rect_y, unit=self._unit, dpi=self._dpi),
            width=self._w if width is None else UnitStr(width, unit=self._unit, dpi=self._dpi),
            height=self._h if height is None else UnitStr(height, unit=self._unit, dpi=self._dpi),
            x=self._pos_x, y=self._pos_y,
            dpi=self._dpi, print_dpi=self._print_dpi, unit=self._unit
        )

    def with_size(self, w: Number | None = None, h: Number | None = None) -> UnitStrGeometry:
        return self.with_rect(width=w, height=h)

    def moved_by(self, dx: Number = 0, dy: Number = 0) -> UnitStrGeometry:
        return UnitStrGeometry(
            rect_x=self._rect_x, rect_y=self._rect_y, width=self._w, height=self._h,
            x=self._pos_x + UnitStr(dx, unit=self._unit, dpi=self._dpi),
            y=self._pos_y + UnitStr(dy, unit=self._unit, dpi=self._dpi),
            dpi=self._dpi, print_dpi=self._print_dpi, unit=self._unit
        )

    def inset(self, dw: Number = 0, dh: Number = 0) -> UnitStrGeometry:
        """Shrink the local rect by (dw, dh) symmetrically (negative to outset)."""
        dw_u = UnitStr(dw, unit=self._unit, dpi=self._dpi)
        dh_u = UnitStr(dh, unit=self._unit, dpi=self._dpi)
        return UnitStrGeometry(
            rect_x=self._rect_x + (dw_u * 0.5),
            rect_y=self._rect_y + (dh_u * 0.5),
            width=self._w - dw_u,
            height=self._h - dh_u,
            x=self._pos_x, y=self._pos_y,
            dpi=self._dpi, print_dpi=self._print_dpi, unit=self._unit
        )

    def outset(self, dw: Number = 0, dh: Number = 0) -> UnitStrGeometry:
        return self.inset(-dw, -dh)

    def _as_unitstr(self, v: Union["UnitStr", Number]) -> "UnitStr":
        """Coerce numbers/UnitStr to a UnitStr in this geom's unit/dpi."""
        if isinstance(v, UnitStr):
            return v.to(self._unit, dpi=self._dpi)  # ensure consistent basis
        return UnitStr(v, unit=self._unit, dpi=self._dpi)

    def adjust(
        self,
        left: Union["UnitStr", Number] = 0,
        top: Union["UnitStr", Number] = 0,
        right: Union["UnitStr", Number] = 0,
        bottom: Union["UnitStr", Number] = 0,
        *,
        normalize: bool = False,
    ) -> "UnitStrGeometry":
        """
        QRectF.adjust(l, t, r, b) analog for UnitStrGeometry.

        Effect:
          x' = x + l
          y' = y + t
          w' = w + (r - l)
          h' = h + (b - t)

        Inputs may be numbers (interpreted in this geom's unit/dpi) or UnitStr.
        """
        l = self._as_unitstr(left)
        t = self._as_unitstr(top)
        r = self._as_unitstr(right)
        b = self._as_unitstr(bottom)

        new_rect_x = self._rect_x + l
        new_rect_y = self._rect_y + t
        new_w = self._w + (r - l)
        new_h = self._h + (b - t)

        out = UnitStrGeometry(
            rect_x=new_rect_x, rect_y=new_rect_y,
            width=new_w, height=new_h,
            x=self._pos_x, y=self._pos_y,
            dpi=self._dpi, print_dpi=self._print_dpi, unit=self._unit
        )

        if not normalize:
            return out

        # Optional QRectF.normalized()-style behavior
        zero = UnitStr(0, unit=self._unit, dpi=self._dpi)
        if new_w < zero:
            out = out.with_rect(rect_x=out._rect_x + new_w, width=-new_w)
        if new_h < zero:
            out = out.with_rect(rect_y=out._rect_y + new_h, height=-new_h)
        return out

    def adjust_inset(self, dw: Union["UnitStr", Number] = 0, dh: Union["UnitStr", Number] = 0) -> "UnitStrGeometry":
        """
        Symmetric shrink by (dw, dh), equivalent to adjust(+dw/2, +dh/2, -dw/2, -dh/2).
        Accepts UnitStr or numbers.
        """
        dw_u = self._as_unitstr(dw) * 0.5
        dh_u = self._as_unitstr(dh) * 0.5
        return self.adjust(left=+dw_u, top=+dh_u, right=-dw_u, bottom=-dh_u)

    def adjust_outset(self, dw: Union["UnitStr", Number] = 0, dh: Union["UnitStr", Number] = 0) -> "UnitStrGeometry":
        """Symmetric expand, inverse of adjust_inset()."""
        dw_u = self._as_unitstr(dw) * 0.5
        dh_u = self._as_unitstr(dh) * 0.5
        return self.adjust(left=-dw_u, top=-dh_u, right=+dw_u, bottom=+dh_u)

    # ---- serialization ------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "unit": self._unit,
            "dpi": self._dpi,
            "print_dpi": self._print_dpi,
            "pos_x": self._pos_x.to_dict(),
            "pos_y": self._pos_y.to_dict(),
            "rect_x": self._rect_x.to_dict(),
            "rect_y": self._rect_y.to_dict(),
            "width": self._w.to_dict(),
            "height": self._h.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> UnitStrGeometry:
        dpi = data.get("dpi", 300)
        unit = data.get("unit", "in")
        return cls(
            x=UnitStr.from_dict(data.get("pos_x", "0.0"), unit=unit, dpi=dpi),
            y=UnitStr.from_dict(data.get("pos_y", "0.0"), unit=unit, dpi=dpi),
            rect_x=UnitStr.from_dict(data.get("rect_x", "0.0"), unit=unit, dpi=dpi),
            rect_y=UnitStr.from_dict(data.get("rect_y", "0.0"), unit=unit, dpi=dpi),
            width=UnitStr.from_dict(data.get("width", "0.0"), unit=unit, dpi=dpi),
            height=UnitStr.from_dict(data.get("height", "0.0"), unit=unit, dpi=dpi),
            dpi=dpi,
            print_dpi=data.get("print_dpi", 300),
            unit=unit,
        )

    # ---- representation & equality -----------------------------------------

    def __repr__(self) -> str:
        x, y = self.pos_tuple(self._unit, self._dpi)
        w, h = self.size_tuple(self._unit, self._dpi)
        return f"UnitStrGeometry(pos=({x:.6g},{y:.6g}) {self._unit}, size=({w:.6g},{h:.6g}) {self._unit}, dpi={self._dpi}, print_dpi={self._print_dpi})"

    def _cmp_tuple(self) -> Tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, int]:
        # Compare using the canonical inch Decimals + dpi
        return (
            self._rect_x.inches, self._rect_y.inches, self._w.inches, self._h.inches,
            self._pos_x.inches, self._pos_y.inches, self._dpi,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, UnitStrGeometry):
            return NotImplemented
        return self._cmp_tuple() == other._cmp_tuple()

    def __hash__(self) -> int:
        return hash(self._cmp_tuple())

    # ---- Qt-specific constructors ------------------------------------------

    @classmethod
    def from_px(cls, rect: QRectF, pos: QPointF, dpi: int = 300) -> UnitStrGeometry:
        """Interpret incoming Qt rect/pos as *pixels at dpi*."""
        return cls(
            rect_x=f"{rect.x()} px@{dpi}",
            rect_y=f"{rect.y()} px@{dpi}",
            width=f"{rect.width()} px@{dpi}",
            height=f"{rect.height()} px@{dpi}",
            x=f"{pos.x()} px@{dpi}",
            y=f"{pos.y()} px@{dpi}",
            dpi=dpi,
            unit="px@{dpi}".format(dpi=dpi),
        )
