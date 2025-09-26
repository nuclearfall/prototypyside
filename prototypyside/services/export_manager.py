# export_manager.py
from math import ceil
from pathlib import Path
from itertools import zip_longest

from PySide6.QtCore import Qt, QSizeF, QRectF, QMarginsF, QPointF
from PySide6.QtGui  import QPainter, QColor, QPdfWriter, QImage, QPageSize, QPageLayout, QTransform
from PySide6.QtWidgets import QGraphicsScene, QStyleOptionGraphicsItem, QGraphicsItem

from prototypyside.models.layout_slot import LayoutSlot
from prototypyside.models.component_template import ComponentTemplate
from prototypyside.models.text_element import TextElement
from prototypyside.utils.units.unit_str import UnitStr #, unitstr_from_raw
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry

from prototypyside.services.app_settings import AppSettings
from prototypyside.services.proto_registry import ProtoRegistry
from prototypyside.services.proto_class import ProtoClass
from prototypyside.services.proto_paint import ProtoPaint
from prototypyside.utils.render_context import RenderContext, RenderMode, RenderRoute, TabMode
from prototypyside.services.render_cache import RenderCache

pc = ProtoClass

class ExportManager:
    def __init__(self, root_registry, merge_manager):
        self.root_registry = root_registry
        self.merge_manager = merge_manager

    def paginate(self, layout, copies: int = 1):
        pages = []
        registry = layout.registry
        _ctx = RenderContext(
            route=RenderRoute.COMPOSITE,
            tab_mode=TabMode.LAYOUT,
            mode=RenderMode.EXPORT,
            dpi=300,
            unit="pt",
        )
        _ctx.cache = RenderCache(_ctx)
        settings = AppSettings(_ctx)
        _registry = ProtoRegistry(root=self.root_registry, 
            settings=settings, 
            parent=self.root_registry
        )
        export_layout = _registry.clone(layout)

        slots_per_page = len(layout.items)
        total_rows = self.merge_manager.count_all_rows(layout)  # 0 if no CSV bound
        has_csv = total_rows > 0

        if has_csv:
            # copies = repeat the whole run copies times
            total_slots_needed = copies * total_rows
            page_count = max(1, math.ceil(total_slots_needed / slots_per_page))
        else:
            # no CSV → clone exactly `copies` pages
            page_count = max(1, copies)

        for _ in range(page_count):
            page = _registry.clone(export_layout)
            self.no_autorender(page, True)
            # Setting page.ctx sets context for everything on the page
            page.ctx = _ctx
            if has_csv:
                self.merge_manager.set_csv_content_for_next_page(page)
            pages.append(page)

        return pages

    def no_autorender(self, page, flag: bool):
        page.setFlag(QGraphicsItem.ItemHasNoContents, flag)
        for slot in page.items:
            slot.setFlag(QGraphicsItem.ItemHasNoContents, flag)
            comp = slot.content
            if comp:
                comp.setFlag(QGraphicsItem.ItemHasNoContents, flag)
                for item in comp.items:
                    item.setFlag(QGraphicsItem.ItemHasNoContents, flag)


    def export_pdf(self, layout, pdf_path):
        # context is set in pages
        pages = self.paginate(layout)

        # Page geometry in points
        page_size_pt: QSizeF = layout.geometry.pt.size
        page_rect_pt: QRectF = layout.geometry.pt.rect

        writer = QPdfWriter(pdf_path)
        writer.setPageSize(QPageSize(page_size_pt, QPageSize.Point))
        writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Point)
        writer.setResolution(72)  # 1pt = 1/72 in

        painter = QPainter(writer)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        for i, page in enumerate(pages):
            # 1) Draw this page
            self.normalize_positions(page, page.ctx)
            painter.save()
            # ensure painter origin is top-left of page in points
            ProtoPaint.render_page(page, page.ctx, painter)
            painter.restore()

            if i < len(pages) - 1:
                writer.newPage()

        painter.end()

    def normalize_positions(self, page, ctx):
        # Layout page is at (0,0) — ensure that:
        page.setPos(0, 0)

        # Slots
        for slot in page.items:
            gs = slot.geometry.to(ctx.unit, dpi=ctx.dpi)  # not slot._geometry
            slot.setPos(float(gs.pos.x()), float(gs.pos.y()))
            # content placement policy: put component at (0,0) inside slot
            comp = slot.content
            comp.setPos(0, 0)
            # Elements
            for el in comp.items:
                ge = el.geometry.to(ctx.unit, dpi=ctx.dpi)
                el.setPos(float(ge.pos.x()), float(ge.pos.y()))

def traverse_export(p: QPainter, item, ctx: RenderContext):
    # 1) Translate to this item's scene position
    p.save()
    pos = item.scenePos()  # already in points for layout/items if you set them correctly
    p.translate(pos.x(), pos.y())

    # 2) Optional: apply local transform if your items use it (rotate/scale)
    if hasattr(item, "transform") and isinstance(item.transform(), QTransform):
        p.setWorldTransform(p.worldTransform() * item.transform(), combine=False)

    # 3) Paint the item itself (LOCAL coords: (0,0) to geometry.size)
    if item in paintable:
        item.render(p, ctx)

    # 4) Recurse to children in z-order if needed
    if hasattr(item, "items"):
        for child in item.items:   # component -> elements
            traverse_export(p, child, ctx)
    if hasattr(item, "content") and pc.isproto(item, paintable):
        traverse_export(p, item.content, ctx)

    p.restore()


