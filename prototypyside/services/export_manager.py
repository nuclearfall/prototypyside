from math import ceil
from PySide6.QtCore import QSizeF
from PySide6.QtGui  import QPainter, QPdfWriter, QImage, QPageSize, QPageLayout
from PySide6.QtWidgets import QGraphicsScene
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry

from PySide6.QtCore import QSizeF, QRectF, QMarginsF
from pathlib import Path
from itertools import zip_longest

class ExportManager:
    # Here we're setting dpi to 600 and downscaling to 300 for print.
    def __init__(self, registry, merge_manager, unit="px", dpi=600):
        self.registry = registry
        self.merge_manager = merge_manager
        self.dpi           = dpi
        self.unit          = unit
        self.page_size_in  = QSizeF(8.5, 11.0)

    def paginate(self, layout, copies=1):
        registry = self.registry
        print(f"Export registry is set to {registry}")
        pages = []
        tpid = layout.content
        template = registry.global_get(tpid)
        csv_path = template.csv_path
        csv_data = self.merge_manager.load_csv(csv_path, template)
        rows = csv_data.rows
        slots_n = len(layout.slots)
        page_count = ceil(max(len(rows), 1) / slots_n) * copies

        print(f"Prior to export:\n* Rows: {csv_data.count}\n* Pages: {page_count}")
        pages = [self.registry.clone(layout) for i in range(page_count)]

        # We have merge data so we need to validate headers one more time before exporting
        # if rows:
        #     validation = csv_data.validate_headers(template)
        #     missing = [k for k, v in validation.items() if v == "missing"]
        #     if missing:
        #         print(f"[EXPORT ERROR] Missing CSV headers for: {', '.join(missing)}")
        #         raise ValueError(f"Export aborted due to missing headers: {', '.join(missing)}")
        #     for p in range(page_count):
        #         rows_for_page = rows[p*slots_n : (p+1)*slots_n] if rows else [None] * slots_n
        #         page = registry.clone(layout)
        #         page_slots = page.slots
        #         for slot, row in zip_longest(page_slots, rows_for_page):
        #             comp_inst = slot.content
        #             if not comp_inst:
        #                 print("Slot has no content")
        #                 pass
        #             for el in comp_inst.items:
        #                 if el.name.startswith("@"):
        #                     el.content = row.get(el.name, "") if row else ""
        #             slot.content = comp_inst
        #         pages.append(page)
        # # template is static export without merge data
        # else: 
        #     for p in range(page_count):
        #         page = registry.clone(layout)
        #         pages.append(page)
        #     return pages

    def export_to_pdf(self, layout, output_path):
        print("We've made it to export...")
        pages = self.paginate(layout)
        print("We've made it through pagination")

        # 1. Get logical point-based page size
        page_size_pt: QSizeF = layout.geometry.to("pt", dpi=self.dpi).size

        # 2. Set up writer
        writer = QPdfWriter(str(output_path))
        writer.setResolution(300) # here is where we downscale from 600

        # 3. QPdfWriter does NOT accept QPageSize directly → use setPageSizeMM or setPageSize()
        # writer.setPageSizeMM(layout.geometry.to("mm", dpi=self.dpi).size)  # This line may raise AttributeError, so instead:

        # Use workaround by setting paper size in points manually:
        # Create a QPageSize in points
        custom_page_size = QPageSize(page_size_pt, QPageSize.Point, name="Custom")

        # Create a PageLayout with default margins (0) and Portrait orientation
        page_layout = QPageLayout(custom_page_size, QPageLayout.Portrait, QMarginsF(0, 0, 0, 0))


        # 4. Setup painter
        painter = QPainter(writer)

        for i, page in enumerate(pages):
            if i > 0:
                writer.newPage()

            if page.image and not page.image.isNull():
                painter.drawImage(layout.geometry.pt.rect, page.image)

        painter.end()

