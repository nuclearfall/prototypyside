# unit_str.py

from __future__ import annotations

import re
from decimal import Decimal, getcontext, ROUND_HALF_UP, ROUND_HALF_EVEN
from typing import Union, Optional

# ----- Decimal context
_CTX = getcontext()
_CTX.prec = 34
_CTX.rounding = ROUND_HALF_UP

# ----- Parsing
NUM_UNIT_RE = re.compile(
    r"^\s*(-?(?:\d+(?:\.\d+)?|\.\d+))\s*([a-zA-Z\"']+)?(?:@(\d+))?\s*$"
)
UNIT_ONLY_RE = re.compile(r"^\s*([a-zA-Z\"']+)\s*(?:@(\d+))?\s*$")

# ----- Canonical unit tables (inches as canonical internal)
UNITS_TO_INCHES = {
    "in": Decimal("1"),
    "mm": Decimal("1") / Decimal("25.4"),
    "cm": Decimal("1") / Decimal("2.54"),
    "pt": Decimal("1") / Decimal("72"),
}
INCHES_TO_UNITS = {u: (Decimal("1") / v) for u, v in UNITS_TO_INCHES.items()}

ROUNDING_INCREMENT = {
    "in": Decimal("0.01"),
    "mm": Decimal("0.1"),
    "cm": Decimal("0.1"),
    "pt": Decimal("1"),
}

_Q_IN  = Decimal("1E-9")   # internal grid (inches)
_Q_OUT = Decimal("1E-6")   # output grid (target units)


def pixels_per_unit(unit: str, dpi: float) -> float:
    return UnitStr("1", unit=unit, dpi=dpi).to("px", dpi=dpi)

def _normalize_unit_token(u: str | None) -> str | None:
    if not u:
        return None
    u = u.lower().strip().replace('"', "in").replace("''", "in").replace("“", "in").replace("”", "in")
    if u in ("inch", "inches"):
        return "in"
    if u in ("pixel", "pixels"):
        return "px"
    return u


def _parse_unit_maybe_at(unit_blob: str | None) -> tuple[Optional[str], Optional[int]]:
    if not unit_blob:
        return None, None
    m = UNIT_ONLY_RE.fullmatch(unit_blob)
    if not m:
        raise ValueError(f"Invalid unit token: {unit_blob!r}")
    unit_tok, dpi_str = m.groups()
    unit = _normalize_unit_token(unit_tok)
    dpi = int(dpi_str) if dpi_str is not None else None
    if dpi is not None and dpi <= 0:
        raise ValueError(f"DPI must be > 0, got {dpi}")
    return unit, dpi


class UnitStr:
    """
    Physically-correct scalar dimension stored internally as **Decimal inches**.

    Supports 'px@<dpi>' in raw and/or unit.

    Rule (requested): If raw has 'px@src' and unit is 'px@tgt' and no explicit dpi=,
                      interpret src as source DPI and tgt as target DPI (object's working DPI).
    """
    __slots__ = ("_raw", "_value", "_unit", "_dpi", "_cache")

    def __init__(
        self,
        raw: Union[str, float, int, Decimal, "UnitStr"],
        unit: Optional[str] = None,
        *,
        dpi: Optional[int] = None,
    ):
        if isinstance(raw, UnitStr):
            explicit_dpi = int(dpi) if dpi is not None else None
            self._raw   = raw._raw
            self._value = raw._value          # Decimal inches
            self._unit  = raw._unit           # preserve display unit
            self._dpi   = explicit_dpi if explicit_dpi is not None else raw._dpi
            return

        # safe to stringify non-UnitStr
        self._raw = str(raw)
        explicit_dpi = int(dpi) if dpi is not None else None
        self._cache: dict[tuple[str, int], float] = {}

        internal_unit = "in"

        # Clone
        if isinstance(raw, UnitStr):
            self._raw   = raw._raw
            self._value = raw._value
            self._unit  = internal_unit
            self._dpi   = explicit_dpi if explicit_dpi is not None else raw._dpi
            return

        # Parse raw
        input_val: Decimal
        raw_unit: Optional[str] = None
        raw_dpi_from_at: Optional[int] = None

        if isinstance(raw, str):
            m = NUM_UNIT_RE.fullmatch(raw.strip())
            if not m:
                raise ValueError(f"Invalid dimension string: {raw!r}")
            value_str, unit_blob, dpi_at_str = m.groups()
            input_val = Decimal(value_str)
            if unit_blob:
                raw_unit, raw_dpi_from_at = _parse_unit_maybe_at(unit_blob)
            if dpi_at_str is not None:
                raw_dpi_from_at = int(dpi_at_str)
                if raw_dpi_from_at <= 0:
                    raise ValueError(f"DPI must be > 0, got {raw_dpi_from_at}")
        elif isinstance(raw, (int, float, Decimal)):
            input_val = Decimal(str(raw))
        else:
            raise TypeError(f"Unsupported type for UnitStr: {type(raw)}")

        # Parse unit param (may also include @dpi)
        param_unit: Optional[str] = None
        param_dpi_from_at: Optional[int] = None
        if unit is not None:
            param_unit, param_dpi_from_at = _parse_unit_maybe_at(unit)

        # Resolve final unit: raw unit (if present) else param unit else 'px'
        final_unit = _normalize_unit_token(raw_unit) or _normalize_unit_token(param_unit) or "px"

        # Classify DPIs into source vs target per the new rule
        source_dpi: Optional[int] = None
        target_dpi_candidate: Optional[int] = None

        # Source from raw if raw is px@src
        if raw_dpi_from_at is not None and (raw_unit == "px"):
            source_dpi = raw_dpi_from_at

        # If raw provided a source dpi and unit is 'px@tgt' and no explicit dpi given,
        # treat unit's @dpi as TARGET DPI.
        if (source_dpi is not None and
            param_unit == "px" and
            param_dpi_from_at is not None and
            explicit_dpi is None):
            target_dpi_candidate = param_dpi_from_at
        else:
            # Otherwise, any @dpi on the unit is a SOURCE hint
            if param_unit == "px" and param_dpi_from_at is not None:
                # If we already had a source_dpi from raw and it's different, it's ambiguous
                if source_dpi is not None and source_dpi != param_dpi_from_at:
                    raise ValueError(
                        f"Conflicting source DPIs: raw@{source_dpi} vs unit@{param_dpi_from_at}"
                    )
                source_dpi = source_dpi or param_dpi_from_at

        # Determine target DPI
        if explicit_dpi is not None:
            # explicit dpi wins as TARGET; if we also derived a target_dpi_candidate, ensure agreement
            if target_dpi_candidate is not None and target_dpi_candidate != explicit_dpi:
                raise ValueError(
                    f"Conflicting target DPIs: unit@{target_dpi_candidate} vs dpi={explicit_dpi}"
                )
            target_dpi = explicit_dpi
            if target_dpi <= 0:
                raise ValueError(f"DPI must be > 0, got {target_dpi}")
        elif target_dpi_candidate is not None:
            target_dpi = target_dpi_candidate
        elif source_dpi is not None:
            target_dpi = source_dpi
        else:
            target_dpi = 300

        # Convert to internal inches
        if final_unit == "px":
            px_dpi_for_input = source_dpi if source_dpi is not None else target_dpi
            self._value = (input_val / Decimal(px_dpi_for_input)).quantize(_Q_IN)
        elif final_unit in UNITS_TO_INCHES:
            self._value = (input_val * UNITS_TO_INCHES[final_unit]).quantize(_Q_IN)
        else:
            raise ValueError(f"Unsupported unit: {final_unit!r}")

        self._unit = final_unit or "in"   # <-- keep the display unit the caller used
        self._dpi  = target_dpi

    # --------- convenience constructors
    @classmethod
    def from_px(cls, px: Union[int, float, Decimal], *, dpi: int = 300) -> "UnitStr":
        return cls(raw=px, unit="px", dpi=dpi)

    # --------- properties
    @property
    def dpi(self) -> int:
        return self._dpi
    @classmethod
    def ppu(cls, unit, dpi):
        pixels_per_unit(unit, dpi)

    @property
    def inches(self) -> Decimal:
        return self._value  # Decimal inches (canonical, immutable)

    @property
    def value(self) -> float:
        # numeric in current unit: use self.unit and (for px) self._dpi embedded in this instance
        if self.unit == "px":
            # value is stored canonically in inches; compute px by this instance's dpi
            return float((self._value * Decimal(self._dpi)).quantize(_Q_OUT))
        # non-px units
        return float((self._value * INCHES_TO_UNITS.get(self.unit, Decimal(1))).quantize(_Q_OUT))

    @property
    def unit(self) -> str:
        return self._unit

    @unit.setter
    def unit(self, unit_blob: str) -> None:
        u, dpi_from_unit = _parse_unit_maybe_at(unit_blob)
        if not u:
            raise ValueError("Unit must be specified")
        # update target/display dpi if the new unit encodes px@<dpi>
        if u == "px" and dpi_from_unit is not None:
            if dpi_from_unit <= 0:
                raise ValueError(f"DPI must be > 0, got {dpi_from_unit}")
            self._dpi = int(dpi_from_unit)
        self._unit = u
        self._cache.clear()

    # convenience aliases
    @property
    def inch(self) -> float: return self.to("in")
    @property
    def mm(self)   -> float: return self.to("mm")
    @property
    def cm(self)   -> float: return self.to("cm")
    @property
    def pt(self)   -> float: return self.to("pt")
    @property
    def px(self)   -> float: return self.to("px")

    # --------- conversion
    def to(self, target: str, dpi: Optional[int] = None) -> "UnitStr":
        """
        Return a NEW UnitStr expressed in the target unit (supports 'px@<dpi>').
        No in-place mutation. Internal inches remain canonical.
        """
        target_unit, dpi_from_unit = _parse_unit_maybe_at(target)
        tgt = target_unit or "in"

        # Decide effective DPI for px outputs
        if tgt == "px":
            dpi_from_call = int(dpi) if dpi is not None else None
            effective_dpi = (
                dpi_from_call
                if dpi_from_call is not None
                else (dpi_from_unit if dpi_from_unit is not None else self._dpi)
            )
            if effective_dpi <= 0:
                raise ValueError("DPI must be > 0 for pixel conversion")
            # compute numeric in px and return a fresh UnitStr with px@dpi
            out_px = (self._value * Decimal(effective_dpi)).quantize(_Q_OUT)
            return UnitStr(f"{out_px} px@{effective_dpi}", dpi=self._dpi)
        elif tgt in INCHES_TO_UNITS:
            out = (self._value * INCHES_TO_UNITS[tgt]).quantize(_Q_OUT)
            return UnitStr(f"{out} {tgt}", dpi=self._dpi)
        else:
            raise ValueError(f"Cannot convert to unsupported unit: {target!r}")

    def fmt(self, fmt: str = "g", unit: str | None = None, dpi: int | None = None) -> str:
        u_blob = unit or self.unit
        u_obj = self.to(u_blob, dpi=dpi)     # UnitStr
        u, _ = _parse_unit_maybe_at(u_blob)
        u = u or "in"
        return f"{format(u_obj.value, fmt)} {u}"  # <-- numeric, not object

    @property
    def round(self) -> "UnitStr":
        inc = ROUNDING_INCREMENT.get(self.unit, Decimal("0.01"))
        rounded_in = (self.value / inc).to_integral_value(rounding=ROUND_HALF_UP) * inc
        return UnitStr(f"{rounded_in} in", dpi=self._dpi)

    def number(self, unit: Optional[str] = None, dpi: Optional[int] = None) -> float:
        """Return the numeric as float in the requested (or current) unit."""
        u = self.to(unit or self.unit, dpi=dpi)
        return float(u.value)  # see note on .value below

    def to_dict(self) -> dict:
        return {u: self.to(u) for u in ("in", "mm", "cm", "pt", "px")}

    @classmethod
    def from_dict(cls, data: dict, *, unit: str = "in", dpi: int = 300) -> "UnitStr":
        u, u_dpi = _parse_unit_maybe_at(unit)
        u = u or "in"
        if u in data:
            if u == "px" and u_dpi is not None:
                return cls(f"{data[u]} px@{u_dpi}", dpi=dpi)
            return cls(f"{data[u]} {u}", dpi=dpi)
        for alt in ("in", "mm", "cm", "pt"):
            if alt in data:
                return cls(f"{data[alt]} {alt}", dpi=dpi)
        if "px" in data:
            return cls(data["px"], unit="px", dpi=dpi)
        raise ValueError("UnitStr.from_dict: no recognised unit found in data")

    # --------- arithmetic in inches
    def _as_decimal_inches(self) -> Decimal:
        return self._value

    # --- helpers (optional but neat) --------------------------------------------
    def _new_from_inches(self, inches: Decimal) -> "UnitStr":
        # snap to your grid
        z = inches.quantize(_Q_IN)
        # collapse -0 to +0 to avoid weird “-0E-9” cases
        if z == 0:
            z = Decimal("0")
        # construct directly as inches (no string formatting)
        return UnitStr(z, unit="in", dpi=self._dpi)

    def _coerce_unitstr(self, other) -> "UnitStr | None":
        if isinstance(other, UnitStr):
            return other
        if isinstance(other, str):
            return UnitStr(other, dpi=self._dpi)
        return None

    # --- arithmetic in inches ---------------------------------------------------
    def __add__(self, other):
        o = self._coerce_unitstr(other)
        if o is not None:
            return self._new_from_inches(self._as_decimal_inches() + o._as_decimal_inches())
        if isinstance(other, (int, float, Decimal)):
            return self._new_from_inches(self._as_decimal_inches() + Decimal(str(other)))
        return NotImplemented

    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        o = self._coerce_unitstr(other)
        if o is not None:
            return self._new_from_inches(self._as_decimal_inches() - o._as_decimal_inches())
        if isinstance(other, (int, float, Decimal)):
            return self._new_from_inches(self._as_decimal_inches() - Decimal(str(other)))
        return NotImplemented

    def __rsub__(self, other):
        o = self._coerce_unitstr(other)
        if o is not None:
            return self._new_from_inches(o._as_decimal_inches() - self._as_decimal_inches())
        if isinstance(other, (int, float, Decimal)):
            return self._new_from_inches(Decimal(str(other)) - self._as_decimal_inches())
        return NotImplemented

    def __mul__(self, other):
        if isinstance(other, (int, float, Decimal)):
            factor = Decimal(str(other))
            return self._new_from_inches(self._as_decimal_inches() * factor)
        if isinstance(other, UnitStr):
            # area (sq in) as Decimal
            return self._as_decimal_inches() * other._as_decimal_inches()
        return NotImplemented

    def __rmul__(self, other):
        return self.__mul__(other)

    def __truediv__(self, other):
        if isinstance(other, (int, float, Decimal)):
            divisor = Decimal(str(other))
            return self._new_from_inches(self._as_decimal_inches() / divisor)
        if isinstance(other, UnitStr):
            # unitless ratio
            return self._as_decimal_inches() / other._as_decimal_inches()
        return NotImplemented

    def __rtruediv__(self, other):
        if isinstance(other, (int, float, Decimal)):
            dividend = Decimal(str(other))
            # result is *inches* when number / UnitStr (unusual, but symmetric)
            return self._new_from_inches(dividend / self._as_decimal_inches())
        return NotImplemented

    def __floordiv__(self, other):
        if isinstance(other, (int, float, Decimal)):
            divisor = Decimal(str(other))
            # floor in inches, then return UnitStr
            q = (self._as_decimal_inches() / divisor).to_integral_value(rounding=ROUND_HALF_EVEN)
            return self._new_from_inches(q)
        if isinstance(other, UnitStr):
            return (self._as_decimal_inches() // other._as_decimal_inches())
        return NotImplemented

    def __rfloordiv__(self, other):
        if isinstance(other, (int, float, Decimal)):
            dividend = Decimal(str(other))
            q = (dividend / self._as_decimal_inches()).to_integral_value(rounding=ROUND_HALF_EVEN)
            return self._new_from_inches(q)
        return NotImplemented
        
    def __neg__(self):
        return self._new_from_inches(-self._as_decimal_inches())

    def __pos__(self):
        return self._new_from_inches(+self._as_decimal_inches())

    def __abs__(self):
        return self._new_from_inches(self._as_decimal_inches().copy_abs())

    # --------- comparisons with tolerance
    def _cmp_key(self) -> Decimal:
        return self._as_decimal_inches().quantize(_Q_IN)

    def __eq__(self, other) -> bool:
        if isinstance(other, UnitStr):
            return (self._cmp_key() - other._cmp_key()).copy_abs() <= _Q_IN
        if isinstance(other, (int, float, Decimal)):
            return (self._cmp_key() - Decimal(str(other))).copy_abs() <= _Q_IN
        return NotImplemented

    def __lt__(self, other) -> bool:
        if isinstance(other, UnitStr):
            return self._cmp_key() < other._cmp_key() - _Q_IN
        if isinstance(other, (int, float, Decimal)):
            return self._cmp_key() < Decimal(str(other)) - _Q_IN
        return NotImplemented

    def __le__(self, other) -> bool:
        if isinstance(other, UnitStr):
            return self._cmp_key() < other._cmp_key() - _Q_IN
        if isinstance(other, (int, float, Decimal)):
            return self._cmp_key() < Decimal(str(other)) - _Q_IN
        return NotImplemented

    def __str__(self) -> str:
        return self.fmt(unit=self.unit)

    def __repr__(self) -> str:
        try:
            cur = self.fmt(unit=self.unit)
        except Exception:
            suffix = f"@{self._dpi}" if self._unit == "px" else ""
            cur = f"{self.value}{self.unit}{suffix}"
        return f"UnitStr('{self._raw}', dpi={self._dpi}) -> {cur} | {self.inches}in"

