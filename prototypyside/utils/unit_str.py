# unit_str.py

import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Union, Optional

UNIT_RE = re.compile(r"^\s*(-?[0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]+)?\s*$")

# How many inches per unit
UNITS_TO_INCHES = {
    "in": Decimal("1"),
    "mm": Decimal("1") / Decimal("25.4"),
    "cm": Decimal("1") / Decimal("2.54"),
    "pt": Decimal("1") / Decimal("72"),
}
# Inverse mapping for output
INCHES_TO_UNITS = {u: (Decimal("1") / v) for u, v in UNITS_TO_INCHES.items()}

# How we round human-readable values
ROUNDING_INCREMENT = {
    "in": Decimal("0.01"),
    "mm": Decimal("0.1"),
    "cm": Decimal("0.1"),
    "pt": Decimal("1"),
}

class UnitStr:
    """
    Stores any dimension *internally* in inches, based on a given DPI.

    The constructor logic for determining the input unit is as follows:
    1. If `raw` is a string with a unit (e.g., "1.5in"), that unit is used.
    2. If `raw` is a number (e.g., 1.5) or a string without a unit, the
       `unit` parameter is used.
    3. If the `unit` parameter is also not provided, it defaults to 'px'.
    """

    __slots__ = ("_raw", "_value", "_unit", "_dpi", "_cache")

    def __init__(
        self,
        raw: Union[str, float, int, Decimal, "UnitStr"],
        unit: Optional[str] = None,
        *,
        dpi: int = 144,
    ):
        """
        Create a new UnitStr.

        Args:
            raw: The value, either as a string ("1in", "100") or number.
            unit: The unit for `raw` if it's a number or a unitless string.
                  If not provided, defaults to 'px'.
            dpi: The dots-per-inch resolution for 'px' conversion.
        """
        self._raw = str(raw)
        self._dpi = dpi
        self._cache = {}
        internal_unit = "in"  # Internal storage is always inches

        if isinstance(raw, UnitStr):
            self._raw = raw._raw
            self._value = raw._value
            self._unit = internal_unit
            self._dpi = dpi  # Allow overriding DPI on clone
            return

        val_decimal: Decimal
        input_unit: Optional[str] = None

        if isinstance(raw, str):
            m = UNIT_RE.fullmatch(raw.strip())
            if not m:
                raise ValueError(f"Invalid dimension string: {raw!r}")
            value_str, unit_from_str = m.groups()
            val_decimal = Decimal(value_str)
            if unit_from_str:
                input_unit = unit_from_str.lower().replace('"', "in")
        elif isinstance(raw, (int, float, Decimal)):
            val_decimal = Decimal(str(raw))
        else:
            raise TypeError(f"Unsupported type for UnitStr: {type(raw)}")

        # If unit wasn't in the string, use the `unit` param, or default to 'px'.
        if input_unit is None:
            input_unit = (unit or "px").lower().replace('"', "in")

        if input_unit == "px":
            self._value = self._px_to_physical(val_decimal, internal_unit, self._dpi)
        elif input_unit in UNITS_TO_INCHES:
            self._value = self._convert_between_phys(val_decimal, input_unit, internal_unit)
        else:
            raise ValueError(f"Unsupported unit: {input_unit}")

        self._unit = internal_unit

    @classmethod
    def from_px(cls, px: Union[int, float, Decimal], *, dpi: int = 144) -> "UnitStr":
        """Convenience constructor to create a UnitStr from a pixel value."""
        return cls(raw=px, unit="px", dpi=dpi)

    @property
    def dpi(self) -> int:
        return self._dpi

    @property
    def value(self) -> Decimal:
        """Numeric value in the internal physical unit (inches)."""
        return self._value

    @property
    def unit(self) -> str:
        """The internal storage unit (always inches)."""
        return self._unit

    # convenience aliases
    @property
    def inch(self) -> float: return self.to("in")
    @property
    def mm(self)   -> float: return self.to("mm")
    @property
    def pt(self)   -> float: return self.to("pt")
    @property
    def px(self)   -> float: return self.to("px")

    def to(self, target: str, dpi: int | None = None) -> float:
        """
        Convert to target unit. Pixel conversion needs a valid dpi
        (defaults to the one supplied at construction).
        """
        dpi = dpi or self._dpi
        target = target.lower().replace('"', "in")

        key = (target, dpi)
        if key in self._cache:
            return self._cache[key]

        if target == "px":
            if dpi <= 0:
                raise ValueError("DPI must be > 0 for pixel conversion")
            result = float((self._value * dpi).quantize(Decimal("1E-6")))
        elif target in INCHES_TO_UNITS:
            result = float((self._value * INCHES_TO_UNITS[target]).quantize(Decimal("1E-6")))
        else:
            raise ValueError(f"Cannot convert to unsupported unit: {target}")

        self._cache[key] = result
        return result

    def fmt(self, fmt: str = "g", unit: str | None = None, dpi: int | None = None) -> str:
        """Return a formatted string (fmt) in unit (default self.unit), using given DPI for px."""
        unit = (unit or self.unit).lower().replace('"', "in")
        val = self.to(unit, dpi=dpi or self._dpi)
        return f"{format(val, fmt)} {unit}"

    @property
    def round(self) -> "UnitStr":
        """Returns a new UnitStr rounded to a human-friendly increment for its native unit."""
        inc = ROUNDING_INCREMENT.get(self.unit, Decimal("0.01"))
        # Round the value in its native unit (inches)
        value_in_unit = self.value
        rounded_val = round(value_in_unit / inc) * inc
        return UnitStr(f"{rounded_val} {self.unit}", dpi=self._dpi)

    def dict(self) -> dict:
        """JSON-friendly dump of the value in all supported units."""
        return {u: self.to(u) for u in ("in", "mm", "cm", "pt", "px")}

    @classmethod
    def from_dict(
        cls,
        data: dict,
        *,
        unit: str = "in",
        dpi: int = 144,
    ) -> "UnitStr":
        """Rebuild a UnitStr from a dictionary, preferring physical units."""
        unit = unit.lower().replace('"', "in")

        if unit in data:
            return cls(f"{data[unit]} {unit}", dpi=dpi)

        for u in ("in", "mm", "cm", "pt"):
            if u in data:
                return cls(f"{data[u]} {u}", dpi=dpi)

        if "px" in data:
            return cls(data["px"], unit="px", dpi=dpi)

        raise ValueError("UnitStr.from_dict: no recognised unit found in data")

    def __str__(self) -> str:
        return self.fmt(unit="in")

    def __repr__(self) -> str:
        return f"UnitStr('{self._raw}', dpi={self._dpi}) -> {self.value.normalize()}in"

    @staticmethod
    def _px_to_physical(px: Decimal, phys_unit: str, dpi: int) -> Decimal:
        if dpi <= 0:
            raise ValueError("DPI must be > 0 when converting from px")
        inches = px / Decimal(dpi)
        if phys_unit == "in":
            return inches
        return (inches * INCHES_TO_UNITS[phys_unit]).quantize(Decimal("1E-6"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _convert_between_phys(val: Decimal, from_u: str, to_u: str) -> Decimal:
        if from_u == to_u:
            return val
        inches = val * UNITS_TO_INCHES[from_u]
        if to_u == "in":
            return inches
        return (inches * INCHES_TO_UNITS[to_u]).quantize(Decimal("1E-6"), rounding=ROUND_HALF_UP)