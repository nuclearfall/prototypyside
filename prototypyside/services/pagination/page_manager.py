# import re
# import math
# import uuid
# from typing import Dict, List, Tuple, Any, List, Optional, Sequence, TYPE_CHECKING
# # services/page_manager.py
# from dataclasses import dataclass
# from math import ceil
# from PySide6.QtCore import QRectF, QPointF 

# from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QGraphicsItemGroup, QGraphicsScene 
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
# from prototypyside.services.undo_commands import ChangePropertiesCommand
# from prototypyside.models.page_model import Page

# if TYPE_CHECKING:
#     from prototypyside.models.layout_template import LayoutTemplate
#     from prototypyside.models.layout_slot import LayoutSlot

# def parse_prop_name(s: str) -> Tuple[str, str]:
#     """
#     Splits `s` into (before, after) at the *first* underscore.
#     If there is no underscore, returns (s, '').
#     """
#     m = re.match(r'^([^_]+)_(.*)$', s)
#     if m:
#         return m.group(1), m.group(2)
#     else:
#         # no underscore found
#         return s, ''

# def obj_from_prop(tab, template, objstr, undo_stack=None) -> object:
#     obj_types = {
#         "layout": "LayoutTemplate",
#         "component": ComponentTemplate,
#     }
#     ostr, prop = parse_prop_name(ostr)
#     if prop and isinstance(template, obj_types.get(ostr, None)):
#         if hasttr(template, prop) and undo_stack:
#             command = ChangePropertiesCommand()


# PAGE_SIZES = {
#     # North American Standard & Common Wide-Format Sizes
#     "Letter (8.5x11 inches)": UnitStrGeometry(width="8.5in", height="11.0in", unit="in"),
#     "Legal (8.5x14 inches)": UnitStrGeometry(width="8.5in", height="14.0in", unit="in"),
#     "Tabloid / Ledger (11x17 inches)": UnitStrGeometry(width="11.0in", height="17.0in", unit="in"),
#     "Super B (13x19 inches)": UnitStrGeometry(width="13.0in", height="19.0in", unit="in"),

#     # International Standard (ISO 216 "A" Series) & Common Wide-Format Sizes
#     "A4 (210x297 mm)": UnitStrGeometry(width="210mm", height="297mm", unit="mm"),
#     "A3 (297x420 mm)": UnitStrGeometry(width="297mm", height="420mm", unit="mm"),
#     "A3+ (329x483 mm)": UnitStrGeometry(width="329mm", height="483mm", unit="mm"), # Equivalent to Super B
#     "A2 (420x594 mm)": UnitStrGeometry(width="420mm", height="594mm", unit="mm"),
#     "A1 (594x841 mm)": UnitStrGeometry(width="594mm", height="841mm", unit="mm"),
#     "A0 (841x1189 mm)": UnitStrGeometry(width="841mm", height="1189mm", unit="mm"),
# }

PRINT_POLICIES = {
    'Letter: 3x3 Standard 2.5"x3.5" Cards': {
        "page_size": "Letter (8.5x11 inches)",
        "geometry": UnitStrGeometry(width="8.5in", height="11in", unit="in", dpi=300),
        "is_landscape": False,
        "rows": 3,
        "columns": 3,
        "whitespace": [
            UnitStr("0.25in", dpi=300),  # top
            UnitStr("0.25in", dpi=300),  # bottom
            UnitStr("0.5in", dpi=300),   # left
            UnitStr("0.5in", dpi=300),   # right
            UnitStr("0.0in", dpi=300),   # spacing_x
            UnitStr("0.0in", dpi=300)    # spacing_y
        ],
        "duplex_print": False,
        "oversized": False,
        "lock_at": 1
    },
    'Letter: 2x4 Standard 2.5"x3.5" Cards': {
        "page_size": "Letter (8.5x11 inches)",
        "geometry": UnitStrGeometry(width="8.5in", height="11in", unit="in", dpi=300),
        "is_landscape": True,
        "rows": 2,
        "columns": 4,
        "whitespace": [
            UnitStr("0.75in", dpi=300),
            UnitStr("0.75in", dpi=300),
            UnitStr("0.5in", dpi=300),
            UnitStr("0.5in", dpi=300),
            UnitStr("0.0in", dpi=300),
            UnitStr("0.0in", dpi=300)
        ],
        "duplexed": False # checked by the ExportManager to alternate page rotation
    },
    'Letter: 2x4 Standard 2.5"x3.5" Cards (Folded)': {
        "page_size": "Letter (8.5x11 inches)",
        "geometry": UnitStrGeometry(width="8.5in", height="11in", unit="in", dpi=300),
        "is_landscape": True,
        "rows": 2,
        "columns": 4,
        "whitespace": [
            UnitStr("0.75in", dpi=300),
            UnitStr("0.75in", dpi=300),
            UnitStr("0.5in", dpi=300),
            UnitStr("0.5in", dpi=300),
            UnitStr("0.0in", dpi=300),
            UnitStr("0.0in", dpi=300)
        ],
        "item_indicies": {"index": [4, 5, 6, 7], "rotation": 180}
    },
    'Letter: 2x4 Standard 2.5"x3.5" Cards': {
        "page_size": "Letter (8.5x11 inches)",
        "geometry": UnitStrGeometry(width="8.5in", height="11in", unit="in", dpi=300),
        "is_landscape": True,
        "rows": 2,
        "columns": 4,
        "whitespace": [
            UnitStr("0.75in", dpi=300),
            UnitStr("0.75in", dpi=300),
            UnitStr("0.5in", dpi=300),
            UnitStr("0.5in", dpi=300),
            UnitStr("0.0in", dpi=300),
            UnitStr("0.0in", dpi=300)
        ],
        "items": {"index": [0, 1, 2, 3, 4, 5, 6, 7, 8], "rotation": 180},
        "duplex_print": True 
    },    
    'Letter: 10x13 Small 0.5" Tokens': {
        "page_size": "Letter (8.5x11 inches)",
        "geometry": UnitStrGeometry(width="8.5in", height="11in", unit="in", dpi=300),
        "is_landscape": False,
        "rows": 13,
        "columns": 9,
        "whitespace": [
            UnitStr("0.5in", dpi=300),
            UnitStr("0.5in", dpi=300),
            UnitStr("0.5in", dpi=300),
            UnitStr("0.5in", dpi=300),
            UnitStr("0.25in", dpi=300),
            UnitStr("0.25in", dpi=300)
        ]
    },
    'Letter: 7x10 Medium 0.75" Tokens': {
        "page_size": "Letter (8.5x11 inches)",
        "geometry": UnitStrGeometry(width="8.5in", height="11in", unit="in", dpi=300),
        "is_landscape": False,
        "rows": 10,
        "columns": 7,
        "whitespace": [
            UnitStr("0.5in", dpi=300),
            UnitStr("0.5in", dpi=300),
            UnitStr("0.5in", dpi=300),
            UnitStr("0.5in", dpi=300),
            UnitStr("0.25in", dpi=300),
            UnitStr("0.25in", dpi=300)
        ]
    },
    'Letter: 6x9 Standard 1.0" Tokens': {
        "page_size": "Letter (8.5x11 inches)",
        "geometry": UnitStrGeometry(width="8.5in", height="11in", unit="in", dpi=300),
        "is_landscape": False,
        "rows": 8,
        "columns": 6,
        "whitespace": [
            UnitStr("0.5in", dpi=300),
            UnitStr("0.5in", dpi=300),
            UnitStr("0.5in", dpi=300),
            UnitStr("0.5in", dpi=300),
            UnitStr("0.125in", dpi=300),
            UnitStr("0.125in", dpi=300)
        ]
    }
}


# class PageManager:
#     def __init__(self, registry, settings):
#         self.registry = registry
#         self.settings = settings

#     # EDITOR: add a live root under the scene and parent the page's slots
#     def mount(self, layout_template, scene: QGraphicsScene, page_index: int):
#         # Ensure grid is up-to-date (rows/cols/whitespace)
#         layout_template.updateGrid()

#         angle = self._page_angle(layout_template, page_index)
#         rect_px = layout_template.geometry.to(self.unit, dpi=self.settings.dpi).rect

#         root = QGraphicsItemGroup()
#         root.setRotation(angle)
#         root.setPos(0, 0)
#         scene.addItem(root)

#         # Pick the slots that belong to this page (flat list = one page; if pagination == CSV-driven, we still mount visible slots only)
#         visible_slots = layout_template.items
#         slot_angles = self._slot_angles(layout_template, page_index, visible_slots)

#         # Parent slots to root for this page view
#         for sl in visible_slots:
#             sl.setParentItem(root)

#         page = Page(index=page_index, angle=angle, rect_px=rect_px, slot_angles=slot_angles)
#         return page, root

#     # EDITOR: remove previously mounted root
#     def unmount(self, scene: QGraphicsScene, root_item: QGraphicsItem):
#         if root_item and root_item.scene() is scene:
#             scene.removeItem(root_item)

#     # EXPORT: build a page graph OFF-scene (mirrors mount semantics)
#     def snapshot(self, layout_template, page_index: int):
#         layout_template.updateGrid()

#         angle = self._page_angle(layout_template, page_index)
#         rect_px = layout_template.geometry.to(self.unit, dpi=self.settings.dpi).rect

#         root = QGraphicsItemGroup()
#         root.setRotation(angle)
#         root.setPos(0, 0)

#         visible_slots = []
#         for sl in layout_template.items:
#             # Shallow “export clone”: reuse the slot item, but do not attach to the live scene
#             # If you truly need isolation, clone slots here instead of reusing
#             sl.setParentItem(root)
#             visible_slots.append(sl)

#         slot_angles = self._slot_angles(layout_template, page_index, visible_slots)
#         page = Page(index=page_index, angle=angle, rect_px=rect_px, slot_angles=slot_angles)
#         return page, root

#     # SHARED: page count is a pure function of rows/cols × CSV rows × copies
#     def compute_page_count(self, layout_template, csv_rows_count: int | None, copies: int = 1) -> int:
#         slots_per_page = max(len(layout_template.items), 1)
#         rows = max(csv_rows_count or 1, 1)
#         return ceil(rows / slots_per_page) * max(copies, 1)

#     # Helpers (extend later for duplex/landscape/item-rotation per policy)
#     def _page_angle(self, layout_template, page_index: int) -> float:
#         return 0.0  # hook up if you support per-page rotation

#     def _slot_angles(self, layout_template, page_index: int, slots: list["LayoutSlot"]) -> list[float]:
#         # Return absolute per-slot angles (e.g., for item_rotation policy)
#         return [0.0] * len(slots)


# # class PageManager:
# #     def __init__(self, registry, settings):
# #         self._registry = registry     # your ProtoRegistry/root
# #         self._settings = settings     # AppSettings (unit, dpi)

# #     # ---- math helpers -----------------------------------------------------
# #     @staticmethod
# #     def _norm(deg: float) -> float:
# #         d = deg % 360.0
# #         return d + 360.0 if d < 0 else d

# #     @staticmethod
# #     def page_rotation_deg(is_landscape: bool, duplex: bool, page_index: int) -> float:
# #         base = 90.0 if is_landscape else 0.0
# #         if duplex and (page_index % 2 == 1):
# #             base += 180.0
# #         return (base % 360.0)

# #     # ---- compute a Page descriptor ----------------------------------------
# #     def build_page(self, template, page_index: int) -> Page:
# #         dpi = self._settings.dpi
# #         page_rect = template.geometry.to(self.unit, dpi=dpi).rect  # QRectF
# #         angle = self.page_rotation_deg(template.is_landscape, template.duplex_print, page_index)

# #         # Per-slot final angles
# #         custom = template.item_rotation if getattr(template, "item_rotation", None) else []
# #         slot_angles: List[float] = []
# #         for idx, slot in enumerate(template.slots):  # row-major
# #             base = getattr(slot, "base_rotation", 0.0) or 0.0
# #             add  = custom[idx] if idx < len(custom) else 0.0
# #             slot_angles.append(self._norm(angle + base + add))

# #         return Page(index=page_index, angle=angle, rect_px=page_rect, slot_angles=slot_angles)

# #     # ---- GUI mounting (live) ----------------------------------------------
# #     def mount(self, template, scene, page_index: int) -> tuple[Page, QGraphicsItemGroup]:
# #         """
# #         Returns (Page, page_root).
# #         page_root is added to the scene; template becomes a child of page_root.
# #         Slots remain children of template.
# #         """
# #         page = self.build_page(template, page_index)

# #         # 1) Create the page root container
# #         root = QGraphicsItemGroup()
# #         scene.addItem(root)

# #         # 2) Parent the template under the root (keep slots under template)
# #         template.setParentItem(root)
# #         template.setPos(0, 0)  # if your template already lives at (0,0), this is redundant

# #         # 3) Apply per-slot *relative* rotation (exclude page angle!)
# #         custom = getattr(template, "item_rotation", None) or []
# #         for idx, slot in enumerate(template.slots):
# #             # make sure origin is sensible for rotation
# #             slot.setTransformOriginPoint(slot.boundingRect().center())
# #             base = getattr(slot, "base_rotation", 0.0) or 0.0
# #             add  = custom[idx] if idx < len(custom) else 0.0
# #             slot.setRotation((base + add) % 360.0)

# #         # 4) Set the page rotation on the root *after* children are in place,
# #         #    and rotate around the page center
# #         root.setTransformOriginPoint(page.rect_px.center())
# #         root.setRotation(page.angle)

# #         return page, root

# #     # ---- unmount (GUI cleanup) --------------------------------------------
# #     def unmount(self, scene, page_root_item: QGraphicsItem) -> None:
# #         if page_root_item is None:
# #             return
# #         scene.removeItem(page_root_item)

# #     # ---- export snapshot (frozen) -----------------------------------------
# #     def snapshot(self, template, page_index: int):
# #         """
# #         For export: deep-clone the needed objects into an off-scene structure.
# #         Returns (Page, cloned_root_item) that ExportManager can render.
# #         """
# #         page = self.build_page(template, page_index)

# #         # Clone a minimal tree (template -> slots -> component templates -> elements)
# #         # Use your ProtoRegistry/Factory to clone with new PIDs.
# #         clone_lt = self._registry.clone(template)  # per your existing API
# #         # Create a dedicated root for the cloned page
# #         cloned_root = QGraphicsObject()
# #         cloned_root.setTransformOriginPoint(page.rect_px.center())
# #         cloned_root.setRotation(page.angle)

# #         # Add cloned slots under cloned_root; apply angles
# #         for idx, cslot in enumerate(clone_lt.slots):
# #             cslot.setParentItem(cloned_root)
# #             cslot.setTransformOriginPoint(cslot.boundingRect().center())
# #             cslot.setRotation(page.slot_angles[idx])

# #         return page, cloned_root