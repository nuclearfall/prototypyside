from math import ceil
from PySide6.QtCore import QSizeF
from PySide6.QtGui  import QPainter, QPdfWriter, QImage
from PySide6.QtWidgets import QGraphicsScene
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry

from PySide6.QtCore import QSizeF, QRectF, QMarginsF
from pathlib import Path
from itertools import zip_longest

class ExportManager:
    def __init__(self, merge_manager, unit="px", dpi=300):
        self.merge_manager = merge_manager
        self.dpi           = dpi
        self.unit          = unit
        self.page_size_in  = QSizeF(8.5, 11.0)

    def paginate(self, layout):
        pages = []
        tpid = layout.content
        registry = layout.registry
        template = registry.root.get(tpid)
        csv_path = template.csv_path
        data = self.merge_manager.load_csv(csv_path, template)
        rows = csv_data.rows
        slots_n = len(layout.slots)
        page_count = ceil(max(len(rows), 1) / slots_n)

        # We have merge data so we need to validate headers one more time before exporting
        if rows:
            validation = csv_data.validate_headers(template)
            missing = [k for k, v in validation.items() if v == "missing"]
            if missing:
                print(f"[EXPORT ERROR] Missing CSV headers for: {', '.join(missing)}")
                raise ValueError(f"Export aborted due to missing headers: {', '.join(missing)}")
            for p in range(page_count):
                rows_for_page = rows[p*slots_n : (p+1)*slots_n] if rows else [None] * slots_n
                page = registry.clone(layout)
                page_slots = page.slots
                for slot, row in zip_longest(page_slots, rows_for_page):
                    comp_inst = registry.clone(template)
                    for el in comp_inst.items:
                        if el.name.startswith("@"):
                            el.content = row.get(el.name, "") if row else ""
                            slot.content = comp_inst
                pages.append(page)
        # template is static export without merge data
        else: 
            for p in range(page_count):
                page = registry.clone(layout)
                pages.append(page)
            return pages

    # def paginate(self, layout):
    #     pages = []
    #     tpid = layout.content
    #     template = registry.get(tpid)
    #     csv_data = self.merge_manager.ensure_loaded(tpid)
    #     if not csv_data:
    #         # This is okay. It just means that we have a static template
    #         print(f"[ERROR] No CSV data found for tpid {tpid}")
    #         return []
    #     results = csv_data.validate_headers(template)

    #     missing = [k for k, v in validation.items() if v == "missing"]
    #     if missing:
    #         warning_msg = f"Missing CSV headers for: {', '.join(missing)}"
    #         if self.warning_handler:
    #             self.warning_handler(warning_msg)
    #         else:
    #             print(f"[EXPORT WARNING] {warning_msg}")
    #     rows = csv_data.rows
    #     flat_slots = [col for row in layout.items for col in row]
    #     slots_n = len(flat_slots)
    #     page_count = ceil(len(rows) / slots_n)

    #     for p in range(page_count):
    #         rows_for_page = rows[p*slots_n : (p+1)*slots_n]
    #         page = registry.clone(layout)
    #         page_slots = [col for row in page.items for col in row]
    #         for slot, row in zip_longest(page_slots, rows_for_page):
    #             if row:
    #                 comp_inst = registry.clone(template)
    #                 for el in comp_inst.items:
    #                     if el.name.startswith("@"):
    #                         el.content = row.get(el.name, "")
    #                 slot.content = comp_inst
    #         pages.append(page)
    #     return pages


    def export_to_pdf(self, layout, output_path):
        print(f"We've made it to export...")
        pages = self.paginate(layout)
        page1 = pages[0]
        page_size_px = page1.geometry.to("px", dpi=self.dpi).size
        page_size_mm = page1.geometry.to("mm", dpi=self.dpi).size

        writer = QPdfWriter(str(output_path))
        writer.setResolution(self.dpi)
        writer.setPageSizeMM(page_size_mm)

        painter = QPainter(writer)

        for i, page in enumerate(pages):
            if i > 0:
                writer.newPage()

            img = page.image
            if img and not img.isNull():
                painter.drawImage(QRectF(0, 0, page_size_px.width(), page_size_px.height()), img)

        painter.end()


