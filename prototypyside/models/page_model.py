# models/page_models.py
from dataclasses import dataclass
from typing import List, Optional
from PySide6.QtCore import QRectF

@dataclass(frozen=True)
class Page:
    index: int
    angle: float       # absolute page rotation deg
    rect_px: QRectF    # page rect in px (after UnitStrGeometry->px)
    slot_angles: List[float]  # final, per-slot absolute angles (deg)
    # GUI: we’ll also return a root QGraphicsItem from PageManager.mount()
