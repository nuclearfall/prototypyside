# prototypyside/utils/unit_str_geometry.py

from __future__ import annotations
from decimal import Decimal
from typing import Optional, Union

from PySide6.QtCore import QRectF, QPointF, QSizeF
from prototypyside.utils.units.unit_str import UnitStr

Number = Union[int, float, str, Decimal, UnitStr]

class UnitStrGeometry:
    """
    Stores a *local* QRectF (rect_x, rect_y, width, height) and an independent
    *scene* position (pos_x, pos_y). All components are UnitStr objects stored
    internally as inches.

    Accessors (`.rect`, `.pos`, `.size`) return Qt types with values in the
    `unit` (defaults to 'in'). Pixel values can be accessed via the
    `.px` property or `.to("px")`.
    """
    __items__ = (
        "_pos_x", "_pos_y",
        "_rect_x", "_rect_y",
        "_w", "_h",
        "_unit", "_dpi", "_print_dpi"
    )

    def __init__(
        self,
        *,
        rect: Optional[QRectF] = None,
        pos:  Optional[QPointF] = None,
        size: Optional[QSizeF]  = None,
        x:      Number | None   = None,
        y:      Number | None   = None,
        rect_x: Number | None   = None,
        rect_y: Number | None   = None,
        width:  Number | None   = None,
        height: Number | None   = None,
        dpi:    int             = 300,
        print_dpi: int          = 300,
        unit: Optional[str] = None,
    ):
        self._dpi = dpi
        self._print_dpi = print_dpi
        self._unit = (unit or "in").lower().replace('"', "in")

        # Unpack Qt types. These values are assumed to be in pixels unless they
        # are already UnitStr objects.
        raw_rx, raw_ry = (rect.x(), rect.y()) if rect else (rect_x or 0, rect_y or 0)
        raw_w, raw_h = (rect.width(), rect.height()) if rect else (width or 0, height or 0)
        if size is not None:
            raw_w, raw_h = size.width(), size.height()

        raw_x, raw_y = (pos.x(), pos.y()) if pos else (x or 0, y or 0)

        # change: bare floats become UnitStr(v, unit=unit, dpi) → use the geometry’s unit
        mk = lambda v: (
            v if isinstance(v, UnitStr)
            else UnitStr(v, unit=unit, dpi=dpi))
      

        self._rect_x = mk(raw_rx)
        self._rect_y = mk(raw_ry)
        self._w      = mk(raw_w)
        self._h      = mk(raw_h)
        self._pos_x  = mk(raw_x)
        self._pos_y  = mk(raw_y)

    @property
    def unit(self) -> str:
        """Canonical storage unit: always 'in'."""
        return "in"

    @property
    def unit(self) -> str:
        return self._unit

    @property
    def dpi(self) -> int:
        return self._dpi

    @property 
    def print(self) -> int:
        return self._print_dpi

    @property
    def round(self) -> UnitStrGeometry:
        """Returns a new geometry with all internal UnitStr values rounded."""
        g = object.__new__(UnitStrGeometry)
        g._rect_x = self._rect_x.round()
        g._rect_y = self._rect_y.round()
        g._w      = self._w.round()
        g._h      = self._h.round()
        g._pos_x  = self._pos_x.round()
        g._pos_y  = self._pos_y.round()
        g._dpi = self._dpi
        g._unit = self._unit
        return g

    # Individual UnitStr accessors
    @property
    def rect_x(self) -> UnitStr: return self._rect_x
    @property
    def rect_y(self) -> UnitStr: return self._rect_y
    @property
    def width(self)  -> UnitStr: return self._w
    @property
    def height(self) -> UnitStr: return self._h
    @property
    def pos_x(self)  -> UnitStr: return self._pos_x
    @property
    def pos_y(self)  -> UnitStr: return self._pos_y

    # Qt-friendly composite accessors
    def _val(self, u: UnitStr) -> float:
        return u.to(self._unit, self._dpi)

    @property
    def rect(self) -> QRectF:
        return QRectF(self._val(self._rect_x), self._val(self._rect_y), self._val(self._w), self._val(self._h))

    @property
    def pos(self) -> QPointF:
        return QPointF(self._val(self._pos_x), self._val(self._pos_y))

    @property
    def size(self) -> QSizeF:
        return QSizeF(self._val(self._w), self._val(self._h))

    def to(self, unit: str, dpi: int | None = None) -> UnitStrGeometry:
        """Returns a new UnitStrGeometry that emits values in the target unit."""
        dpi = dpi or self._dpi
        du = unit.lower().replace('"', "in")
        if du not in {"in", "cm", "mm", "pt", "px"}:
            raise ValueError(f"Unsupported display unit: {du!r}")

        g = object.__new__(UnitStrGeometry)
        g._rect_x, g._rect_y = self._rect_x, self._rect_y
        g._w, g._h = self._w, self._h
        g._pos_x, g._pos_y = self._pos_x, self._pos_y
        g._dpi = dpi
        g._unit = du
        return g

    # Shorthand views
    @property
    def px(self)   -> UnitStrGeometry: return self.to("px")
    @property
    def inch(self) -> UnitStrGeometry: return self.to("in")
    @property
    def mm(self)   -> UnitStrGeometry: return self.to("mm")
    @property
    def pt(self)   -> UnitStrGeometry: return self.to("pt")

    @classmethod
    def from_px(cls, rect: QRectF, pos: QPointF, dpi: int = 300) -> UnitStrGeometry:
        """Build a UnitStrGeometry by interpreting the given QRectF and QPointF as pixels."""
        return cls(
            x=pos.x(), y=pos.y(),
            rect_x=rect.x(), rect_y=rect.y(),
            width=rect.width(), height=rect.height(),
            dpi=dpi,
        )

    def to_dict(self) -> dict:
        """JSON-friendly dump of the geometry."""
        return {
            "unit": self.unit,
            "dpi": self.dpi,
            "print_dpi": self._print_dpi,
            "pos": {"x": self._pos_x.to_dict(), "y": self._pos_y.to_dict()},
            "rect": {
                "x": self._rect_x.to_dict(),
                "y": self._rect_y.to_dict(),
                "width": self._w.to_dict(),
                "height": self._h.to_dict(),
            },
        }

    @classmethod
    def from_dict(cls, blob: dict) -> UnitStrGeometry:
        """Reconstructs a UnitStrGeometry from its dictionary representation."""
        dpi = blob.get("dpi", 300)
        pos_data = blob.get("pos", {})
        rect_data = blob.get("rect", {})

        return cls(
            x=UnitStr.from_dict(pos_data.get("x", {}), dpi=dpi),
            y=UnitStr.from_dict(pos_data.get("y", {}), dpi=dpi),
            rect_x=UnitStr.from_dict(rect_data.get("x", {}), dpi=dpi),
            rect_y=UnitStr.from_dict(rect_data.get("y", {}), dpi=dpi),
            width=UnitStr.from_dict(rect_data.get("width", {}), dpi=dpi),
            height=UnitStr.from_dict(rect_data.get("height", {}), dpi=dpi),
            print_dpi=blob.get("print_dpi", 300),
            dpi=dpi,
            unit=blob.get("unit", "in"),
        )

    def __repr__(self) -> str:
        pos_str = f"x={self._pos_x.to(self.unit):.2f}, y={self._pos_y.to(self.unit):.2f}"
        rect_str = f"w={self._w.to(self.unit):.2f}, h={self._h.to(self.unit):.2f}"
        return (
            f"UnitStrGeometry({pos_str}, {rect_str}, "
            f"unit='{self.unit}', dpi={self.dpi})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, UnitStr):
            # Allow comparison with numbers if that's a desired behavior,
            # converting the number to a UnitStr first for comparison.
            # Otherwise, return NotImplemented.
            try:
                other_unit_str = UnitStr(other, unit=self.unit, dpi=self._dpi)
                return self._value == other_unit_str._value and self._dpi == other_unit_str._dpi
            except (ValueError, TypeError): # If conversion fails
                return NotImplemented # Or False, if strict
        
        # Ensure comparison is based on canonical values and DPI
        return self._value == other._value and self.unit == other.unit and self._dpi == other._dpi

    def __ne__(self, other: object) -> bool:
        return not (self == other)

    def __hash__(self) -> int:
        # Hash based on the canonical value and unit, and dpi
        return hash((self._value, self._canonical_unit, self._dpi))