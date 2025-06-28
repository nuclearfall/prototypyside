import re
from decimal import Decimal
from typing import Union

# Constants (assumed already defined)
UNITS_TO_INCHES = {
    "in": Decimal("1.0"),
    "cm": Decimal("1") / Decimal("2.54"),
    "mm": Decimal("1") / Decimal("25.4"),
    "pt": Decimal("1") / Decimal("72.0"),
    "px": None  # handled via DPI
}

INCHES_TO_UNITS = {
    unit: (Decimal("1") / factor if factor else None)
    for unit, factor in UNITS_TO_INCHES.items()
}

UNIT_STR_REGEX = re.compile(r"\s*(\d+(?:\.\d*)?|\.\d+)\s*(px|in|cm|mm|pt|\"?)?\s*", re.IGNORECASE)

class UnitStr:
    __slots__ = ("_raw", "_value", "_unit", "_dpi", "_unit_cache")

    def __init__(self, raw: Union[str, float, int], unit: str = None, dpi: int = 300):
        self._raw = raw
        self._dpi = dpi
        self._unit_cache = {}

        if isinstance(raw, (int, float)):
            self._value = Decimal(str(raw))
            self._unit = "px" if not unit else unit
        elif isinstance(raw, str):
            match = UNIT_STR_REGEX.fullmatch(raw)
            if not match:
                raise ValueError(f"Invalid dimension string: '{raw}'")
            value_str, unit = match.groups()
            self._value = Decimal(value_str)
            self._unit = (unit or "in").lower().strip()
            if self._unit == '"':
                self._unit = "in"
        else:
            raise TypeError(f"Unsupported type for UnitStr: {type(raw)}")

        if self._unit not in UNITS_TO_INCHES:
            raise ValueError(f"Unsupported unit: '{self._unit}'")

    @property
    def dpi(self):
        return self._dpi

    @property
    def inch(self):
        return self.to("in")

    @property
    def px(self):
        return self.to("px", dpi=self._dpi)

    @property
    def mm(self):
        return self.to("mm")

    @property
    def pt(self):
        return self.to("pt")
    
    @property
    def raw(self) -> str:
        return str(self._raw)

    @property
    def value(self) -> Decimal:
        return self._value

    @property
    def unit(self) -> str:
        return self._unit

    def to(self, target_unit: str, dpi: int = None) -> float:
        target_unit = target_unit.lower().strip().replace('"', 'in')
        dpi = dpi or self._dpi

        if target_unit == "px":
            if dpi <= 0:
                raise ValueError("DPI must be > 0 for pixel conversion")
            if dpi not in self._unit_cache:
                self._unit_cache[dpi] = float(
                    (self._value / Decimal(dpi) if self._unit == "px"
                     else self._value * UNITS_TO_INCHES[self._unit] * Decimal(dpi))
                    .quantize(Decimal("0.000001"))
                )
            return self._unit_cache[dpi]

        key = f"{self._unit}->{target_unit}"
        if key in self._unit_cache:
            return self._unit_cache[key]

        if self._unit == "px":
            raise ValueError("Cannot convert from px to non-px unit without DPI")

        inches = self._value * UNITS_TO_INCHES[self._unit]
        result = inches * INCHES_TO_UNITS[target_unit]
        result = float(result.quantize(Decimal("0.000001")))
        self._unit_cache[key] = result
        return result

    def format(self, fmt: str = ".2f", unit: str = None) -> str:
        """
        Formats the value as a string with the given number format and unit.
        Example: UnitStr("25.4 mm").format(".1f", "in") -> "1.0 in"
        """
        unit_type = (unit or self.unit).lower().strip().replace('"', "in")
        value = self.to(unit)
        formatted = format(value, fmt)
        return f"{formatted} {unit}"

    def as_dict(self) -> dict:
        return {
            "in": self.to("in"),
            "mm": self.to("mm"),
            "cm": self.to("cm"),
            "pt": self.to("pt"),
            "px": self.to("px"),
        }

    # def __add__(self, other):
    #     if isinstance(other, UnitStr):
    #         value = self.to(self.unit) + other.to(self.unit)
    #         return UnitStr(value, unit=self.unit, dpi=self.dpi)
    #     elif isinstance(other, (float, int)):
    #         value = self.to(self.unit) + other
    #         return UnitStr(value, unit=self.unit, dpi=self.dpi)
    #     else:
    #         return NotImplemented

    # def __radd__(self, other):
    #     # Supports int/float + UnitStr and also sum() calls.
    #     return self.__add__(other)
        
    # def __sub__(self, other):
    #     # Support subtraction for UnitStr - UnitStr and UnitStr - float/int
    #     if isinstance(other, UnitStr):
    #         # Convert other to self's unit (or to px for safety), subtract
    #         value = self.to("px") - other.to("px")
    #         # Result in px, or optionally in self.unit for chaining
    #         return UnitStr(value, unit="px", dpi=self.dpi)
    #     elif isinstance(other, (float, int)):
    #         return UnitStr(self.to("px") - other, unit="px", dpi=self.dpi)
    #     else:
    #         return NotImplemented

    # def __rsub__(self, other):
    #     if isinstance(other, (float, int)):
    #         return UnitStr(other - self.to("px"), unit="px", dpi=self.dpi)
    #     else:
    #         return NotImplemented

    # def __sub__(self, other):
    #     if isinstance(other, UnitStr):
    #         value = self.to(self.unit) - other.to(self.unit)
    #         return UnitStr(value, unit=self.unit, dpi=self.dpi)
    #     elif isinstance(other, (float, int)):
    #         value = self.to(self.unit) - other
    #         return UnitStr(value, unit=self.unit, dpi=self.dpi)
    #     else:
    #         return NotImplemented

    # def __mul__(self, other):
    #     if isinstance(other, (int, float)):
    #         return UnitStr(self.to(self.unit) * other, unit=self.unit, dpi=self.dpi)
    #     elif isinstance(other, UnitStr):
    #         # Multiplying two lengths doesn't make much sense, but allow if you want
    #         return UnitStr(self.to(self.unit) * other.to(self.unit), unit=self.unit, dpi=self.dpi)
    #     else:
    #         return NotImplemented

    # def __rmul__(self, other):
    #     # Handles int * UnitStr
    #     return self.__mul__(other)

    # def __truediv__(self, other):
    #     if isinstance(other, (int, float)):
    #         return UnitStr(self.to(self.unit) / other, unit=self.unit, dpi=self.dpi)
    #     elif isinstance(other, UnitStr):
    #         # Returns a scalar (unitless ratio)
    #         return self.to(self.unit) / other.to(self.unit)
    #     else:
    #         return NotImplemented

    def __str__(self):
        return self.raw

    def __repr__(self):
        return f"UnitStr(raw='{self.raw}', value={self.value}, unit='{self.unit}', dpi={self.dpi})"
