# prototypyside/config.py

from PySide6.QtGui import QColor, QPageSize
from enum import Enum, auto


# --- Constants for Resize Handles ---
HANDLE_SIZE = 8
HANDLE_COLOR = QColor(0, 120, 215)
HANDLE_GRAB_WIDTH = 10 # Larger grab area for handles

MEASURE_INCREMENT = {
    "cm": {
        3: 0.25, 
        2: .50,
        1: 1,
    },
    "in": {
        3: 0.0625,
        2: 0.25,
        1: 1.0
    },
    "px": {
        3: 25,
        2: 50,
        1: 100,
    },
    "pt": {
        3: 9,
        2: 36,
        1: 72 
    }
}


VALID_MEASURES = [e for e in MEASURE_INCREMENT]

LIGHTEST_GRAY = 240  # very light gray
DARKEST_GRAY = 200  # dark gray (lower value = darker)

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
