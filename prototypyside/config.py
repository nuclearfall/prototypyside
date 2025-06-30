# prototypyside/config.py

from PySide6.QtGui import Qt, QColor, QPageSize
from enum import Enum, auto


# --- Constants for Resize Handles ---
HANDLE_SIZE = 8
HANDLE_COLOR = QColor(0, 120, 215)
HANDLE_GRAB_WIDTH = 12 # Larger grab area for handles


PAGE_UNITS = {
    "in": QPageSize.Unit.Inch,
    "mm": QPageSize.Unit.Millimeter,
    "pt": QPageSize.Unit.Point,
}

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

DISPLAY_MODE_FLAGS = {
    "stretch":      {"aspect": Qt.IgnoreAspectRatio,         "desc": "Stretch to Fit"},
    "aspect_fit":   {"aspect": Qt.KeepAspectRatio,           "desc": "Keep Aspect Ratio"},
    "aspect_fill":  {"aspect": Qt.KeepAspectRatioByExpanding,"desc": "Fill (Crop to Fit)"},
    "center":       {"aspect": Qt.KeepAspectRatio,           "desc": "Center (No Scaling)"},  # scaling logic must skip resize
    "topleft":      {"aspect": Qt.KeepAspectRatio,           "desc": "Top-Left (No Scaling)"},# scaling logic must skip resize
    "tile":         {"aspect": None,                         "desc": "Tile / Repeat"},        # Custom tiling logic
}


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


