import re
from typing import List, Dict, Tuple
from PySide6.QtCore import QRectF, QPointF
from PySide6.QtGui import QPageSize

from prototypyside.utils.unit_str import UnitStr

UNITS_TO_INCHES = {
    "in": 1.0,
    "cm": 1 / 2.54,
    "mm": 1 / 25.4,
    "pt": 1 / 72.0,
    "px": None  # special case
}
INCHES_TO_UNITS = {
    "in": 1.0,
    "cm": 2.54,
    "mm": 25.4,
    "pt": 72.0,
}

def parse_dimension(value, dpi: int = 300, to_unit: str = "px") -> float:
    """
    Parses a dimension string or number into the target unit.
    Supported units: "in", "cm", "mm", "pt", "px"
    If value is numeric, it's assumed to be px unless to_unit is px (in which case just returns value).
    """
    # Normalize unit (for output)
    to_unit = to_unit.lower().replace('"', "in").strip()
    if to_unit not in UNITS_TO_INCHES:
        raise ValueError(f"Unsupported target unit: {to_unit}")

    # Parse input value
    if isinstance(value, (int, float)):
        # Numeric input is always px
        px_val = float(value)
    else:
        value = str(value).strip().lower().replace('"', "in")
        # Regex: capture value and optional unit
        match = re.match(r"([0-9.]+)\s*([a-z]+)?", value)
        if not match:
            raise ValueError(f"Invalid dimension format: '{value}'")
        num, unit = match.groups()
        num = float(num)
        unit = (unit or "in").strip()
        if unit not in UNITS_TO_INCHES:
            raise ValueError(f"Unsupported input unit: {unit}")
        if unit == "px":
            px_val = num
        else:
            # Convert input to inches
            inches = num * UNITS_TO_INCHES[unit]
            px_val = inches * dpi

    # Now px_val holds the dimension in px
    if to_unit == "px":
        return px_val
    elif to_unit == "in":
        return px_val / dpi
    else:
        # Convert px to inches, then inches to to_unit
        inches = px_val / dpi
        return inches * INCHES_TO_UNITS[to_unit]

def from_px_unit(px_unit, unit, dpi):
    return parse_dimension(px_unit, unit=unit, dpi=dpi)

def format_dimension(pixels: float, unit: str = "in", dpi: int = 300) -> str:
    if unit == "in":
        return f"{pixels_to_inches(pixels, dpi):.2f} in"
    elif unit == "cm":
        return f"{pixels_to_cm(pixels, dpi):.2f} cm"
    elif unit == "px":
        return f"{pixels:.0f} px"
    else:
        raise ValueError(f"Unsupported unit: {unit}")

def inches_to_pixels(inches: float, dpi: int) -> int:
    """
    Converts a measurement in inches to pixels.
    Args:
        inches (float): The measurement in inches.
        dpi (int): Dots Per Inch.
    Returns:
        int: The measurement in pixels (rounded to the nearest integer).
    Raises:
        ValueError: If DPI is not positive.
    """
    if dpi <= 0:
        raise ValueError("DPI must be a positive value.")
    return inches * dpi

def pixels_to_inches(pixels: int, dpi: int) -> float:
    """
    Converts a measurement in pixels to inches.
    Args:
        pixels (int): The measurement in pixels.
        dpi (int): Dots Per Inch.
    Returns:
        float: The measurement in inches.
    Raises:
        ValueError: If DPI is not positive.
    """
    if dpi <= 0:
        raise ValueError("DPI must be a positive value.")
    return pixels / dpi

def cm_to_pixels(cm: float, dpi: int) -> int:
    """
    Converts a measurement in centimeters to pixels.
    Args:
        cm (float): The measurement in centimeters.
        dpi (int): Dots Per Inch.
    Returns:
        int: The measurement in pixels (rounded to the nearest integer).
    Raises:
        ValueError: If DPI is not positive.
    """
    if dpi <= 0:
        raise ValueError("DPI must be a positive value.")
    inches = cm / CM_PER_INCH
    return inches_to_pixels(inches, dpi)

def pixels_to_cm(pixels: int, dpi: int) -> float:
    """
    Converts a measurement in pixels to centimeters.
    Args:
        pixels (int): The measurement in pixels.
        dpi (int): Dots Per Inch.
    Returns:
        float: The measurement in centimeters.
    Raises:
        ValueError: If DPI is not positive.
    """
    if dpi <= 0:
        raise ValueError("DPI must be a positive value.")
    inches = pixels_to_inches(pixels, dpi)
    return inches * CM_PER_INCH

def convert_to_pixels(value: float, unit: str, dpi: int) -> int:
    """
    Converts a value from a specified unit ('in' or 'cm') to pixels.
    Args:
        value (float): The measurement value.
        unit (str): The unit of measurement ('in' for inches, 'cm' for centimeters).
        dpi (int): Dots Per Inch.
    Returns:
        int: The measurement in pixels.
    Raises:
        ValueError: If an unsupported unit is provided or DPI is not positive.
    """
    if dpi <= 0:
        raise ValueError("DPI must be a positive value.")

    if unit.lower() == 'in':
        return inches_to_pixels(value, dpi)
    elif unit.lower() == 'cm':
        return cm_to_pixels(value, dpi)
    else:
        raise ValueError("Unsupported unit. Use 'in' for inches or 'cm' for centimeters.")

def from_px(pixels: int, unit: str, dpi: int) -> float:
    """
    Converts a value from pixels to a specified unit ('in' or 'cm').
    Args:
        pixels (int): The measurement in pixels.
        unit (str): The target unit of measurement ('in' for inches, 'cm' for centimeters).
        dpi (int): Dots Per Inch.
    Returns:
        float: The measurement in the target unit.
    Raises:
        ValueError: If an unsupported unit is provided or DPI is not positive.
    """
    if dpi <= 0:
        raise ValueError("DPI must be a positive value.")

    if unit.lower() == 'in':
        return pixels_to_inches(pixels, dpi)
    elif unit.lower() == 'cm':
        return pixels_to_cm(pixels, dpi)
    else:
        raise ValueError("Unsupported unit. Use 'in' for inches or 'cm' for centimeters.")

def to_px(value, dpi=300):
    return parse_dimension(value, dpi=dpi, to_unit="px")

def to_px_pos(x, y, dpi=300):
    # Return as QPointF instead of tuple to work with setPos
    return QPointF(
        parse_dimension(x, dpi=dpi, to_unit="px"),
        parse_dimension(y, dpi=dpi, to_unit="px")
    )

def to_px_qrectf(x, y, w, h, dpi=300):
    return QRectF(
        parse_dimension(x, dpi=dpi, to_unit="px"),
        parse_dimension(y, dpi=dpi, to_unit="px"),
        parse_dimension(w, dpi=dpi, to_unit="px"),
        parse_dimension(h, dpi=dpi, to_unit="px")
    )

def convert_px_dpi(px_value, old_dpi, new_dpi):
    return px_value * (new_dpi / old_dpi)

def pos_to_unit_str(scene_pos: QPointF, unit: str = None, dpi: int = None):
    """
    Convert a scene position (px) to (x, y) UnitStrs in the desired unit and dpi.
    If unit or dpi is not provided, uses self.tab.settings.
    """
    unit = unit
    dpi = dpi

    x_px = scene_pos.x()
    y_px = scene_pos.y()

    if unit == "in":
        logical_x = x_px / dpi
        logical_y = y_px / dpi
    elif unit == "mm":
        logical_x = (x_px / dpi) * 25.4
        logical_y = (y_px / dpi) * 25.4
    elif unit == "cm":
        logical_x = (x_px / dpi) * 2.54
        logical_y = (y_px / dpi) * 2.54
    elif unit == "pt":
        logical_x = (x_px / dpi) * 72.0
        logical_y = (y_px / dpi) * 72.0
    else:
        logical_x = x_px / dpi
        logical_y = y_px / dpi

    return (
        UnitStr(logical_x, unit=unit, dpi=dpi),
        UnitStr(logical_y, unit=unit, dpi=dpi)
    )

def px_to_physical(px_value, target_unit, dpi):
    """
    Converts a pixel value to a physical value in the given unit at the specified DPI.
    Supported units: 'in', 'mm', 'cm', 'pt'
    """
    if target_unit == "in":
        return px_value / dpi
    elif target_unit == "mm":
        return (px_value / dpi) * 25.4
    elif target_unit == "cm":
        return (px_value / dpi) * 2.54
    elif target_unit == "pt":
        return (px_value / dpi) * 72.0
    else:
        raise ValueError(f"Unsupported target unit: {target_unit}")


def qrectf_to_list(rect: QRectF) -> List[float]:
    return [rect.x(), rect.y(), rect.width(), rect.height()]

def list_to_qrectf(data: List[float]) -> QRectF:
    if len(data) == 4:
        return QRectF(data[0], data[1], data[2], data[3])
    raise ValueError("Invalid QRectF data: must be a list of 4 floats.")

def qpointf_to_list(point: QPointF) -> List[float]:
    return [point.x(), point.y()]

def list_to_qpointf(data: List[float]) -> QPointF:
    if len(data) == 2:
        return QPointF(data[0], data[1])
    raise ValueError("Invalid QRectF data: must be a list of 4 floats.")


def page_in_units(page_size_obj: QPageSize, unit_str: str, dpi) -> Dict[str, str]:
    """
    Returns the width and height of a QPageSize object in the specified unit string.

    Args:
        page_size_obj: The QPageSize object representing the page.
        unit_str: The desired unit as a string (e.g., "in", "cm", "pt", "mm").
                  Case-insensitive.

    Returns:
        A dictionary with 'width' and 'height' as unit-formatted strings
        (e.g., {'width': '10.50in', 'height': '7.20cm'}).
        Returns values formatted to two decimal places.

    Raises:
        ValueError: If an unsupported unit string is provided.
    """
    unit_str_lower = unit_str.lower()

    if unit_str_lower not in _Q_PAGE_SIZE_UNIT_MAP:
        raise ValueError(
            f"Unsupported unit string: '{unit_str}'. "
            f"Supported units are: {', '.join(list(_Q_PAGE_SIZE_UNIT_MAP.keys()))}"
        )

    # Determine the QPageSize.Unit enum to pass to page_size_obj.size()
    q_page_unit_enum = _Q_PAGE_SIZE_UNIT_MAP[unit_str_lower]

    # Get dimensions from QPageSize in the base unit (e.g., mm if 'cm' was requested)
    dims_qsizef: QSizeF = page_size_obj.size(q_page_unit_enum)
    width = dims_qsizef.width()
    height = dims_qsizef.height()

    # Apply any specific conversion factors for display (e.g., mm to cm)
    display_factor = _UNIT_DISPLAY_FACTOR.get(unit_str_lower, 1.0) # Default to 1.0 if not specified
    width /= display_factor
    height /= display_factor

    # Format the output strings to two decimal places for consistency
    formatted_width = f"{width:.2f}{unit_str_lower}"
    formatted_height = f"{height:.2f}{unit_str_lower}"

    return formatted_width, formatted_height

_Q_PAGE_SIZE_UNIT_MAP = {
    "pt": QPageSize.Point,
    "in": QPageSize.Inch,
    "mm": QPageSize.Millimeter,
    "cm": QPageSize.Millimeter, # We'll convert from mm to cm
}

def page_in_px(page_size_obj: QPageSize, dpi: float) -> Dict[str, float]:
    """
    Returns the width and height of a QPageSize object in pixels.

    Args:
        page_size_obj: The QPageSize object representing the page.
        dpi: The Dots Per Inch value to use for conversion. This is a required parameter,
             typically obtained from application settings or a screen's DPI.

    Returns:
        A dictionary with 'width' and 'height' as float values in pixels.

    Raises:
        ValueError: If DPI is not a positive value.
    """
    if dpi <= 0:
        raise ValueError("DPI must be a positive value to convert to pixels.")

    # Get the dimensions of the page in inches first.
    # DPI is a conversion factor from inches to pixels.
    dims_in_inches: QSizeF = page_size_obj.size(QPageSize.Inch)

    # Convert width and height from inches to pixels
    width_px = dims_in_inches.width() * dpi
    height_px = dims_in_inches.height() * dpi

    return width_px, height_px

def compute_scale_factor(
    max_size: Tuple[float, float],
    current_size: Tuple[float, float]
) -> float:
    """
    Given max_size (width, height) and current_size (width, height),
    return the uniform scale factor ≤ 1.0 needed to make
    current_size fit inside max_size.  Returns 1.0 if no scaling needed.
    """
    max_w, max_h = max_size
    cur_w, cur_h = current_size

    # avoid division by zero; if cur dimension is zero, treat it as no scale needed
    if cur_w <= 0 or cur_h <= 0:
        return 1.0

    # if already fits, no scaling
    if cur_w <= max_w and cur_h <= max_h:
        return 1.0

    scale_w = max_w / cur_w
    scale_h = max_h / cur_h
    return min(scale_w, scale_h)