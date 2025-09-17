# prototypyside/config.py
from PySide6.QtGui import Qt

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


