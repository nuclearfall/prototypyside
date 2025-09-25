"""Render cache utilities for ProtoPaintable objects.

This module provides a lightweight caching layer that memoizes expensive
rendering primitives (scaled rasters and rich text documents).  The cache is
keyed off of the immutable characteristics that influence the generated
output—geometry, DPI, render mode and content fingerprints—so repeated
rendering requests for identical inputs can reuse the cached objects instead of
rebuilding them for every slot/component.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Optional, Tuple, Union

from PySide6.QtGui import QImage, QPixmap, QTextDocument

from prototypyside.utils.render_context import RenderContext

ImageType = Union[QImage, QPixmap]


class RenderCache:
    """Cache container for ProtoPaint rendering artifacts."""

    def __init__(self, ctx: Optional[RenderContext] = None) -> None:
        self._ctx = ctx
        self._image_cache: Dict[Tuple, ImageType] = {}
        self._text_cache: Dict[Tuple, QTextDocument] = {}

    # ------------------------------------------------------------------
    # cache management helpers
    # ------------------------------------------------------------------
    def bind(self, ctx: RenderContext) -> None:
        """Associate the cache with a render context."""

        self._ctx = ctx

    def clear(self) -> None:
        """Drop all cached artifacts."""

        self._image_cache.clear()
        self._text_cache.clear()

    # ------------------------------------------------------------------
    # key builders
    # ------------------------------------------------------------------
    @staticmethod
    def image_key(
        *,
        source: Path | str,
        target_size: Tuple[int, int],
        aspect_mode: int,
        transform_mode: int,
        ctx: RenderContext,
    ) -> Tuple:
        path = Path(source)
        return (
            "img",
            str(path.expanduser().resolve()),
            target_size[0],
            target_size[1],
            int(aspect_mode),
            int(transform_mode),
            int(ctx.dpi),
            ctx.unit,
            ctx.mode.value,
            ctx.tab_mode.value,
            ctx.route.value,
        )

    @staticmethod
    def text_key(
        *,
        content_hash: str,
        font_signature: str,
        width_px: float,
        height_px: float,
        padding_pt: float,
        alignment: int,
        wrap_mode: int,
        color_rgba: Optional[int],
        ctx: RenderContext,
    ) -> Tuple:
        return (
            "text",
            content_hash,
            font_signature,
            round(width_px, 4),
            round(height_px, 4),
            round(padding_pt, 4),
            int(alignment),
            int(wrap_mode),
            int(color_rgba) if color_rgba is not None else None,
            int(ctx.dpi),
            ctx.unit,
            ctx.mode.value,
            ctx.tab_mode.value,
            ctx.route.value,
        )

    # ------------------------------------------------------------------
    # cache accessors
    # ------------------------------------------------------------------
    def image(self, key: Tuple, factory: Callable[[], Optional[ImageType]]) -> Optional[ImageType]:
        cached = self._image_cache.get(key)
        if cached is not None:
            return cached
        generated = factory()
        if generated is not None:
            self._image_cache[key] = generated
        return generated

    def text_document(self, key: Tuple, factory: Callable[[], QTextDocument]) -> QTextDocument:
        cached = self._text_cache.get(key)
        if cached is not None:
            return cached
        doc = factory()
        self._text_cache[key] = doc
        return doc

