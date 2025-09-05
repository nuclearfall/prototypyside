from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Any, Union, TYPE_CHECKING
from enum import IntEnum
import json

from PySide6.QtWidgets import QGraphicsObject, QGraphicsItem, QStyleOptionGraphicsItem
from PySide6.QtCore import Qt, QRectF, QPointF, QSizeF, QMarginsF, Signal
from PySide6.QtGui import QPainter, QPixmap, QColor, QImage, QPen, QBrush,  QPageLayout

from prototypyside.models.layout_slot import LayoutSlot
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.services.proto_class import ProtoClass
from prototypyside.utils.units.unit_str_helpers import geometry_with_px_rect, geometry_with_px_pos
from prototypyside.config import DISPLAY_MODE_FLAGS, PAGE_UNITS
 
from prototypyside.services.pagination.page_manager import PRINT_POLICIES
from prototypyside.models.component_template import ComponentTemplate
from prototypyside.services.proto_registry import ProtoRegistry
from prototypyside.utils.valid_path import ValidPath
from prototypyside.utils.graphics_item_helpers import rotate_by

class WhitespaceIndex(IntEnum):
    MARGIN_TOP    = 0
    MARGIN_BOTTOM = 1
    MARGIN_LEFT   = 2
    MARGIN_RIGHT  = 3
    SPACING_X     = 4
    SPACING_Y     = 5

class LayoutTemplate(QGraphicsObject):
    template_changed = Signal()
    policyChanged = Signal()     # landscape/duplex/item_rotation changes
    slotsChanged  = Signal()     # rows/cols rebuild, autofill, etc.


    def __init__(
        self, 
        proto:ProtoClass,
        pid: str,
        registry: ProtoRegistry,
        pagination_policy: Optional[dict] = None,  
        name: Optional[str] = None, 
        file_path: Optional[Path] = None,
        parent: Optional[QGraphicsObject] = None,
        rehydrated = False
    ):
        super().__init__(parent)
        self.proto = proto
        self._pid = pid
        self._registry = registry      
        self._name = name
        self._file_path = ValidPath.file(file_path, must_exist=True)
        self._items: list[LayoutSlot] = []
        if self._file_path:
            self._name = self._file_path
            self._name = registry.validate_name(proto, name)

        self._dpi = registry.settings.dpi
        self._unit = "px" or registry.settings.unit
        self._name = registry.validate_name(proto, name)

        self._polkey = pagination_policy or 'Letter: 3x3 Standard 2.5"x3.5" Cards'
        pol = PRINT_POLICIES.get(self._polkey)
        self._geometry = pol.get("geometry")
        self._rows = pol.get("rows", 3)
        self._columns = pol.get("columns", 3)
        self._page_size = pol.get("page_size", UnitStrGeometry(width="8.5in", height="11in"))
        self._orientation = pol.get("orientation", "portrait")
        self._is_landscape = False

        self._duplex_print = pol.get("duplex_print", False)
        self._whitespace = pol.get(
            "whitespace", [
                UnitStr("0.25in", dpi=300),  # top
                UnitStr("0.25in", dpi=300),  # bottom
                UnitStr("0.5in", dpi=300),   # left
                UnitStr("0.5in", dpi=300),   # right
                UnitStr("0.0in", dpi=300),   # spacing_x
                UnitStr("0.0in", dpi=300)    # spacing_y
            ]
        )
        self.setGrid()

        self._content = None
        self.first_pass = True
        self.setAcceptHoverEvents(True)

    def boundingRect(self) -> QRectF: 
        return self._geometry.to("px", dpi=self.dpi).rect

    def setRect(self, new_rect: QRectF):
        self.prepareGeometryChange()
        self.geometry = geometry_with_px_rect(self._geometry, new_rect, dpi=self.dpi)
        self.update()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        if change == QGraphicsItem.ItemPositionChange:
            self._geometry = geometry_with_px_pos(self._geometry, value, dpi=self.dpi)
        return super().itemChange(change, value)

    # ———————————————— property setters/getters ——————————————————————————— #
    @property
    def file_path(self):
        return self._file_path

    @file_path.setter
    def file_path(self, path):
        path = Path(path).expanduser().resolve() if isinstance(path, str) else None
        if path and str(Path(path)) != str(self._file_path):
            self._file_path = Path(path).expanduser().resolve() 
 
    @property
    def polkey(self):
        return self._polkey
    
    @polkey.setter
    def polkey(self, pol):
        if pol == self._polkey or pol not in PRINT_POLICIES:
            return
        self._polkey = pol
        policy = PRINT_POLICIES[pol]

        # Apply via property setters so signals fire consistently:
        if "geometry" in policy and policy["geometry"] is not None:
            self._geometry = policy["geometry"]
        if "rows" in policy:
            self._rows = int(policy["rows"])
        if "columns" in policy:
            self._columns = int(policy["columns"])
        if "whitespace" in policy:
            self._whitespace = policy["whitespace"]
        if "orientation" in policy:
            self.orientation = bool(policy["orientation"])
        # if "duplex_print" in policy:
        #     self._duplex_print = bool(policy["duplex_print"])
        # if "page_size" in policy:
        #     self._page_size = policy["page_size"]
        # if "item_rotation" in policy:
        #     self._item_rotation = list(policy["item_rotation"])

        self.policyChanged.emit()
        # rows/columns may have changed; ensure grid dims up to date:
        self.setGrid()
        self.updateGrid()

    @property
    def name(self) -> str: return self._name

    @name.setter
    def name(self, value):
        if value != self._name:
            self._name = value
    
    @property
    def content(self) -> str: return self._content

    @content.setter
    def content(self, new):
        if new != self._content:
            self._content = new

    @property
    def dpi(self) -> int: return self._dpi

    @dpi.setter
    def dpi(self, new: int):
        print(f"[LAYOUT_TEMPLATE] Attempting to set new dpi to {new}")
        if self._dpi != new:
            self._dpi = new
            for item in self._items:
                item.dpi = self._dpi
            self.invalidate_cache()
            self.update()

    @property
    def unit(self) -> str: return self._unit

    @unit.setter
    def unit(self, new: str):
        if self._unit != new:
            self._unit = new
            for item in self._items:
                item.unit = self._unit

    @property
    def geometry(self) -> UnitStrGeometry: return self._geometry.to("px", dpi=self.dpi)
    
    @geometry.setter
    def geometry(self, new_geom: UnitStrGeometry):
        if self._geometry == new_geom:
            return
        print(f"[LAYOUT_TEMPLATE] Attempting to set geometry to {new_geom}")
        self.prepareGeometryChange()
        self._geometry = new_geom
        self.updateGrid()
        # block the itemChange override
        self.blockSignals(True)
        super().setPos(self._geometry.to("px", dpi=self.dpi).pos)
        self.blockSignals(False)
   
    @property
    def page_size(self) -> str: return self._page_size
        
    @page_size.setter
    def page_size(self, value):
        if self._page_size != value:
            self._page_size = value

    @property
    def registry(self) -> "Proto Registry": return self._registry

    @property
    def pid(self) -> str: return self._pid
    
    @pid.setter
    def pid(self, value):
        self._pid = value
        self.template_changed.emit()

    @property
    def rows(self) -> int: return self._rows

    @rows.setter
    def rows(self, value):
        if value != self._rows:
            self._rows = value
            # self.setGrid(self._registry, self._rows, self._columns)

    @property
    def columns(self) -> int: return self._columns

    @columns.setter
    def columns(self, value):
        if value != self._columns:
            self._columns = value
            # self.setGrid(self._registry, self._rows, self._columns)

    @property
    def items(self) -> list[LayoutSlot]: return self._items

    @items.setter
    def items(self, slot_vals: list["LayoutSlot"]):
        # If rows/cols aren’t initialized yet (e.g., during rehydrate/clone),
        # don’t enforce a hard count; otherwise validate length.
        if self._rows and self._columns:
            expected = self._rows * self._columns
            if len(slot_vals) > expected:
                raise ValueError(f"Too many values; expected {expected} but got {len(slot_vals)}.")

        # 1) Assign
        self._items = list(slot_vals or [])

        # 2) Ensure parent/scene wiring & basic row/col defaults (safe no-ops if already set)
        for idx, slot in enumerate(self._items):
            # keep row/col stable if already set; otherwise derive from index
            if getattr(slot, "row", None) is None:    slot.row    = idx // max(self._columns or 1, 1)
            if getattr(slot, "column", None) is None: slot.column = idx %  max(self._columns or 1, 1)
            if hasattr(slot, "setParentItem") and slot.parentItem() is not self:
                slot.setParentItem(self)

        # 3) Invalidate page cache (optional)
        self.update()

    # @items.setter
    # def items(self, slot_vals: list[LayoutSlot]):
    #     expected = self._rows * self._columns
    #     if len(slot_vals) > expected:
    #         raise ValueError(f"Too mnany values {expected} were expected.")

    @property
    def slots(self) -> list[list[LayoutSlot]]:
        # Derived 2-D view (rows × columns) from the flat list
        grid: list[list[LayoutSlot]] = []
        if not self._items:
            return grid
        for r in range(self._rows):
            row = []
            base = r * self._columns
            for c in range(self._columns):
                row.append(self._items[base + c])
            grid.append(row)
        return grid
        
    @property
    def duplex_print(self) -> bool: return self._duplex_print

    @duplex_print.setter
    def duplex_print(self, v):
        if v != self.duplex_print:
            self._duplex_print = v
            self.policyChanged.emit()
    @property
    def whitespace(self) -> List[UnitStr]: return self._whitespace

    @whitespace.setter
    def whitespace(self, value: List[UnitStr]) -> None:
        if value != self._whitespace:
            self._whitespace = value
            self.updateGrid()

    @property
    def is_landscape(self) -> bool: return self._is_landscape

    @is_landscape.setter
    def is_landscape(self, value: bool):
        self._is_landscape = value
        self.orientation = "portrait" if value is False else "landscape"
       
    @property
    def orientation(self) -> str: return self._orientation

    @orientation.setter
    def orientation(self, value: str):
        rotation = {
            "duplex": 180,
            "landscape": 90,
            "portrait": 0
        }
        if value != self._orientation:
            self._orientation = value
            self.setRotate(value)

    @property
    def item_rotation(self) -> float: return self._item_rotation
    
    @item_rotation.setter
    def item_rotation(self, lst):
        self._item_rotation = list(lst or [])
        self.policyChanged.emit()

    @property
    def image(self) -> QImage:
        if not hasattr(self, "_cache_image") or self._cache_image is None:
            self._cache_image = self._render_to_image()
        return self._cache_image


    def _render_to_image(self) -> QImage:
        """
        Renders the entire layout page to a single QImage by compositing pre-rendered slot images.
        
        Assumes each slot has a .geometry and .image property.
        """
        # Calculate full page size in pixels
        self.updateGrid()

            
        page_size = self.geometry.to("px", dpi=self.dpi).rect
        page_size = self.geometry.to("px", dpi=self.dpi).size
        width = max(1, int(page_size.width()))
        height = max(1, int(page_size.height()))

        image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.white)  # or Qt.transparent if preferred

        painter = QPainter(image)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        for slot in self.items:
            if slot.content:
                slot_img = slot.image  # Cached slot image
                if isinstance(slot_img, QImage):
                    size = slot.geometry.to("px", dpi=self._dpi).size 
                    pos = slot.geometry.to("px", dpi=self._dpi).pos
                    target_rect = QRectF(pos, size)      
                    painter.drawImage(target_rect, slot_img)
        painter.end()
        return image

    def clear_slot_content(self):
        for item in self._items:
            item.content = None
        self.update()

    def whitespace_in_units(self, unit="px"):
        return [v.to(unit, dpi=self._dpi) for v in self._whitespace]

    def invalidate_cache(self):
        for slot in self._items:
            slot.invalidate_cache()
        self._cache_image = None

    def setGrid(self, registry=None, rows=None, columns=None):
        registry = registry or self._registry

        # --- targets ------------------------------------------------------------
        target_rows = rows or self._rows or 1
        target_cols = columns or self._columns or 1
        total_new   = target_rows * target_cols

        self._rows = target_rows
        self._columns = target_cols

        # --- geometry for the target grid --------------------------------------
        t, b, l, r, sx, sy = self.whitespace_in_units(unit="in")
        page_in = self._geometry.inch
        w, h = page_in.size.width(), page_in.size.height()

        avail_w = max(0.0, w - l - r - (target_cols - 1) * sx)
        avail_h = max(0.0, h - t - b - (target_rows - 1) * sy)
        cell_w  = (avail_w / target_cols) if target_cols else 0.0
        cell_h  = (avail_h / target_rows) if target_rows else 0.0

        def cell_geom(rr, cc):
            x = l + cc * (sx + cell_w)
            y = t + rr * (sy + cell_h)
            return UnitStrGeometry(width=cell_w, height=cell_h, x=x, y=y, unit="in", dpi=self._dpi)

        # row-major list of desired (row, col, geom)
        targets = [(rr, cc, cell_geom(rr, cc))
                   for rr in range(target_rows)
                   for cc in range(target_cols)]

        scene = self.scene()

        # --- choose survivors (content first, then empties), stable row-major ----
        def row_major_key(it):
            return (getattr(it, "row", 0), getattr(it, "column", 0))

        existing = list(self._items)
        existing.sort(key=row_major_key)

        with_content = [it for it in existing if getattr(it, "_content", None)]
        empties      = [it for it in existing if not getattr(it, "_content", None)]
        survivors    = (with_content + empties)[:total_new]   # keep, in stable order

        # For fast membership checks and later cleanup
        survivor_set = set(survivors)

        # --- build new items in target order, reusing survivors first ------------
        reused_idx = 0
        new_items  = []
        used_pids  = set()

        for (rr, cc, geom) in targets:
            if reused_idx < len(survivors):
                slot = survivors[reused_idx]
                reused_idx += 1
            else:
                slot = registry.create(
                    ProtoClass.LS,
                    geometry=geom,
                    row=rr, column=cc,
                    parent=self
                )

            # update slot → target placement
            slot.row = rr
            slot.column = cc
            slot.geometry = geom
            slot.setPos(geom.px.pos)

            # Add to scene only if not already in the same scene
            if scene and slot.scene() is not scene:
                scene.addItem(slot)

            new_items.append(slot)
            used_pids.add(slot.pid)

        # --- remove/deregister anything not used --------------------------------
        for slot in existing:
            if slot.pid not in used_pids:
                if scene and slot.scene() is scene:
                    scene.removeItem(slot)
                registry.deregister(slot.pid)

        # --- finalize ------------------------------------------------------------
        self._items = new_items
        self.update()
        self.template_changed.emit()



    def updateGrid(self) -> None:
        top, bottom, left, right, spacing_x, spacing_y = self.whitespace_in_units(unit="in")
        page_rect_in = self.geometry.to("in", dpi=self._dpi).rect
        total_w, total_h = page_rect_in.width(), page_rect_in.height()
        avail_w = total_w - left - right - (self._columns - 1) * spacing_x
        avail_h = total_h - top  - bottom - (self._rows    - 1) * spacing_y
        cell_w = max(avail_w / self._columns, 0.0) if self._columns else 0.0
        cell_h = max(avail_h / self._rows,    0.0) if self._rows else 0.0

        scene = self.scene()
        if self.first_pass and scene:
            for slot in self.items:
                if not slot.parentItem():
                    slot.addParentItem()
                if not slot.scene():
                    scene.addItem(slot)
                    scene.setPos(slot.geometry.px.pos)
                slot.update()
            self.first_pass = False

        # print(f"On updateGrid call:\nTemplate {self.pid} has scene: {bool(self.scene())}\nTemplate dimensions:{self.geometry.px.rect}\n")
        # Update every slot’s geometry from flat list

        for r in range(self._rows):
            for c in range(self._columns):
                slot = self._items[self._idx(r, c)]
                x = left + c * (cell_w + spacing_x)
                y = top  + r * (cell_h + spacing_y)
                slot.geometry = UnitStrGeometry(width=cell_w, height=cell_h, x=x, y=y, unit="in", dpi=self._dpi)
                slot.row = r
                slot.column = c
                pos = slot.geometry.px.pos
                slot.setPos(pos)

                # print(f" - Slot {slot.pid} has scene: {slot.scene()}\n   - slot grid location: {r, c}\n   - position set to {slot.pos()}")
                slot.invalidate_cache()
                # if slot.parentItem() is not self:
                #     slot.setParentItem(self)
                # if slot.scene():
                #     scene = self.scene()
                #     scene.addItem(slot)

        self.update()
        self.template_changed.emit()


    # def updateGrid(self) -> None:
    #     """
    #     Recompute and apply each slot’s geometry (size + position) based on:
    #       • self.geometry   – page size & orientation
    #       • self.whitespace - margins, vertical, and horizontal spacing
    #       • self._rows, self._columns

    #     Does NOT create or remove slots; only updates existing ones.
    #     """
    #     # 1. Gather pixel-values for margins & spacing
    #     top, bottom, left, right, spacing_x, spacing_y = self.whitespace_in_units(unit="in")
    #     page_size = self.geometry.to("in", dpi=self._dpi).rect
    #     total_w, total_h = page_size.width(), page_size.height()

    #     # 2. Compute available area and per-cell size
    #     avail_w = total_w - left - right - (self._columns - 1) * spacing_x
    #     avail_h = total_h - top - bottom - (self._rows    - 1) * spacing_y
    #     cell_w = max(avail_w / self.columns,  0)
    #     cell_h = max(avail_h / self.rows,     0)

    #     # 3. Loop through each slot and assign its new UnitStrGeometry
    #     for r, row in enumerate(self.slots):
    #         for c, slot in enumerate(row):
    #             x = left + c * (cell_w + spacing_x)
    #             y = top  + r * (cell_h + spacing_y)

    #             # rect is local to the slot; pos is the offset on the page
    #             new_geom = UnitStrGeometry(width=cell_w, height=cell_h, x=x, y=y, unit="in", dpi=self._dpi)
    #             slot.geometry = new_geom
    #             slot.row      = r
    #             slot.column   = c
    #             slot.invalidate_cache()   # so that its rendered thumbnail will be rebuilt

    #             if slot.scene() is None and self.scene() is not None:
    #                 slot.setParentItem(self)

    #             px_rect = self.geometry.to("px", dpi=self._dpi).rect
    #             px_pos = self.geometry.to("px", dpi=self._dpi).pos

    #     self.update()
    #     self.template_changed.emit()

    def get_whitespace(self):
        return [m.to("px", dpi=self.dpi) for m in self._whitespace]
        
    def get_item_position(self, row: int, col: int) -> tuple[float, float]:
        item = self._items[self._idx(row, col)]
        pos = item.geometry.to("px", dpi=self.dpi).pos
        return (pos.x(), pos.y())

    def get_item_size(self, row, col):
        return self._items[self._idx(row, col)].geometry.to("px", dpi=self.dpi).size


    def get_item_at_position(self, scene_pos: QPointF) -> Optional["LayoutSlot"]:
        """
        Given a scene-coordinate point, return the LayoutSlot whose rect contains it,
        or None if no item matches.
        """

        for row in range(self.rows):
            for col in range(self.columns):
                item = self.slots[row][col]
                rect = item.geometry.to("px", dpi=self.dpi).rect
                pos = item.geometry.to("px", dpi=self.dpi).pos
                x, y = pos.x(), pos.y()
                w, h = rect.width(), rect.height()
                item_rect = QRectF(x, y, w, h)
                if item_rect.contains(scene_pos):
                    return self.slots[row][col]

        return None

    def replace_template_instances(self, source_pid: str) -> int:
            """
            For every slot whose content is a clone of `source_pid`,
            replace it with a fresh clone of the current source template.

            Returns the number of slots updated.
            """
            if not self.content:
                return

            source = self._registry.global_get(source_pid)
            if not source or not isinstance(source, ComponentTemplate):
                raise TypeError(f"Template with {source_pid} couldn't be located in the registry.")

            updated_count = 0
            for slot in self.items:  # flattens rows → slots
                if hasattr(slot.content, 'tpid') and slot.content.tpid == source_pid:
                    # --- START REPAIR ---
                    # Keep a reference to the old content before replacing it.
                    old_content = slot.content
                    
                    # Create and assign the new clone.
                    new_clone = self._registry.clone(source)
                    slot.content = new_clone
                    updated_count += 1
                    
                    if old_content:
                        # Create a copy of the list to iterate over, as remove_item modifies it.
                        for item in list(getattr(old_content, 'items', [])):
                            # remove_item handles deregistering the child element.
                            old_content.remove_item(item)
                        # Deregister the old container itself.
                        self._registry.deregister(old_content.pid)
            
            if updated_count > 0:
                self.update()
            
            return updated_count

    def _idx(self, r: int, c: int) -> int:
        return r * self._columns + c

    def _in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self._rows and 0 <= c < self._columns

    def clone(self):
        registry = self.registry
        return registry.clone(self)

    def to_dict(self) -> Dict:
        items = [item.to_dict() for item in self._items]
        return {
            "pid": self._pid,
            "name": self._name,
            "file_path": str(self._file_path),
            "page_size": self._page_size,
            "pkey": self._polkey,
            "geometry": self._geometry.to_dict(),
            "rows": self._rows,
            "columns": self._columns,
            "whitespace": [w.to_dict() for w in self.whitespace],
            "orientation": self._orientation,
            "content": self._content,
            "items": items,
        }

    @classmethod
    def from_dict(cls, data: dict, registry: "ProtoRegistry") -> "LayoutTemplate":
        serial_pid = ProtoClass.validate_pid(data.get("pid"))
        if not serial_pid:
            raise ValueError(f"Invalid or missing pid for LayoutTemplate: {serial_pid!r}")

        geom = UnitStrGeometry.from_dict(data.get("geometry", None))
        # Do NOT pass geometry=... to __init__; your __init__ doesn't accept it.
        inst = cls(
            proto=ProtoClass.LT,
            pid=serial_pid,
            registry=registry,
            pagination_policy=data.get("pagination_policy"),
            name=data.get("name"),
        )

        # Apply geometry directly to the backing field to avoid triggering updateGrid()
        if geom:
            inst._geometry = geom

        # File path (tolerant)
        fp_raw = data.get("file_path", None)
        if fp_raw:
            try:
                file_path = Path(fp_raw).expanduser().resolve()
                if file_path.exists():
                    inst.file_path = file_path
            except Exception:
                pass  # keep going

        inst._page_size = data.get("page_size", "custom")
        inst._rows = int(data.get("rows", 3))
        inst._columns = int(data.get("columns", 3))
        inst._orientation = bool(data.get("orientation", False))

        # Whitespace: use provided 6-tuple if present; otherwise keep whatever policy set earlier
        ws_in = data.get("whitespace")
        if ws_in:
            ws_vals = [UnitStr.from_dict(d) for d in ws_in if d is not None]
            if len(ws_vals) == 6:
                inst._whitespace = ws_vals  # set private to avoid early updateGrid()

        inst.setGrid(registry=registry, rows=inst._rows, columns=inst._columns)
        inst.updateGrid()
        return inst

    def paint(self, painter: QPainter, option, widget=None):
        """
        Paints the background, border, and grid of the layout page.

        Parameters
        ----------
        painter : QPainter
            The QPainter used for rendering.
        option : QStyleOptionGraphicsItem
            Option passed from the scene.
        widget : QWidget, optional
            The widget being painted on.
        """

        rect = self.geometry.to("px", dpi=self.dpi).rect
        painter.setRenderHint(QPainter.Antialiasing)

        rows = self._rows
        cols = self._columns

        # ——— Background ———
        painter.save()
        painter.setBrush(Qt.white)
        painter.setPen(QPen(Qt.black, 2))
        painter.drawRect(rect)
        painter.restore()

        # ——— Grid lines ———
        # top_margin, bottom_margin, left_margin, right_margin, spacing_x, spacing_y = self.whitespace_in_units()


        # total_w = rect.width() - left_margin - right_margin - spacing_x * (cols - 1)
        # total_h = rect.height() - top_margin - bottom_margin - spacing_y * (rows - 1)

        # cell_w = total_w / cols if cols > 0 else 0
        # cell_h = total_h / rows if rows > 0 else 0

        # grid_pen = QPen(Qt.gray, 1, Qt.DashLine)
        # painter.setPen(grid_pen)

        # # Horizontal grid lines
        # for r in range(rows + 1):
        #     y = rect.top() + top_margin + r * (cell_h + spacing_y) - (spacing_y if r > 0 else 0)
        #     x_start = rect.left() + left_margin
        #     x_end = x_start + total_w + spacing_x * (cols - 1)
        #     painter.drawLine(x_start, y, x_end, y)

        # # Vertical grid lines
        # for c in range(cols + 1):
        #     x = rect.left() + left_margin + c * (cell_w + spacing_x) - (spacing_x if c > 0 else 0)
        #     y_start = rect.top() + top_margin
        #     y_end = y_start + total_h + spacing_y * (rows - 1)
        #     painter.drawLine(x, y_start, x, y_end)
