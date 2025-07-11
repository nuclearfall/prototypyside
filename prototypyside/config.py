# prototypyside/config.py

from PySide6.QtGui import Qt, QColor, QPageSize
from enum import Enum, auto

from prototypyside.utils.unit_str_geometry import UnitStrGeometry

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
    "letter":
        {
            "display":  "Letter (8.5 × 11 in)",
            "qpage_size": QPageSize.Letter,
            "geometry": UnitStrGeometry(width="8.5in", height="11in"),
            "unit": "in"
        },
    "legal": {
            "display": "Legal (8.5 × 14 in)",
            "qpage_size": QPageSize.Legal,
            "geometry": UnitStrGeometry(width="8.5in", height="14in"),
            "unit": "in"
        },
    "a4": {
            "display": "A4 (210 × 297 mm)",
            "qpage_size": QPageSize.A4,
            "geometry": UnitStrGeometry(width="210mm", height="297mm"),
            "unit": "mm"
    },
    "a5": {
            "display": "A5 (148 × 210 mm)",
            "qpage_size": QPageSize.A5,
            "geometry": UnitStrGeometry(width="148mm", height="210mm"),
            "unit": "mm"
    },
    "tabloid": {
        "display": "Tabloid (11 × 17 in)",
        "qpage_size": QPageSize.Tabloid,
        "geometry": UnitStrGeometry(width="11in", height="17in"),
        "unit": "in"
    },
    "executive": {
        "display": "(7.25 × 10.5 in)",
        "qpage_size": QPageSize.Executive,
        "geometry": UnitStrGeometry(width="7.25in", height="10.5in"),
        "unit": "in"
    },
    "b5": {
        "display": "B5 (176 × 250 mm)",
        "qpage_size": QPageSize.B5,
        "geometry": UnitStrGeometry(width="176mm", height="250mm"),

    },
    "custom": {
        "display": "Custom...",
        "qpage_size": None,
        "geometry": None # Must enter custom_geometry in UnitStrGeometryField
    }
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
        1: 2.0,
    },
    "mm": {
        3: 5, 
        2: 10,
        1: 20,
    },
    "in": {
        3: 0.125,
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

MIN_ELEMENT_SIZE = 20.0 # Define a minimum size for items
MIN_ALLOWED_SCALE = 0.8


