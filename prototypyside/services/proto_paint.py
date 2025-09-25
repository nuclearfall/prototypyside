import hashlib
import json

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple, Union

from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import (QPainter, QImage, QPixmap, QPen, 
    QTextOption, QTextLayout, QFontMetricsF, QTextDocument, 
    QTextCursor, QTextCharFormat, QBrush, QImageReader)
from prototypyside.services.proto_class import ProtoClass
from prototypyside.services.shape_factory import ShapeFactory
from prototypyside.utils.render_context import RenderContext
from prototypyside.utils.valid_path import ValidPath
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry

pc = ProtoClass
elem_types = [pc.IE, pc.TE, pc.VE]
image_types = [pc.IE, pc.VE, pc.CT, pc.CC]
zero = UnitStr(0)
Aspect = Qt.AspectRatioMode
Xform  = Qt.TransformationMode
ModeLike = Union[str, Aspect, Tuple[Aspect, Xform]]


@dataclass(frozen=True)
class ImageScaleMode:
    STRETCH: Aspect = Qt.IgnoreAspectRatio
    FIT:     Aspect = Qt.KeepAspectRatio
    FILL:    Aspect = Qt.KeepAspectRatioByExpanding

    FAST:   Xform = Qt.FastTransformation
    SMOOTH: Xform = Qt.SmoothTransformation

    _ASPECTS = {
        "stretch": STRETCH,
        "fit":     FIT,
        "fill":    FILL,
    }
    _XFORMS = {
        "fast":   FAST,
        "smooth": SMOOTH,
    }

    @classmethod
    def resolve(
        cls,
        mode: ModeLike,
        quality: Union[str, Xform, None] = None,
        *,
        default_transform: Xform = SMOOTH
    ) -> Tuple[Aspect, Xform]:
        if isinstance(mode, tuple) and len(mode) == 2:
            aspect, xform = mode
            if quality is not None:
                xform = cls._resolve_xform(quality, default_transform)
            return cls._resolve_aspect(aspect), xform

        aspect = cls._resolve_aspect(mode)
        xform = cls._resolve_xform(quality, default_transform)
        return aspect, xform

    @classmethod
    def _resolve_aspect(cls, a: Union[str, Aspect]) -> Aspect:
        if isinstance(a, str):
            found = cls._ASPECTS.get(a.lower())
            if found is None:
                raise ValueError(f"Unknown aspect mode '{a}'. Use one of: {', '.join(cls._ASPECTS)}.")
            return found
        return a

    @classmethod
    def _resolve_xform(cls, q: Union[str, Xform, None], default: Xform) -> Xform:
        if q is None:
            return default
        if isinstance(q, str):
            found = cls._XFORMS.get(q.lower())
            if found is None:
                raise ValueError(f"Unknown transform '{q}'. Use one of: {', '.join(cls._XFORMS)}.")
            return found
        return q

    @classmethod
    def stretch(cls) -> Tuple[Aspect, Xform]:
        return cls.STRETCH, cls.SMOOTH

    @classmethod
    def fit(cls) -> Tuple[Aspect, Xform]:
        return cls.FIT, cls.SMOOTH

    @classmethod
    def fill(cls) -> Tuple[Aspect, Xform]:
        return cls.FILL, cls.SMOOTH


SHAPES = {
    "rect":         ShapeFactory.rect,
    "rounded_rect": ShapeFactory.rounded_rect,
    "oval":         ShapeFactory.oval,
    "hexagon":      ShapeFactory.hexagon,
    "diamond":      ShapeFactory.diamond,
    "octagon":      ShapeFactory.octagon,
    "polygon":      ShapeFactory.polygon,
    "default":      None,
}




# imports you’ll likely need
from PySide6.QtCore import QSize, QRect
from PySide6.QtGui import (QImage, QPixmap, QImageReader, QPainter,
                           Qt)

class ProtoPaint:
    @classmethod
    def _target_size_px(cls, geom: UnitStrGeometry, ctx: RenderContext) -> Tuple[int, int]:
        geom_px = geom.to("px", dpi=ctx.dpi)
        w_px = max(1, round(float(geom_px.size.width())))
        h_px = max(1, round(float(geom_px.size.height())))
        return w_px, h_px

    @classmethod
    def _generate_scaled_image(
        cls,
        image_path: Path,
        geom: UnitStrGeometry,
        ctx: RenderContext,
        aspect_mode: Aspect,
        xform_mode: Xform,
    ):
        if not ValidPath.check(image_path, must_exist=True):
            return None

        try:
            if ctx.is_export:
                reader = QImageReader(str(image_path))
                reader.setAutoTransform(True)
                base_img = reader.read()
                if base_img.isNull():
                    return None
                base = base_img
            else:
                base_px = QPixmap(str(image_path))
                if base_px.isNull():
                    return None
                base = base_px

            w_px, h_px = cls._target_size_px(geom, ctx)
            target_px_size = QSize(w_px, h_px)

            scaled = base.scaled(target_px_size, aspect_mode, xform_mode)

            if aspect_mode == Qt.KeepAspectRatioByExpanding:
                sw, sh = scaled.width(), scaled.height()
                if (sw, sh) != (w_px, h_px):
                    cx = max(0, (sw - w_px) // 2)
                    cy = max(0, (sh - h_px) // 2)
                    crop_rect = QRect(cx, cy, w_px, h_px)
                    scaled = scaled.copy(crop_rect)

            return scaled
        except Exception as e:
            print(f"Image load/scale failed: {e}")
            return None

    @classmethod
    def image_with_mode(
        cls,
        image_path: Path,
        geom: UnitStrGeometry,
        ctx: RenderContext,
        aspect: ModeLike,
        transform: Union[str, Xform, None] = None,
        cache=None,
    ):
        """
        Returns a QImage (export) or QPixmap (GUI) already scaled to the px size
        implied by `geom` at `ctx.dpi`, respecting aspect + transform.
        For FILL (KeepAspectRatioByExpanding) we crop the overshoot to avoid
        a second scale later.
        """
        aspect_mode, xform_mode = ImageScaleMode.resolve(aspect, transform)
        w_px, h_px = cls._target_size_px(geom, ctx)

        cache_obj = cache or getattr(ctx, "cache", None)

        def factory():
            return cls._generate_scaled_image(image_path, geom, ctx, aspect_mode, xform_mode)

        if cache_obj is not None:
            key = cache_obj.image_key(
                source=image_path,
                target_size=(w_px, h_px),
                aspect_mode=int(aspect_mode),
                transform_mode=int(xform_mode),
                ctx=ctx,
            )
            return cache_obj.image(key, factory)

        return factory()

    @classmethod
    def _build_text_document(
        cls,
        obj,
        ctx: RenderContext,
        width_px: float,
        padding_pt: float,
        alignment,
        wrap_mode,
        color,
    ) -> QTextDocument:
        doc = QTextDocument(getattr(obj, "content", "") or "")

        font = getattr(obj, "font", None)
        if font is not None:
            qfont = font.scale(ldpi=144, dpi=ctx.dpi).to("pt", dpi=ctx.dpi).qfont
            doc.setDefaultFont(qfont)

        doc.setDocumentMargin(padding_pt)
        doc.setTextWidth(width_px)

        opt = QTextOption()
        opt.setWrapMode(QTextOption.WrapMode(int(wrap_mode)))
        opt.setAlignment(Qt.Alignment(int(alignment)))
        doc.setDefaultTextOption(opt)

        if color is not None:
            cursor = QTextCursor(doc)
            cursor.select(QTextCursor.Document)
            fmt = QTextCharFormat()
            fmt.setForeground(QBrush(color))
            cursor.mergeCharFormat(fmt)

        return doc

    @classmethod
    def text_document(
        cls,
        obj,
        ctx: RenderContext,
        *,
        geom_pt: Optional[UnitStrGeometry] = None,
        cache=None,
    ) -> QTextDocument:
        geom_pt = geom_pt or cls.ctx_geom(obj.geometry, ctx)
        geom_px = geom_pt.to("px", dpi=ctx.dpi)
        width_px = float(geom_px.size.width())
        height_px = float(geom_px.size.height())

        padding = getattr(obj, "padding", None)
        padding_pt = padding.to("pt", dpi=ctx.dpi).value if padding is not None else 0.0

        alignment = getattr(obj, "h_align", Qt.AlignLeft | Qt.AlignTop)
        wrap_mode = getattr(obj, "wrap_mode", QTextOption.WordWrap)
        color = getattr(obj, "color", None)

        font = getattr(obj, "font", None)
        font_signature = ""
        if font is not None and hasattr(font, "to_dict"):
            font_signature = json.dumps(font.to_dict(), sort_keys=True)

        content = getattr(obj, "content", "") or ""
        content_hash = hashlib.sha1(content.encode("utf-8")).hexdigest()

        cache_obj = cache or getattr(ctx, "cache", None)

        def factory() -> QTextDocument:
            return cls._build_text_document(
                obj,
                ctx,
                width_px,
                padding_pt,
                alignment,
                wrap_mode,
                color,
            )

        if cache_obj is not None:
            key = cache_obj.text_key(
                content_hash=content_hash,
                font_signature=font_signature,
                width_px=width_px,
                height_px=height_px,
                padding_pt=padding_pt,
                alignment=int(alignment),
                wrap_mode=int(wrap_mode),
                color_rgba=color.rgba() if color is not None else None,
                ctx=ctx,
            )
            return cache_obj.text_document(key, factory)

        return factory()


    @classmethod
    def ensure_local(cls, geom: UnitStrGeometry, dpi: float) -> UnitStrGeometry:
        w, h = geom.size_tuple()
        x, y = geom.pos_tuple()
        return UnitStrGeometry(width=w, height=h, x=x, y=y, dpi=dpi)

    @classmethod
    def ctx_geom(cls, geom: UnitStrGeometry, ctx: RenderContext) -> UnitStrGeometry:
        return cls.ensure_local(geom, ctx.dpi).to(ctx.unit, dpi=ctx.dpi)

    @classmethod
    def ctx_ustr(cls, ustr: UnitStr, ctx: RenderContext) -> UnitStr:
        return ustr.to(ctx.unit, dpi=ctx.dpi)

    @classmethod
    def shape_path(cls, shp: str, geom: UnitStrGeometry, ctx: RenderContext, *, extra=None, adjusts=None):
        # geom is expected to be UnitStrGeometry in LOCAL coords; adjust by UnitStr deltas in ctx.unit
        fin_geom = geom
        if adjusts:
            gt = geom.ustr_tuple(unit=ctx.unit, dpi=ctx.dpi)
            adjusted = [g+adj for g, adj in zip(gt, adjusts)]
            dx, dy, dw, dh = adjusted
            fin_geom = UnitStrGeometry(width=dw, height=dh, x=dx, y=dy, unit=ctx.unit, dpi=ctx.dpi)
        fn = SHAPES.get(shp) or SHAPES["default"]
        return fn(fin_geom, extra=extra) if fn else None

    @classmethod
    def border_shape_path(cls, shp: str, geom: UnitStrGeometry, ctx: RenderContext, bw: UnitStr, extra=None):
        bw_u = cls.ctx_ustr(bw, ctx)
        if bw_u <= UnitStr(0.0):
            return None
        adjusts = (-bw*(1/2), -bw*(1/2), bw*(1/2), bw*(1/2))
        return cls.shape_path(shp, geom, ctx, adjusts=adjusts, extra=extra)

    @classmethod
    def bleed_shape_path(cls, shp: str, geom: UnitStrGeometry, ctx: RenderContext, bleed: UnitStr, extra=None, include_bleed: bool = False):
        if not include_bleed:
            return None
        bleed_u = cls.ctx_ustr(bleed, ctx)
        if bleed_u <= UnitStr(0, unit=ctx.unit, dpi=ctx.dpi):
            return None
        b = bleed_u.value
        adjusts = (-b, -b, +2*b, +2*b)  # expand on all sides
        return cls.shape_path(shp, geom, ctx, extra=extra, adjusts=adjusts)

    @classmethod
    def paint_bleed_path(cls, obj, ctx: RenderContext, painter: QPainter):
        geom = obj.geometry
        shape = obj.shape
        bleed = obj.bleed
        bw = cls.ctx_ustr(obj.border_width, ctx)

        extra = None
        if shape == "rounded_rect" and bw >= UnitStr(0):
            extra = obj.corner_radius
        if shape == "polygon" and getattr(obj, "sides", None):
            extra = obj.sides

        path = cls.bleed_shape_path(shape, geom, ctx, bleed=bleed, extra=extra, include_bleed=obj.include_bleed)
        color = obj.border_color if bw > UnitStr(0.0) else obj.bg_color

        if path:
            painter.save()
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawPath(path)
            painter.restore()

    @classmethod
    def paint_border_path(cls, obj, ctx: RenderContext, painter: QPainter):
        bw = cls.ctx_ustr(obj.border_width, ctx)
        if bw <= UnitStr(0, unit=ctx.unit, dpi=ctx.dpi):
            return

        geom = obj.geometry
        shape = obj.shape

        extra = None
        if shape == "rounded_rect" and bw >= UnitStr(0):
            extra = obj.corner_radius
        if shape == "polygon" and getattr(obj, "sides", None):
            extra = obj.sides

        path = cls.border_shape_path(shape, geom, ctx, bw=bw, extra=extra)
        if path is None:
            return

        color = obj.border_color
        bw_f = float(cls.ctx_ustr(bw, ctx).value)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(color)
        pen.setWidthF(bw_f)
        pen.setJoinStyle(Qt.MiterJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)
        painter.restore()

    @classmethod
    def paint_text_path(cls, obj, ctx, painter, extra=None):
        """
        Render rich text into obj.geometry using a clip path, all in PT coordinates.
        Assumes UnitStrFont.qfont() returns a QFont sized in points.
        """
        # --- 1) Geometry & clip path in PT ---
        # ctx_geom returns a geom in pts 
        geom_pt = cls.ctx_geom(obj.geometry, ctx)
        shape = obj.shape
        extra = (
            obj.corner_radius if shape == "rounded_rect"
            else (obj.sides if shape == "polygon" else None)
        )
        clip_shape_path = cls.shape_path(shape, geom_pt, ctx, extra=extra)

        # --- 2) Build or fetch cached QTextDocument ---
        doc = cls.text_document(obj, ctx, geom_pt=geom_pt)

        # --- 3) Paint in PT coordinates (no manual scaling) ---
        painter.save()
        painter.setClipping(True)
        painter.setClipPath(clip_shape_path)
        doc.drawContents(painter, geom_pt.rect)
        painter.restore()


    @classmethod
    def paint_background_path(cls, obj, ctx: RenderContext, painter: QPainter):
        if obj.bg_color.alpha() <= 0:
            return

        geom = obj.geometry
        shape = obj.shape

        extra = None
        if shape == "rounded_rect":
            extra = obj.corner_radius
        if shape == "polygon" and getattr(obj, "sides", None):
            extra = obj.sides

        path = cls.shape_path(shape, cls.ctx_geom(geom, ctx), ctx, extra=extra)

        painter.save()
        painter.setPen(Qt.NoPen)
        painter.fillPath(path, obj.bg_color)
        painter.restore()

    @classmethod
    def paint_image(cls, obj, ctx: RenderContext, painter: QPainter):
        # Resolve the geometry you intend to paint (bleed vs no-bleed, etc.)
        wants_bleed = obj.bleed > zero and obj.include_bleed
        base_geom = obj.geometry
        final_geom = base_geom.outset(obj.bleed, obj.bleed) if wants_bleed else base_geom

        # Dest rects in your two coordinate systems
        geom_px = final_geom.to("px", dpi=ctx.dpi)  # GUI
        geom_pt = final_geom.to("pt", dpi=ctx.dpi)  # PDF export (points)

        # choose target rect based on ctx
        target_rect = geom_pt.rect if ctx.is_export else geom_px.rect

        # Choose the right aspect + transform for this element
        # (assuming obj.aspect is one of "stretch"/"fit"/"fill" mapped by your ImageScaleMode
        #  and obj.xform in {"fast","smooth"} or None)
        aspect = obj.aspect
        xform  = getattr(obj, "xform", None)

        image_path = ValidPath.file(obj.content, must_exist=True)
        if not image_path:
            return

        # Get the raster sized for the px target box at ctx.dpi
        raster = cls.image_with_mode(image_path, final_geom, ctx, aspect, xform)
        if raster is None:
            return

        # Hint: enable smoothing only when using Smooth transformation
        # (it mainly affects downscales / non-integer transforms on draw)
        _, xform_mode = ImageScaleMode.resolve(aspect, xform)
        painter.save()

        painter.setRenderHint(QPainter.SmoothPixmapTransform, xform_mode == Qt.SmoothTransformation)

        target_rectF = target_rect if hasattr(target_rect, "toRectF") else target_rect

        # src rect is the full raster
        if isinstance(raster, QPixmap):
            src_rectF = QRectF(0, 0, raster.width(), raster.height())
            painter.drawPixmap(target_rectF, raster, src_rectF)
        else:  # QImage
            src_rectF = QRectF(0, 0, raster.width(), raster.height())
            painter.drawImage(target_rectF, raster, src_rectF)
        painter.restore()


    @classmethod
    def paint_element_outline(cls, elem, ctx, painter):
        """
        Simple outline rendering for ImageElement-like items (pc.IE).
        Uses elem.outline (ElementOutline instance) for both outline and handles.
        """
        ol = elem.outline  # ElementOutline
        # Keep geometry/handles in sync with current element rect
        ol._on_geometry_changed()
        ol.update_visibility_policy()
        # Paint the outline box; handles are separate QGraphicsObjects
        # and manage their own paint via the scene
        ol.render(ctx, painter)

    # @classmethod
    # def paint_text_outline(cls, ctx, elem, painter):
    #     """
    #     Text outline rendering for TextElement-like items (pc.TE).
    #     Delegates to elem.outline (TextOutline) so overset UI and handles show.
    #     """
    #     ol = elem.outline  # TextOutline
    #     # Keep geometry/handles in sync (includes overset frame logic)
    #     ol._on_geometry_changed()
    #     ol.update_visibility_policy()
    #     # Paint text-specific outline (overset button/box etc.)
    #     ol.render(painter, option, widget)

    @classmethod
    def paint_outline(cls, elem, ctx, painter):
        """
        Dispatcher: call the correct outline renderer for the element type.
        pc.VE intentionally ignored for now.
        """
        # if elem.proto == pc.IE:
        cls.paint_element_outline(elem, ctx, painter)
        # elif elem.proto == pc.TE:
        #     cls.paint_text_outline(elem, ctx, painter)

    @classmethod
    def paint_placeholder_text(cls, obj, ctx, painter: QPainter):
        """
        Draw placeholder text
        """
        font = obj.font
        rect = ojb.geometry.to(ctx.unit, dpi=ctx.dpi)
        painter.save()
        painter.setPen(QPen(Qt.darkGray))
        font = UnitStrFont(family="Arial", size=10, italic=True, dpi=ctx.dpi)
        painter.setFont(font.scale(ldpi=144, dpi=ctx.dpi).to("px", dpi=ctx.dpi))
        painter.drawText(rect, (obj.h_align | obj.v_align), 
                        "Drop Image\nor Double Click to Set")
        painter.restore()

    @classmethod
    def render(cls, obj, ctx: RenderContext, painter: QPainter):
        geom = obj.geometry
        include_bleed = obj.include_bleed
        bw = cls.ctx_ustr(obj.border_width, ctx)

        zero = UnitStr(0)
        wants_bleed = include_bleed and obj.bleed > zero
        has_image = False
        if obj.proto in image_types:
            has_image = ValidPath.check(obj.content, must_exist=True)

        if not has_image and wants_bleed:
            cls.paint_bleed_path(obj, ctx, painter)

        if not has_image and obj.bg_color.alpha() > 0:
            cls.paint_background_path(obj, ctx, painter)

        if obj.proto in image_types and has_image:
            cls.paint_image(obj, ctx, painter)

        if ctx.is_gui and ctx.is_component_tab and not has_image:
            if obj.proto == pc.TE:
                cls.paint_text_path(obj, ctx, painter)
            if obj.proto == pc.IE or obj.proto == pc.VE:
                cls.paint_placeholder_text(obj, ctx, painter)

        cls.paint_border_path(obj, ctx, painter)

        # paint_outline will only draw if ctx.is_gui and ctx.is_component_tab
        if pc.isproto(obj, elem_types):
            cls.paint_outline(obj, ctx, painter)
