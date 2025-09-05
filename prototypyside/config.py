# prototypyside/config.py
from __future__ import annotations
from os import fspath
from pathlib import Path
from typing import Callable, Optional, TypeVar, Union, Iterable
from PySide6.QtGui import Qt, QColor, QPageSize
from enum import Enum, auto

from prototypyside.services.proto_class import ProtoClass



# --- Constants for Resize Handles ---
HANDLE_SIZE = 8
HANDLE_COLOR = QColor(0, 120, 215)
HANDLE_GRAB_WIDTH = 12 # Larger grab area for handles

ALIGNMENT_MAP = {
    "Top Left": Qt.AlignTop | Qt.AlignLeft, 
    "Top Center": Qt.AlignTop | Qt.AlignHCenter,
    "Top Right": Qt.AlignTop | Qt.AlignRight, 
    "Center Left": Qt.AlignVCenter | Qt.AlignLeft,
    "Center": Qt.AlignCenter, 
    "Center Right": Qt.AlignVCenter | Qt.AlignRight,
    "Bottom Left": Qt.AlignBottom | Qt.AlignLeft, 
    "Bottom Center": Qt.AlignBottom | Qt.AlignHCenter,
    "Bottom Right": Qt.AlignBottom | Qt.AlignRight,
}

VMAP = {
    "Top":    Qt.AlignTop,
    "Center": Qt.AlignVCenter,
    "Bottom": Qt.AlignBottom,
}

HMAP = {
    "Left":    Qt.AlignLeft,
    "Center":  Qt.AlignHCenter,
    "Right":   Qt.AlignRight,
    "Justify": Qt.AlignJustify,
}

HMAP_REV = {v: k for k, v in HMAP.items()}
VMAP_REV = {v: k for k, v in VMAP.items()}

def hflag(h: str) -> Qt.Alignment:
    return HMAP.get(h, Qt.AlignLeft)

def vflag(v: str) -> Qt.Alignment:
    return VMAP.get(v, Qt.AlignTop)

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
            "geometry": ProtoClass.UG.new(width="8.5in", height="11in"),
            "unit": "in"
        },
    "legal": {
            "display": "Legal (8.5 × 14 in)",
            "qpage_size": QPageSize.Legal,
            "geometry": ProtoClass.UG.new(width="8.5in", height="14in"),
            "unit": "in"
        },
    "a4": {
            "display": "A4 (210 × 297 mm)",
            "qpage_size": QPageSize.A4,
            "geometry": ProtoClass.UG.new(width="210mm", height="297mm"),
            "unit": "mm"
    },
    "a5": {
            "display": "A5 (148 × 210 mm)",
            "qpage_size": QPageSize.A5,
            "geometry": ProtoClass.UG.new(width="148mm", height="210mm"),
            "unit": "mm"
    },
    "tabloid": {
        "display": "Tabloid (11 × 17 in)",
        "qpage_size": QPageSize.Tabloid,
        "geometry": ProtoClass.UG.new(width="11in", height="17in"),
        "unit": "in"
    },
    "executive": {
        "display": "(7.25 × 10.5 in)",
        "qpage_size": QPageSize.Executive,
        "geometry": ProtoClass.UG.new(width="7.25in", height="10.5in"),
        "unit": "in"
    },
    "b5": {
        "display": "B5 (176 × 250 mm)",
        "qpage_size": QPageSize.B5,
        "geometry": ProtoClass.UG.new(width="176mm", height="250mm"),

    },
    "custom": {
        "display": "Custom...",
        "qpage_size": None,
        "geometry": None # Must enter custom_geometry in ProtoClass.UGField
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
    },
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


