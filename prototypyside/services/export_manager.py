from math import ceil
from PySide6.QtCore import QSizeF
from PySide6.QtGui  import QPainter, QPdfWriter, QPageSize
from PySide6.QtWidgets import QGraphicsScene
from prototypyside.utils.unit_str_geometry import UnitStrGeometry

class ExportManager:
    def __init__(self, merge_manager, registry, unit="in", dpi=300):
        self.merge_manager = merge_manager
        self.registry      = registry
        self.dpi           = dpi
        self.unit          = unit
        self.page_size_in  = QSizeF(8.5, 11.0)  # Letter in inches
  
    def export_to_pdf(self, layout_template, output_path):
        # ——————————————————————————————
        # 1) Prep layout geometry for high-dpi rendering
        print("Preparing for export...")
        print(layout_template.name)
        template = layout_template.get_template()
        registry = layout_template.registry

        dpi=300
        tg = layout_template.geometry
        layout_template.geometry = UnitStrGeometry(
            width=tg.width, height=tg.height, unit=self.unit, dpi=self.dpi
        )

        # ——————————————————————————————
        # 2) Grab every CSV row WITHOUT mutating the master template
        # template is a clone so will have a non None template_pid
        all_rows  = self.merge_manager.get_all_rows(template.template_pid)
        print(f"Have csv: {all_rows}")
        total     = len(all_rows)

        # ——————————————————————————————
        # 3) Figure out our grid dimensions (m rows × n cols)
        slot_grid  = layout_template.items  # List[List[LayoutSlot]]
        m          = layout_template.rows        
        n          = layout_template.columns
        per_page   = m * n
        pages      = ceil(total / per_page) if per_page else 0
        print(f"Total rows to populate {total} on {pages} pages")
        # ——————————————————————————————
        # 4) Clone the layout template for each page
        clone = registry.clone(layout_template)
        print()
        page_templates = [
            registry.clone(layout_template)
            for _ in range(pages)
        ]
        print(f"Page templates have been prepped. {[p.pid for p in page_templates]}")

        # ——————————————————————————————
        # 5) Set up PDF writer & painter once
        pdf = QPdfWriter(output_path)
        pdf.setPageSize(QPageSize(self.page_size_in, QPageSize.Inch))
        pdf.setResolution(self.dpi)
        painter = QPainter(pdf)
        painter.setRenderHint(QPainter.Antialiasing)

        # ——————————————————————————————
        # 6) Loop pages: fill slots, render, newPage()
        for pg_idx, page in enumerate(page_templates):
            scene = QGraphicsScene()
            page.setPos(0, 0)
            scene.addItem(page)
            scene.setSceneRect(page.geometry.to("in", dpi=self.dpi).rect)

            # Clear any old content
            for row in page.items:
                for slot in row:
                    slot.content = None

            # Fill slots with component clones + data
            flat_slots = [slot for row in page.items for slot in row]
            start = pg_idx * per_page
            slice_rows = all_rows[start : start + per_page]
            for slot, row_data in zip(flat_slots, slice_rows):
                comp = registry.clone(template)
                print(comp)
                for item in comp.items:
                    if item.name.startswith("@"):
                        item.content = row_data.get(item.name, "")
                slot.content = comp
                slot.invalidate_cache()

            # Render this page
            scene.render(painter)
            page.invalidate_cache()
            page.update()

            # Advance to next PDF page if needed
            if pg_idx < pages - 1:
                pdf.newPage()

        painter.end()
