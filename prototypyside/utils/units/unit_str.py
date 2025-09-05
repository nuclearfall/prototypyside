# unit_str.py  (drop-in replacement with "raw px@source" + "unit px@target" support)

from __future__ import annotations

import re
from decimal import Decimal, getcontext, ROUND_HALF_UP
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

        self._unit = internal_unit
        self._dpi  = target_dpi

    # --------- convenience constructors
    @classmethod
    def from_px(cls, px: Union[int, float, Decimal], *, dpi: int = 300) -> "UnitStr":
        return cls(raw=px, unit="px", dpi=dpi)

    # --------- properties
    @property
    def dpi(self) -> int:
        return self._dpi

    @property
    def value(self) -> Decimal:
        return self._value  # inches

    @property
    def unit(self) -> str:
        return self._unit   # 'in'

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
    def to(self, target: str, dpi: Optional[int] = None) -> float:
        target_unit, dpi_from_unit = _parse_unit_maybe_at(target)
        target = target_unit or "in"
        dpi_from_call = int(dpi) if dpi is not None else None

        if target == "px":
            effective_dpi = (
                dpi_from_call
                if dpi_from_call is not None
                else (dpi_from_unit if dpi_from_unit is not None else self._dpi)
            )
            if effective_dpi <= 0:
                raise ValueError("DPI must be > 0 for pixel conversion")
        else:
            effective_dpi = self._dpi

        key = (target, effective_dpi)
        if key in self._cache:
            return self._cache[key]

        if target == "px":
            out = (self._value * Decimal(effective_dpi)).quantize(_Q_OUT)
        elif target in INCHES_TO_UNITS:
            out = (self._value * INCHES_TO_UNITS[target]).quantize(_Q_OUT)
        else:
            raise ValueError(f"Cannot convert to unsupported unit: {target!r}")

        f = float(out)
        self._cache[key] = f
        return f

    def fmt(self, fmt: str = "g", unit: str | None = None, dpi: int | None = None) -> str:
        u_blob = unit or self.unit
        val = self.to(u_blob, dpi=dpi)
        u, _ = _parse_unit_maybe_at(u_blob)
        u = u or "in"
        return f"{format(val, fmt)} {u}"

    @property
    def round(self) -> "UnitStr":
        inc = ROUNDING_INCREMENT.get(self.unit, Decimal("0.01"))
        rounded_in = (self.value / inc).to_integral_value(rounding=ROUND_HALF_UP) * inc
        return UnitStr(f"{rounded_in} in", dpi=self._dpi)

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

    def __add__(self, other):
        if isinstance(other, UnitStr):
            return UnitStr(f"{(self._as_decimal_inches() + other._as_decimal_inches()).quantize(_Q_IN)} in", dpi=self._dpi)
        if isinstance(other, (int, float, Decimal)):
            return UnitStr(f"{(self._as_decimal_inches() + Decimal(str(other))).quantize(_Q_IN)} in", dpi=self._dpi)
        return NotImplemented

    def __radd__(self, other): return self.__add__(other)

    def __sub__(self, other):
        if isinstance(other, UnitStr):
            return UnitStr(f"{(self._as_decimal_inches() - other._as_decimal_inches()).quantize(_Q_IN)} in", dpi=self._dpi)
        if isinstance(other, (int, float, Decimal)):
            return UnitStr(f"{(self._as_decimal_inches() - Decimal(str(other))).quantize(_Q_IN)} in", dpi=self._dpi)
        return NotImplemented

    def __rsub__(self, other):
        if isinstance(other, (int, float, Decimal)):
            return UnitStr(f"{(Decimal(str(other)) - self._as_decimal_inches()).quantize(_Q_IN)} in", dpi=self._dpi)
        return NotImplemented

    def __mul__(self, other):
        if isinstance(other, (int, float, Decimal)):
            return UnitStr(f"{(self._as_decimal_inches() * Decimal(str(other))).quantize(_Q_IN)} in", dpi=self._dpi)
        if isinstance(other, UnitStr):
            return (self._as_decimal_inches() * other._as_decimal_inches())  # sq in (Decimal)
        return NotImplemented

    def __rmul__(self, other):
        if isinstance(other, (int, float, Decimal)):
            return UnitStr(f"{(Decimal(str(other)) * self._as_decimal_inches()).quantize(_Q_IN)} in", dpi=self._dpi)
        return NotImplemented

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

    # --------- debug
    def __str__(self) -> str:
        return self.fmt(unit="in")

    def __repr__(self) -> str:
        return f"UnitStr('{self._raw}', dpi={self._dpi}) -> {self.value.normalize()}in"
