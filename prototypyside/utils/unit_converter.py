# prototypyside/utils/unit_converter.py
import re


CM_PER_INCH = 2.54

def parse_dimension(value: str, dpi: int = 72) -> int:
    """
    Parses a dimension string (e.g., '5in', '10cm', '32px') into pixels.
    """
    import re
    value = value.strip().lower()
    match = re.match(r"([0-9.]+)\s*(px|in|cm|\"?)?", value)
    if not match:
        raise ValueError(f"Invalid dimension format: '{value}'")

    num, unit = match.groups()
    num = float(num)
    unit = unit or "in"

    # Aliases
    if unit == "\"":
        unit = "in"

    if unit == "in":
        return inches_to_pixels(num, dpi)
    elif unit == "cm":
        return cm_to_pixels(num, dpi)
    elif unit == "px":
        return int(round(num))  # already in pixels
    else:
        raise ValueError(f"Unsupported unit: {unit}")


def format_dimension(pixels: int, unit: str = "in", dpi: int = 72) -> str:
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
    return int(round(inches * dpi))

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

def convert_from_pixels(pixels: int, unit: str, dpi: int) -> float:
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