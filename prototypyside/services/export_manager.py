# export_manager.py
from math import ceil
from pathlib import Path
from itertools import zip_longest

from PySide6.QtCore import QSizeF
from PySide6.QtGui  import QPainter, QColor, QPdfWriter, QImage, QPageSize, QPageLayout
from PySide6.QtWidgets import QGraphicsScene, QStyleOptionGraphicsItem

from prototypyside.models.layout_slot import LayoutSlot
from prototypyside.models.component_template import ComponentTemplate
from prototypyside.models.text_element import TextElement
from prototypyside.models.vector_element import VectorElement
from prototypyside.utils.units.unit_str import UnitStr #, unitstr_from_raw
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
# from prototypyside.services.pagination.page_manager import PageManager
from PySide6.QtCore import Qt, QSizeF, QRectF, QMarginsF, QPointF
from prototypyside.services.proto_class import ProtoClass
from prototypyside.utils.render_context import RenderContext, RenderMode, RenderRoute, TabMode
from prototypyside.services.render_cache import RenderCache

pc = ProtoClass

class ExportManager:
    def __init__(self, settings, merge_manager):
        print(f'Setting received from {settings}')
        self.settings = settings
        self.print_dpi = settings.dpi
        self.merge_manager = merge_manager

    def paginate(self, layout, copies: int = 1):
        pages = []
        registry = layout.registry

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

        page_ctx = RenderContext(
            route=RenderRoute.COMPOSITE,
            tab_mode=TabMode.LAYOUT,
            mode=RenderMode.EXPORT,
            dpi=72,
            unit="pt",
        )
        page_ctx.cache = RenderCache(page_ctx)

        for _ in range(page_count):
            page = registry.clone(layout)
            page.display_mode = False
            page.unit = "pt"
            page.ctx = page_ctx
            if has_csv:
                self.merge_manager.set_csv_content_for_next_page(page)
            pages.append(page)

        return pages

    # def paginate(self, layout, copies: int = 1):
    #     """
    #     Create cloned pages and populate them with CSV rows.
    #     If there is NO CSV bound to any slot, clone exactly `copies` pages.
    #     Otherwise, compute page_count from total rows and slots_per_page.
    #     """
    #     # registry = self.registry  # assuming this exists on the manager
    #     pages = []
    #     registry = layout.registry
    #     # Build a RenderContext configured for export of a layout-composite route
        
    #     # how many rows across all slot components?
    #     total_rows = self.merge_manager.count_all_rows(layout)

    #     slots_per_page = len(layout.items)
    #     slot_count = max(copies*total_rows, slots_per_page*copies)
    #     page_count = ceil(slot_count / slots_per_page)

    #     for _ in range(page_count):
    #         page = registry.clone(layout)
    #         page.display_mode = False
    #         # page.unit = "pt"
    #         page.ctx = RenderContext(
    #             route=RenderRoute.COMPOSITE,
    #             tab_mode=TabMode.LAYOUT,
    #             mode=RenderMode.EXPORT,
    #         )
    #         self.merge_manager.set_csv_content_for_next_page(page)
    #         pages.append(page)

    #     return pages

    def export_pdf(self, layout, pdf_path):
        pages = self.paginate(layout)

        # Prepare a consistent export context (points @ 72dpi)
        export_ctx = RenderContext(
            route=RenderRoute.COMPOSITE,
            tab_mode=TabMode.LAYOUT,
            mode=RenderMode.EXPORT,
            dpi=72,
            unit="pt"
        )
        export_ctx.cache = RenderCache(export_ctx)

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
            # 1) Normalize units for all nested objects ONCE
            page.unit = "pt"
            page.ctx = export_ctx
            self._normalize_positions_to_points(page, export_ctx)  # sets setPos() from geometry for layout/slots/components/elements

            # 2) Draw this page
            painter.save()
            # ensure painter origin is top-left of page in points
            # (QPdfWriter already uses points; no further scaling needed)
            traverse_export(painter, page, export_ctx)
            painter.restore()

            if i < len(pages) - 1:
                writer.newPage()

        painter.end()

    def _normalize_positions_to_points(self, page, ctx):
        # Layout page is at (0,0) — ensure that:
        page.setPos(0, 0)

        # Slots
        for slot in page.items:
            gs = slot.geometry.to(ctx.unit, dpi=ctx.dpi)
            slot.setPos(float(gs.rect.x()), float(gs.rect.y()))
            # content placement policy: put component at (0,0) inside slot
            if slot.content:
                slot.content.setPos(0, 0)
                slot.content.ctx = ctx
                # Elements
                for el in getattr(slot.content, "items", []):
                    ge = el.geometry.to(ctx.unit, dpi=ctx.dpi)
                    el.setPos(float(ge.rect.x()), float(ge.rect.y()))
                    el.ctx = ctx


    # def export_pdf(self, layout, pdf_path):
    #     pages = self.paginate(layout)

    #     # Page geometry in POINTS
    #     page_size_pt: QSizeF = layout.geometry.pt.size
    #     page_rect_pt: QRectF = layout.geometry.pt.rect

    #     # QPdfWriter setup
    #     writer = QPdfWriter(pdf_path)
    #     writer.setPageSize(QPageSize(page_size_pt, QPageSize.Point))
    #     writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Point)
    #     writer.setResolution(72)
        
    #     painter = QPainter(writer)
    #     painter.setRenderHint(QPainter.Antialiasing, True)
    #     painter.setRenderHint(QPainter.TextAntialiasing, True)

    #     scene = QGraphicsScene()
    #     scene.setSceneRect(page_rect_pt)  # scene units = points
        
    #     for i, page in enumerate(pages):
    #         page.unit = "pt"
    #         scene.clear()
            
    #         # Set export context for all items
    #         export_context = RenderContext(
    #             route=RenderRoute.COMPOSITE,
    #             tab_mode=TabMode.LAYOUT,
    #             mode=RenderMode.EXPORT,
    #             dpi=self.print_dpi
    #         )
            
    #         page.ctx = export_context
    #         for slot in page.items:
    #             if slot.content:
    #                 slot.content.ctx = export_context
    #                 # Ensure elements know they're in export mode
    #                 for item in getattr(slot.content, "items", []):
    #                     item.ctx = export_context
    #                     item.update()
            
    #         scene.addItem(page)  
    #         page.setGrid()
    #         page.updateGrid()
            
    #         if i > 0:
    #             writer.newPage()

    #         target = page_rect_pt
    #         source = scene.sceneRect()
    #         scene.render(painter, target, source)

    #     painter.end()

def traverse_export(p: QPainter, item, ctx: RenderContext):
    # 1) Translate to this item's scene position
    p.save()
    pos = item.pos()  # already in points for layout/items if you set them correctly
    p.translate(pos.x(), pos.y())

    # 2) Optional: apply local transform if your items use it (rotate/scale)
    if hasattr(item, "transform") and isinstance(item.transform(), QTransform):
        p.setWorldTransform(p.worldTransform() * item.transform(), combine=False)

    # 3) Paint the item itself (LOCAL coords: (0,0) to geometry.size)
    item.export_paint(p, ctx)

    # 4) Recurse to children in z-order if needed
    for child in getattr(item, "items", []):   # component -> elements
        traverse_export(p, child, ctx)
    for slot in getattr(item, "slots", []):    # layout -> slots
        traverse_export(p, slot, ctx)
    if getattr(item, "content", None) is not None:   # slot -> component
        traverse_export(p, item.content, ctx)

    p.restore()



        # def export_pdf(self, layout, pdf_path):
        #     pages = self.paginate(layout)

        #     # Page geometry in POINTS
        #     page_size_pt: QSizeF = layout.geometry.pt.size
        #     page_rect_pt: QRectF = layout.geometry.pt.rect

        #     # QPdfWriter setup
        #     writer = QPdfWriter(pdf_path)
        #     writer.setPageSize(QPageSize(page_size_pt, QPageSize.Point))
        #     # margins in points (QPageLayout.Point)
        #     writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Point)
        #     # optional: DPI for rasterized bits (images/effects); vectors/text stay vector
        #     # optional metadata
        #     # writer.setTitle(layout.name or "Layout")
        #     # writer.setCreator("ProtoTypeSide")
        #     writer.setResolution(72)
        #     painter = QPainter(writer)
        #     painter.setRenderHint(QPainter.Antialiasing, True)
        #     painter.setRenderHint(QPainter.TextAntialiasing, True)

        #     scene = QGraphicsScene()
        #     scene.setSceneRect(page_rect_pt)  # scene units = points
        #     scene.clear()
        #     for i, page in enumerate(pages):
        #         page.unit = "pt"
        #         scene.clear()
        #         scene.addItem(page)  
        #         page.setGrid()
        #         page.updateGrid()
        #         if i > 0:
        #             writer.newPage()

        #         # With QPdfWriter there’s no pageRect(); just use your page rect in points.
        #         target = page_rect_pt
        #         source = scene.sceneRect()
        #         scene.render(painter, target, source)

        #     painter.end()


    # def export_component_to_png(self, template, output_dir):
    #     """
    #     PNG export with per-row overrides and bleed-aware geometry.
    #     Depends on ComponentTemplate.include_bleed to set _bleed_rect.
    #     """
    #     # use canonical dpi for everything. DPI for comp_inst is set by LayoutSlot.dpi property
    #     dpi = self.settings.dpi
    #     # --- helpers --------------------------------------------------------------
    #     def _truthy(v) -> bool:
    #         if isinstance(v, bool): return v
    #         s = str(v).strip().lower()
    #         return s in ("1", "true", "yes", "y", "on")

    #     def _maybe_qcolor(v):
    #         if isinstance(v, QColor): return v
    #         s = str(v).strip()
    #         if s.startswith("#"):
    #             c = QColor(s);  return c if c.isValid() else None
    #         parts = [p.strip() for p in s.split(",")]
    #         try:
    #             if len(parts) == 3:
    #                 r,g,b = map(int, parts); return QColor(r,g,b)
    #             if len(parts) == 4:
    #                 r,g,b,a = map(int, parts); return QColor(r,g,b,a)
    #         except Exception:
    #             pass
    #         c = QColor(s); return c if c.isValid() else None

    #     def _maybe_unitstr(v):
    #         if pc.isproto(v, pc.US): return v
    #         return UnitStr(str(v), "px", )

    #     def _valid_image_path(p):
    #         try:
    #             path = Path(str(p)).expanduser()
    #             return path.is_file()
    #         except Exception:
    #             return False

    #     # --- setup ---------------------------------------------------------------
    #     output_dir = Path(output_dir)
    #     output_dir.mkdir(parents=True, exist_ok=True)

    #     if template.csv_path:
    #         csv_data = self.merge_manager.load_csv(template.csv_path, template)
    #         rows = csv_data.rows
    #         validation = csv_data.validate_headers(template)
    #         missing = [k for k, v in validation.items() if v == "missing"]
    #         if missing:
    #             print(f"[EXPORT ERROR] Missing CSV headers for: {', '.join(missing)}")
    #             raise ValueError(f"Export aborted due to missing headers: {', '.join(missing)}")
    #     else:
    #         rows = [{}]

    #     # background aliases
    #     bg_aliases = ("@bg", "@background", "@background_image", "@bg_image")

    #     # supported overrides (strip '@' → attr)
    #     override_map = {
    #         # exclude "@background_image": "background_image" as it's handled seperately
    #         "@include_bleed":    "include_bleed",
    #         "@bg_color":         "bg_color",
    #         "@border_width":     "border_width",
    #         "@border_color":     "border_color",
    #     }

    #     for i, row in enumerate(rows, start=1):
    #         if not pc.isproto(template, pc.CT):
    #             raise TypeError("Export must be a ComponentTemplate.")
    #         comp_inst = self.registry.clone(template)

    #         # --- (A) per-row template overrides (before any painting) -------------
    #         # A1) background image via aliases (first valid path wins)
    #         bg_val = None
    #         for key in bg_aliases:
    #             v = row.get(key, None)
    #             if v and _valid_image_path(v):
    #                 setattr(comp_inst, "background_image", v)
    #                 break

    #         # A2) explicit overrides
    #         for at_key, attr in override_map.items():
    #             if at_key not in row:
    #                 continue
    #             val = row[at_key]

    #             if attr == "include_bleed":
    #                 setattr(comp_inst, attr, _truthy(val))

    #             elif attr in ("bg_color", "border_color"):
    #                 qc = _maybe_qcolor(val)
    #                 if qc is not None:
    #                     setattr(comp_inst, attr, qc)

    #             # elif attr == "border_width":
    #             #     setattr(comp_inst, "border_width", unitstr_from_raw(attr, dpi=dpi))

    #         # --- (B) bind CSV-driven element content ------------------------------
    #         for el in getattr(comp_inst, "items", []):
    #             if getattr(el, "name", "").startswith("@"):
    #                 v = row.get(el.name, None)
    #                 # if there isn't row data, let slot handle item.content if present.

    #         # --- (C) render via LayoutSlot; geometry depends on bleed ------------
    #         # choose geometry
    #         slot_geometry = comp_inst.geometry if not comp_inst.include_bleed else comp_inst.bleed_rect

    #         slot = LayoutSlot(
    #             pid=('ls'),
    #             geometry=slot_geometry,
    #             registry=self.registry
    #         )

    #         scene = QGraphicsScene()
    #         scene.addItem(slot)
    #         slot.content = comp_inst
    #         comp_inst.set_print_mode = True        # turn off element outlines
    #         slot.set_print_mode = True             # belt-and-suspenders + invalidate cache
    #         slot.dpi = dpi

    #         image = slot.image
    #         filename = f"{template.name}_{i}{'_bleed' if comp_inst.include_bleed else ''}.png"
    #         image.save(str(output_dir / filename), "PNG")
    #         print(f"Exported component to {filename}")


    # # def export_component_to_png(self, template, output_dir, dpi=300):
    # #     output_dir = Path(output_dir)
    # #     output_dir.mkdir(parents=True, exist_ok=True)

    # #     if template.csv_path:
    # #         csv_data = self.merge_manager.load_csv(template.csv_path, template)
    # #         rows = csv_data.rows
    # #     else:
    # #         rows = [{}]  # single empty row for static content

    # #     validation = csv_data.validate_headers(template) if template.csv_path else {}
    # #     missing = [k for k, v in validation.items() if v == "missing"]
    # #     if missing:
    # #         print(f"[EXPORT ERROR] Missing CSV headers for: {', '.join(missing)}")
    # #         raise ValueError(f"Export aborted due to missing headers: {', '.join(missing)}")

    # #     for i, row in enumerate(rows, start=1):
    # #         comp_inst = self.registry.clone(template)
    # #         # Apply CSV data to bound elements
    # #         for el in comp_inst.items:
    # #             if el.name.startswith("@"):  # CSV-bound element
    # #                 val = row.get(el.name, "")
    # #                 el.content = val
    # #         # We're not going to register the slot.
    # #         slot = LayoutSlot(
    # #                 pid=('ls'),
    # #                 geometry=template.geometry, 
    # #                 registry=self.registry)

    # #         scene = QGraphicsScene()
    # #         scene.addItem(slot)
            
    # #         slot.content = comp_inst
    # #         slot.dpi = 300
    # #         image = slot.image
    # #         filename = f"{template.name}_{i}.png"
    # #         image.save(str(output_dir / filename), "PNG")
    # #         print(f"Exported component to {filename}")

    # def export_to_pdf(self, layout, output_path, scale_to_300=False):
    #     pages = self.paginate(layout)
    #     self.dpi = self.settings.print_dpi # Keep this one
    #     page_size_pt = layout.geometry.to("pt", dpi=self.dpi).size
    #     page_size_px = layout.geometry.to("px", dpi=self.dpi).size
    #     print(f"page size in points is {page_size_pt}\npage size in pixels is {page_size_px}")

    #     # Use point-based size for proper PDF coordinate alignment
    #     page_size = QPageSize(page_size_pt, QPageSize.Point, name="Custom")
    #     page_layout = QPageLayout(page_size, QPageLayout.Portrait, QMarginsF(0, 0, 0, 0))

    #     writer = QPdfWriter(str(output_path))
    #     # Only hacks use setResolution to scale to 300. We keep our units like our paper, px agnostic.
    #     writer.setResolution(72)  # UnitStr sets it's own resolution. Leave writer as base resolution 72.
    #     writer.setPageLayout(page_layout)

    #     painter = QPainter(writer)
    #     print(f"[EXPORTMANAGER] Settings dpi is now being changed from {self.settings.print_dpi} to {self.dpi}")
    #     # REMOVED: self.dpi = self.settings.print_dpi # This line was redundant
    #     print(f"[EXPORTMANAGER] Layout dpi is now set to {layout.dpi}")
    #     for i, page in enumerate(pages):
    #         if i > 0:
    #             writer.newPage()
    #         page.dpi = self.settings.print_dpi # This should cause cache invalidation and force redraw with new dpi
    #         page.updateGrid()
    #         img = getattr(page, "image", None)
    #         # Optional: Smooth scaling
    #         if scale_to_300:
    #             # Since we've rendered to raster, this is in pixels not ustr and ustrgeom
    #             scale_factor = 300 / self.settings.print_dpi
    #             new_width_px = int(img.width() * scale_factor)
    #             new_height_px = int(img.height() * scale_factor)
    #             img = img.scaled(
    #                 new_width_px, new_height_px,
    #                 Qt.KeepAspectRatio, # Use KeepAspectRatio unless you explicitly want to distort
    #                 Qt.SmoothTransformation
    #             )

    #         if img and not img.isNull():
    #             target_rect = QRectF(0, 0, page_size_pt.width(), page_size_pt.height())
    #             painter.drawImage(target_rect, img)

    #     painter.end()

    # def export_with_vector_text_to_pdf(self, layout, output_path, scale_to_300=True):
    #     """
    #     Export pages while drawing text as vector graphics.
    #     Render raster at 600 DPI for quality, scale to 300 DPI for output balance
    #     """
    #     pages = self.paginate(layout)
    #     self.dpi = self.settings.print_dpi

    #     page_size_pt = layout.geometry.to("pt", dpi=self.dpi).size
    #     page_size = QPageSize(page_size_pt, QPageSize.Point, name="Custom")
    #     page_layout = QPageLayout(page_size, QPageLayout.Portrait, QMarginsF(0, 0, 0, 0))

    #     writer = QPdfWriter(str(output_path))
    #     writer.setResolution(72)
    #     writer.setPageLayout(page_layout)

    #     painter = QPainter(writer)

    #     scale_pt_per_px = 72 / self.settings.print_dpi
    #     option = QStyleOptionGraphicsItem()

    #     for i, page in enumerate(pages):
    #         if i > 0:
    #             writer.newPage()

    #         page.dpi = self.settings.print_dpi
    #         for slot in page.items:
    #             slot.render_text = False
    #             slot.render_vector = False

    #         page.invalidate_cache()
    #         img = page.image

    #         if scale_to_300:
    #             scale_factor = 300 / self.settings.print_dpi
    #             new_width_px = int(img.width() * scale_factor)
    #             new_height_px = int(img.height() * scale_factor)
    #             img = img.scaled(new_width_px, new_height_px, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    #         target_rect = QRectF(0, 0, page_size_pt.width(), page_size_pt.height())
    #         painter.drawImage(target_rect, img)

    #         for slot in page.items:
    #             if not slot.content:
    #                 continue
    #             slot_pos_px = slot.geometry.to("px", dpi=self.settings.print_dpi).pos

    #             painter.save()

    #             # Scale painter so 1 unit = 1 px at 300 DPI = 72 pts
    #             scale = self.settings.print_dpi / 72.0  # e.g. 4.166
    #             slot_pos_pt = QPointF(slot_pos_px.x() / scale, slot_pos_px.y() / scale)
    #             painter.translate(slot_pos_pt)
    #             painter.scale(1 / scale, 1 / scale)

    #             for item in slot.content.items:
    #                 if pc.isproto(item, (pc.TE, pc.VE)):
    #                     painter.save()
    #                     painter.setTransform(item.sceneTransform(), True)  # compose with current page/slot transform
    #                     painter.setClipRect(template.boundingRect())
    #                     item.paint(painter, option, widget=None)
    #                     painter.restore()
    #             painter.restore()

    #     painter.end()
