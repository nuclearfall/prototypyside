# prototypyside/config.py

from PySide6.QtGui import QColor, QPageSize
from enum import Enum, auto


# --- Constants for Resize Handles ---
HANDLE_SIZE = 8
HANDLE_COLOR = QColor(0, 120, 215)
HANDLE_GRAB_WIDTH = 10 # Larger grab area for handles

MEASURE_INCREMENT = {"cm": 0.5, "in": 0.25, "\"": 0.25, "px": 20}
MEASURE_ADJUSTMENT = {"cm": 0.05, "in": 0.0125, "px": 5}

# Define handle positions for clarity
class HandleType(Enum):
    TOP_LEFT = auto()
    TOP_RIGHT = auto()
    BOTTOM_LEFT = auto()
    BOTTOM_RIGHT = auto()
    TOP_CENTER = auto()
    BOTTOM_CENTER = auto()
    LEFT_CENTER = auto()
    RIGHT_CENTER = auto()

MIN_ELEMENT_SIZE = 20.0 # Define a minimum size for elements
MIN_ALLOWED_SCALE = 0.8

PAGE_SIZES = {
    "Letter (8.5 × 11 in)": QPageSize.Letter,
    "Legal (8.5 × 14 in)": QPageSize.Legal,
    "A4 (210 × 297 mm)": QPageSize.A4,
    "A5 (148 × 210 mm)": QPageSize.A5,
    "Tabloid (11 × 17 in)": QPageSize.Tabloid,
    "Executive (7.25 × 10.5 in)": QPageSize.Executive,
    "B5 (176 × 250 mm)": QPageSize.B5,
    "Custom...": None  # Placeholder if user wants to enter their own dimensions
}
