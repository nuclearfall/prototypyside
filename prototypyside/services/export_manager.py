from math import ceil
from PySide6.QtCore import QSizeF
from PySide6.QtGui  import QPainter, QPdfWriter, QImage, QPageSize, QPageLayout
from PySide6.QtWidgets import QGraphicsScene, QStyleOptionGraphicsItem

from prototypyside.models.layout_slot import LayoutSlot
from prototypyside.models.text_element import TextElement
from prototypyside.models.vector_element import VectorElement
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.proto_helpers import resolve_pid
from PySide6.QtCore import Qt, QSizeF, QRectF, QMarginsF, QPointF
from pathlib import Path
from itertools import zip_longest

class ExportManager:
    # Here we're setting dpi to 600 and downscaling to 300 for print.
    def __init__(self, settings, registry, merge_manager, dpi=300):
        print(f'Setting received from {settings}')
        # self.original_dpi = settings.dpi 
        self.settings = settings
        self.settings.print_dpi = 300
        self.registry = registry
        self.merge_manager = merge_manager


    def paginate(self, layout, copies=1):
        registry = self.registry
        print(f"Export registry is set to {registry}")
        pages = []
        tpid = layout.content
        template = registry.global_get(tpid)

        layout.updateGrid()

        slots_n = len(layout.slots)
        page_count = copies
        rows = []

        if template.csv_path:
            csv_data = self.merge_manager.load_csv(template.csv_path, template)
            rows = csv_data.rows
            print(f'There are {csv_data.count} rows: {rows}')
            page_count = ceil(max(len(rows), 1) / slots_n) * copies

        for _ in range(page_count):
            page = registry.clone(layout)
            pages.append(page)

        all_slots = [slot for page in pages for slot in page.slots]

        if rows:
            validation = csv_data.validate_headers(template)
            missing = [k for k, v in validation.items() if v == "missing"]
            if missing:
                print(f"[EXPORT ERROR] Missing CSV headers for: {', '.join(missing)}")
                raise ValueError(f"Export aborted due to missing headers: {', '.join(missing)}")

            for row, slot in zip_longest(rows, all_slots):
                if not row or not slot:
                    continue
                comp_inst = slot.content
                print(f"Slot Content is {slot.content} and row is {row}")
    
                if not comp_inst:
                    continue
                print(f"{comp_inst.pid} elements: {[el.name for el in comp_inst.items]}")

                # export_manager.py
                for el in comp_inst.items:
                    name = getattr(el, "name", "") or ""
                    if not name.startswith("@"):
                        continue

                    # Try exact header first (e.g., '@top_text'), then normalized ('top_text')
                    v = row.get(name)
                    if v in (None, ""):
                        v = row.get(name.lstrip("@"))
                    if v is None:
                        v = ""

                    # Apply to element
                    # (adjust to your element API)
                    if hasattr(el, "content"):        # TextElement/VectorElement in your codebase
                        el.content = v

                slot.invalidate_cache()

        return pages

    def export_component_to_png(self, template, output_dir, dpi=300):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if template.csv_path:
            csv_data = self.merge_manager.load_csv(template.csv_path, template)
            rows = csv_data.rows
        else:
            rows = [{}]  # single empty row for static content

        validation = csv_data.validate_headers(template) if template.csv_path else {}
        missing = [k for k, v in validation.items() if v == "missing"]
        if missing:
            print(f"[EXPORT ERROR] Missing CSV headers for: {', '.join(missing)}")
            raise ValueError(f"Export aborted due to missing headers: {', '.join(missing)}")

        for i, row in enumerate(rows, start=1):
            comp_inst = self.registry.clone(template)
            # Apply CSV data to bound elements
            for el in comp_inst.items:
                if el.name.startswith("@"):  # CSV-bound element
                    val = row.get(el.name, "")
                    el.content = val
            # We're not going to register the slot.
            slot = LayoutSlot(
                    pid=resolve_pid('ls'),
                    geometry=template.geometry, 
                    registry=self.registry)

            scene = QGraphicsScene()
            scene.addItem(slot)
            
            slot.content = comp_inst
            slot.dpi = 300
            image = slot.image
            filename = f"{template.name}_{i}.png"
            image.save(str(output_dir / filename), "PNG")
            print(f"Exported component to {filename}")

    def export_to_pdf(self, layout, output_path, scale_to_300=False):
        pages = self.paginate(layout)
        self.dpi = self.settings.print_dpi # Keep this one
        page_size_pt = layout.geometry.to("pt", dpi=self.dpi).size
        page_size_px = layout.geometry.to("px", dpi=self.dpi).size
        print(f"page size in points is {page_size_pt}\npage size in pixels is {page_size_px}")

        # Use point-based size for proper PDF coordinate alignment
        page_size = QPageSize(page_size_pt, QPageSize.Point, name="Custom")
        page_layout = QPageLayout(page_size, QPageLayout.Portrait, QMarginsF(0, 0, 0, 0))

        writer = QPdfWriter(str(output_path))
        # Only hacks use setResolution to scale to 300. We keep our units like our paper, px agnostic.
        writer.setResolution(72)  # UnitStr sets it's own resolution. Leave writer as base resolution 72.
        writer.setPageLayout(page_layout)

        painter = QPainter(writer)
        print(f"[EXPORTMANAGER] Settings dpi is now being changed from {self.settings.print_dpi} to {self.dpi}")
        # REMOVED: self.dpi = self.settings.print_dpi # This line was redundant
        print(f"[EXPORTMANAGER] Layout dpi is now set to {layout.dpi}")
        for i, page in enumerate(pages):
            if i > 0:
                writer.newPage()
            page.dpi = self.settings.print_dpi # This should cause cache invalidation and force redraw with new dpi
            page.updateGrid()
            img = getattr(page, "image", None)
            # Optional: Smooth scaling
            if scale_to_300:
                # Since we've rendered to raster, this is in pixels not ustr and ustrgeom
                scale_factor = 300 / self.settings.print_dpi
                new_width_px = int(img.width() * scale_factor)
                new_height_px = int(img.height() * scale_factor)
                img = img.scaled(
                    new_width_px, new_height_px,
                    Qt.KeepAspectRatio, # Use KeepAspectRatio unless you explicitly want to distort
                    Qt.SmoothTransformation
                )

            if img and not img.isNull():
                target_rect = QRectF(0, 0, page_size_pt.width(), page_size_pt.height())
                painter.drawImage(target_rect, img)

        painter.end()

    def export_with_vector_text_to_pdf(self, layout, output_path, scale_to_300=True):
        """
        Export pages while drawing text as vector graphics.
        Render raster at 600 DPI for quality, scale to 300 DPI for output balance
        """
        pages = self.paginate(layout)
        self.dpi = self.settings.print_dpi

        page_size_pt = layout.geometry.to("pt", dpi=self.dpi).size
        page_size = QPageSize(page_size_pt, QPageSize.Point, name="Custom")
        page_layout = QPageLayout(page_size, QPageLayout.Portrait, QMarginsF(0, 0, 0, 0))

        writer = QPdfWriter(str(output_path))
        writer.setResolution(72)
        writer.setPageLayout(page_layout)

        painter = QPainter(writer)

        scale_pt_per_px = 72 / self.settings.print_dpi
        option = QStyleOptionGraphicsItem()

        for i, page in enumerate(pages):
            if i > 0:
                writer.newPage()

            page.dpi = self.settings.print_dpi
            for slot in page.slots:
                slot.render_text = False
                slot.render_vector = False

            page.invalidate_cache()
            img = page.image

            if scale_to_300:
                scale_factor = 300 / self.settings.print_dpi
                new_width_px = int(img.width() * scale_factor)
                new_height_px = int(img.height() * scale_factor)
                img = img.scaled(new_width_px, new_height_px, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            target_rect = QRectF(0, 0, page_size_pt.width(), page_size_pt.height())
            painter.drawImage(target_rect, img)

            for slot in page.slots:
                if not slot.content:
                    continue
                slot_pos_px = slot.geometry.to("px", dpi=self.settings.print_dpi).pos

                painter.save()

                # Scale painter so 1 unit = 1 px at 300 DPI = 72 pts
                scale = self.settings.print_dpi / 72.0  # e.g. 4.166
                slot_pos_pt = QPointF(slot_pos_px.x() / scale, slot_pos_px.y() / scale)
                painter.translate(slot_pos_pt)
                painter.scale(1 / scale, 1 / scale)

                for item in slot.content.items:
                    if isinstance(item, (TextElement, VectorElement)):
                        painter.save()
                        painter.setTransform(item.sceneTransform(), True)  # compose with current page/slot transform
                        painter.setClipRect(item.boundingRect())
                        item.paint(painter, option, widget=None)
                        painter.restore()
                painter.restore()

        painter.end()


