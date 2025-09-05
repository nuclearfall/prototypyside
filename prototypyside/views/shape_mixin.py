from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Tuple, Optional, Callable, Union
import math

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath

# Expect: UnitStr, ShapeFactory available in your import path
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.services.shape_factory import ShapeFactory  # or wherever you keep it


def _px(v: Union[UnitStr, float, int], dpi: float) -> float:
    if isinstance(v, UnitStr):
        return float(v.to("px", dpi=dpi))
    return float(v)


class ShapeableElementMixin:
    """
    Mixin for elements that can be drawn/clip/selected by a mutable shape.
    Assumes the host class exposes:
      - self.dpi (float)
      - self._geometry (UnitStrGeometry) with .to("px", dpi).rect
      - self.prepareGeometryChange()
      - self.update()
    """

    # --- SERIALIZED state ---
    _shape_kind: str = "rect"          # "rect" | "rounded_rect" | "circle" | "polygon" | "hexagon"
    _shape_params: Dict[str, Any] = None  # e.g. {"radius": "12 pt"} or {"sides": 5}

    # --- Cache ---
    _shape_cache: Optional[Tuple[QRectF, float, str, Tuple[Tuple[str, Any], ...], QPainterPath]] = None

    # -------- public api -------- #
    @property
    def shape_kind(self) -> str:
        return getattr(self, "_shape_kind", "rect")

    @shape_kind.setter
    def shape_kind(self, kind: str):
        if kind != self.shape_kind:
            self.prepareGeometryChange()
            self._shape_kind = kind
            self._invalidate_shape_cache()
            self.update()

    @property
    def shape_params(self) -> Dict[str, Any]:
        return getattr(self, "_shape_params", {}) or {}

    @shape_params.setter
    def shape_params(self, params: Dict[str, Any]):
        # normalize a copy
        params = dict(params or {})
        # sanitize polygon sides
        if self.shape_kind in ("polygon",) and "sides" in params:
            try:
                params["sides"] = max(3, int(params["sides"]))
            except Exception:
                params["sides"] = 3
        self.prepareGeometryChange()
        self._shape_params = params
        self._invalidate_shape_cache()
        self.update()

    def set_shape(self, kind: str, **params: Any):
        """Single call for palette: mutate shape + params atomically."""
        self.prepareGeometryChange()
        self._shape_kind = kind
        self.shape_params = params  # setter invalidates cache & updates

    # -------- drawing / hit helpers -------- #
    def shape_path(self) -> QPainterPath:
        """
        Returns a cached QPainterPath for current geometry/dpi/kind/params.
        """
        rect = self._current_frame_rect_px()
        dpi = float(self.dpi)

        # normalize params -> px where needed (without mutating source)
        params_px = {}
        for k, v in self.shape_params.items():
            if k in ("radius",):  # keys that can be UnitStr
                params_px[k] = _px(v, dpi)
            else:
                params_px[k] = v

        fp = tuple(sorted(params_px.items()))  # fingerprint

        if self._shape_cache is not None:
            cached_rect, cached_dpi, cached_kind, cached_fp, cached_path = self._shape_cache
            if cached_rect == rect and cached_dpi == dpi and cached_kind == self.shape_kind and cached_fp == fp:
                return cached_path

        # build path
        path = self._build_path(rect, dpi, self.shape_kind, params_px)
        self._shape_cache = (QRectF(rect), dpi, self.shape_kind, fp, QPainterPath(path))
        return path

    # Host can override if its "frame" differs from _geometry.px.rect (e.g., overset expansion)
    def _current_frame_rect_px(self) -> QRectF:
        return self._geometry.to("px", dpi=self.dpi).rect

    def _invalidate_shape_cache(self):
        self._shape_cache = None

    # -------- internal -------- #
    def _build_path(self, rect: QRectF, dpi: float, kind: str, params: Dict[str, Any]) -> QPainterPath:
        if kind == "rect":
            return ShapeFactory.rect(rect)

        if kind == "rounded_rect":
            # prefer explicit radius param; fall back to element.corner_radius if present
            radius = params.get("radius", None)
            if radius is None and hasattr(self, "corner_radius"):
                radius = _px(getattr(self, "corner_radius"), dpi)
            else:
                radius = float(radius or 0.0)
            return ShapeFactory.rounded_rect(rect, radius)

        if kind == "circle":
            return ShapeFactory.circle(rect)

        if kind == "polygon":
            sides = max(3, int(params.get("sides", 3)))
            return ShapeFactory.polygon(rect, sides)

        if kind == "hexagon":
            return ShapeFactory.hexagon(rect)

        # default fallback
        return ShapeFactory.rect(rect)
