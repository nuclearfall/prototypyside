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
from prototypyside.utils.units.unit_str_helpers import geometry_with_px_rect, geometry_with_px_pos
from prototypyside.config import PAGE_SIZES, DISPLAY_MODE_FLAGS, PAGE_UNITS
from prototypyside.utils.proto_helpers import get_prefix, resolve_pid
from prototypyside.services.pagination.page_manager import PRINT_POLICIES, PAGE_SIZES
from prototypyside.models.component_template import ComponentTemplate
if TYPE_CHECKING:
    from prototypyside.services.proto_registry import ProtoRegistry

class WhitespaceIndex(IntEnum):
    MARGIN_TOP    = 0
    MARGIN_BOTTOM = 1
    MARGIN_LEFT   = 2
    MARGIN_RIGHT  = 3
    SPACING_X     = 4
    SPACING_Y     = 5

class LayoutTemplate(QGraphicsObject):
    template_changed = Signal()
    marginsChanged = Signal()
    spacingChanged = Signal()
    is_landscapeChanged = Signal()

    def __init__(self, pid, registry, name=None, pagination_policy='Letter: 3x3 Standard 2.5"x3.5" Cards', parent=None):
        super().__init__(parent)
        self._pid = pid
        self._registry = registry
        self._dpi = 300
        self._unit = "px"
        self._name = name
        self._pagination_policy = pagination_policy
        self._pkey = pagination_policy

        pol = PRINT_POLICIES[pagination_policy]
        self._rows = pol.get("rows")
        self._columns = pol.get("columns")
        self._page_size = pol.get("page_size")
        self._is_landscape = pol.get("is_landscape")

        geometry = PAGE_SIZES.get(self._page_size)
        rect = geometry.px.rect
        w = rect.width()
        h = rect.height()

        self._portrait_geometry = geometry
        self._landscape_geometry = self._change_orientation(geometry)
        # check to see if the page is already in a horizontal orientation
        if w > h and self.is_landscape:
            self._landscape_geometry = geometry
            self._portrait_geometry = self._change_orientation(geometry)

        self._geometry = self._portrait_geometry if not self._is_landscape else self._landscape_geometry
        self._whitespace = pol.get("whitespace")

        self._content = None
        self.items = []

        self.setAcceptHoverEvents(True)

        self.set_policy_props()

    def set_policy_props(self):
        policy = self._pkey
        if policy in PRINT_POLICIES:
            for prop, value in PRINT_POLICIES.get(policy).items():
                fprop = f"_{prop}"
                if hasattr(self, prop):
                    setattr(self, prop, value)
            self.marginsChanged.emit()
            self.spacingChanged.emit()
            self.updateGrid()

    def boundingRect(self) -> QRectF: 
        return self._geometry.to(self.unit, dpi=self.dpi).rect

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
    def pagination_policy(self):
        return self._pagination_policy
    
    @pagination_policy.setter
    def pagination_policy(self, pol):
        self._pagination_policy = pol
        pol = PRINT_POLICIES[pol]
        self.rows = pol.get("rows")
        self.columns = pol.get("columns")
        self.geometry = pol.get("geometry")
        self.whitespace = pol.get("whitespace")
        self.setGrid(self._registry, rows=pol.get("rows"), columns=pol.get("columns"))
        is_landscape = pol.get("is_landscape")
        self.is_landscape = is_landscape

        self.updateGrid()

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if value != self._name:
            self._name = value
    
    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, new):
        if new != self._content:
            self._content = new

    @property
    def dpi(self) -> int:
        return self._dpi

    @dpi.setter
    def dpi(self, new: int):
        print(f"[LAYOUTTEMPLATE] Attempting to set new dpi to {new}")
        if self._dpi != new:
            self._dpi = new
            for row in self.items:
                for item in row:
                    item.dpi = self._dpi
        self.invalidate_cache()
        self.update()

    @property
    def unit(self) -> str:
        return self._unit

    @unit.setter
    def unit(self, new: str):
        if self._unit != new:
            self._unit = new
            for item in self.items:
                item.unit = self._unit

    @property
    def geometry(self) -> UnitStrGeometry: return self._geometry.to(self.unit, dpi=self.dpi)
    
    @geometry.setter
    def geometry(self, new_geom: UnitStrGeometry):
        if self._geometry == new_geom:
            return
        self.prepareGeometryChange()
        self._geometry = new_geom
        if self._is_landscape:
            self.geometry = self._landscape_geometry
        else:
            self.geometry = self._portrait_geometry
        self.updateGrid()
        # block the itemChange override
        self.blockSignals(True)
        super().setPos(self._geometry.to(self.unit, dpi=self.dpi).pos)
        self.blockSignals(False)
   
    @property
    def page_size(self):
       return self._page_size
        
    @page_size.setter
    def page_size(self, key):
        if key in PAGE_SIZES and key != "Custom": #custom not implemented
            self._page_size = key
            self.geometry = PAGE_SIZES.get("geometry")

    @property
    def registry(self):
        return self._registry

    @property
    def pid(self):
        return self._pid
    
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
            self.setGrid(self._registry, self._rows, self._columns)

    @property
    def columns(self) -> int: return self._columns

    @columns.setter
    def columns(self, value):
        if value != self._columns:
            self._columns = value
            self.setGrid(self._registry, self._rows, self._columns)

    @property
    def grid(self):
        return (self._rows, self._columns)

    @grid.setter
    def grid(self, tup):
        rows, cols = tup
        if tup != (self._rows, self._columns):
            self._rows = rows
            self._columns = cols
            self.setGrid(self._registry, self._rows, self._columns)

    @property
    def whitespace(self) -> List[UnitStr]:
        return self._whitespace

    @whitespace.setter
    def whitespace(self, value: List[UnitStr]) -> None:
        # --- list/tuple case ---
        if isinstance(value, (list, tuple)):
            if value == self._whitespace:
                return
            if len(value) != len(WhitespaceIndex):  # == 6
                raise ValueError(f"Expected {len(WhitespaceIndex)} whitespace values, got {len(value)}")
            new_ws = []
            for old, new in zip(self._whitespace, value):
                new_ws.append(old if new is None else UnitStr(new, dpi=self.dpi))
            self._whitespace = new_ws

            self.updateGrid()
            self.marginsChanged.emit()
            self.spacingChanged.emit()

    @property
    def is_landscape(self) -> bool:
        return self._is_landscape

    @is_landscape.setter
    def is_landscape(self, value: bool):
        self._is_landscape = value
        self.geometry = self._portrait_geometry if not self._is_landscape else self._landscape_geometry
        print(f"[LAYOUTTEMPLATE]: geometry set to {self.geometry.px}: landscape is {self._landscape_geometry.px} and portrait is {self._portrait_geometry.px}")
        self.updateGrid()
        self.update()

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
        page_rect = self.geometry.to("px", dpi=self.dpi).rect
        page_size = self.geometry.to("px", dpi=self.dpi).size
        print(f"During rendering, page size in pixels at {self.dpi} is {page_size}")
        width = max(1, int(page_rect.width()))
        height = max(1, int(page_rect.height()))

        image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.white)  # or Qt.transparent if preferred

        painter = QPainter(image)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        for row in self.items:
            for slot in row:
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
        for item in self.slots:
            # item.content property invalidates cached image and reloads content if any.
            item.content = None
        self.update()

    def update_slot_content(self, new_template):
        self.content = new_template
        for item in self.slots:
            # item.content property invalidates and reloads content image if any.
            item.content = self.registry.clone(template)
        self.update()

    def whitespace_in_units(self, unit="px"):
        return [v.to(unit, dpi=self._dpi) for v in self._whitespace]

    def invalidate_cache(self):
        for row in self.items:
            for slot in row:
                slot.invalidate_cache()
        self._cache_image = None

    @property
    def slots(self) -> List[LayoutSlot]:
        return [slot for row in self.items for slot in row]

    ### Grid manipulation ###
    def setGrid(self, registry=None, rows=None, columns=None):
        rows = rows or self.rows
        columns = columns or self.columns
        registry = registry or self._registry
        if not self._registry:
            self._registry = registry

        current_rows = len(self.items) if self.items else 0
        current_cols = len(self.items[0]) if self.items and self.items[0] else 0
        target_rows = max(1, rows if rows is not None else current_rows)
        target_cols = max(1, columns if columns is not None else current_cols)

        # Compute per-cell size in inches using current page geometry + whitespace
        t, b, l, r, sx, sy = self.whitespace_in_units(unit="in")
        page_in = self._geometry.to("in", dpi=self._dpi)
        w, h = page_in.size.width(), page_in.size.height()
        avail_width  = max(0, w - l - r - (target_cols - 1) * sx)
        avail_height = max(0, h - t - b - (target_rows - 1) * sy)
        item_width   = (avail_width  / target_cols) if target_cols else 0
        item_height  = (avail_height / target_rows) if target_rows else 0

        # Shrink rows
        while len(self.items) > target_rows:
            row = self.items.pop()
            for item in row:
                if item is not None:
                    registry.deregister(item.pid)
                    if item.scene() is not None and self.scene() is not None:
                        self.scene().removeItem(item)

        # Shrink cols
        for row in self.items:
            while len(row) > target_cols:
                item = row.pop()
                if item is not None:
                    registry.deregister(item.pid)
                    if item.scene() is not None and self.scene() is not None:
                        self.scene().removeItem(item)

        # Expand rows
        while len(self.items) < target_rows:
            self.items.append([None for _ in range(target_cols)])

        # Expand cols
        for row in self.items:
            while len(row) < target_cols:
                row.append(None)

        # Create/update
        for r in range(target_rows):
            for c in range(target_cols):
                x = l + c * (sx + item_width)
                y = t + r * (sy + item_height)
                if self.items[r][c] is not None:
                    slot = self.items[r][c]
                    slot.geometry = UnitStrGeometry(width=item_width, height=item_height, x=x, y=y, unit="in", dpi=self._dpi)
                    slot.update()
                else:
                    slot = registry.create(
                        "ls",
                        geometry=UnitStrGeometry(width=item_width, height=item_height, x=x, y=y, unit="in", dpi=self._dpi),
                        registry=self._registry,
                        row=r,
                        column=c,
                        parent=self
                    )
                    slot.setParentItem(self)
                    self.items[r][c] = slot
                    if slot.scene() is None and self.scene() is not None:
                        self.scene().addItem(slot)

        # One recompute of local pixel poses, cache invalidation and repaint
        self.updateGrid()


    def updateGrid(self) -> None:
        """
        Recompute and apply each slot’s geometry (size + position) based on:
          • self.geometry   – page size & is_landscape
          • self.whitespace - margins, vertical, and horizontal spacing
          • self._rows, self._columns

        Does NOT create or remove slots; only updates existing ones.
        """
        # 1. Gather pixel-values for margins & spacing
        top, bottom, left, right, spacing_x, spacing_y = self.whitespace_in_units(unit="in")
        page_rect = self.geometry.to("in", dpi=self._dpi).rect
        total_w, total_h = page_rect.width(), page_rect.height()

        # 2. Compute available area and per-cell size
        avail_w = total_w - left - right - (self._columns - 1) * spacing_x
        avail_h = total_h - top - bottom - (self._rows    - 1) * spacing_y
        cell_w = max(avail_w / self.columns,  0)
        cell_h = max(avail_h / self.rows,     0)

        # 3. Loop through each slot and assign its new UnitStrGeometry
        for r, row in enumerate(self.items):
            for c, slot in enumerate(row):
                x = left + c * (cell_w + spacing_x)
                y = top  + r * (cell_h + spacing_y)

                # rect is local to the slot; pos is the offset on the page
                new_geom = UnitStrGeometry(width=cell_w, height=cell_h, x=x, y=y, unit="in", dpi=self._dpi)
                slot.geometry = new_geom
                slot.row      = r
                slot.column   = c
                slot.invalidate_cache()   # so that its rendered thumbnail will be rebuilt

                if slot.scene() is None and self.scene() is not None:
                    slot.setParentItem(self)

                px_rect = self.geometry.to("px", dpi=self._dpi).rect
                px_pos = self.geometry.to("px", dpi=self._dpi).pos

        self.update()
        self.template_changed.emit()

    def get_whitespace(self):
        return [m.to(self.unit, dpi=self.dpi) for m in self._whitespace]
        
    def get_item_position(self, row: int, col: int) -> tuple[float, float]:
        item = self.items[row][col]
        return item.geometry.to(self.unit, dpi=self.dpi).pos

    def get_item_size(self, row, col):
        """
        Returns the uniform cell size (width, height) in pixels for all items in the grid.
        """
        item_size = self.items[row][col].geometry.to(self.unit, dpi=self.dpi).size

    def get_item_at_position(self, scene_pos: QPointF) -> Optional["LayoutSlot"]:
        """
        Given a scene-coordinate point, return the LayoutSlot whose rect contains it,
        or None if no item matches.
        """

        for row in range(self.rows):
            for col in range(self.columns):
                item = self.items[row][col]
                rect = item.geometry.to(self.unit, dpi=self.dpi).rect
                pos = item.geometry.to(self.unit, dpi=self.dpi).pos
                x, y = pos.x(), pos.y()
                w, h = rect.width(), rect.height()
                item_rect = QRectF(x, y, w, h)
                if item_rect.contains(scene_pos):
                    return self.items[row][col]

        return None


    def to_dict(self) -> Dict:
        print(f'Serialzing results in content {self.content}')
        items = []
        for row in self.items:
            row_list = []
            for item in row:
                row_list.append(item.to_dict())
            items.append(row_list)
        return {
            "pid": self._pid,
            "name": self._name,
            "page_size": self._page_size,
            "geometry": self._geometry.to_dict(),
            "pagination_policy": self._pagination_policy,
            "rows": self._rows,
            "columns": self._columns,
            "margin_top": self.margin_top.to_dict(),
            "margin_bottom": self.margin_bottom.to_dict(),
            "margin_left": self.margin_left.to_dict(),
            "margin_right": self.margin_right.to_dict(),
            "spacing_x": self.spacing_x.to_dict(),
            "spacing_y": self.spacing_y.to_dict(),
            "is_landscape": self._is_landscape,
            "content": self._content,
            "items": items,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict,
        registry: "ProtoRegistry",
        is_clone: bool = False,
    ) -> "LayoutTemplate":
        """
        Hydrate or clone a LayoutTemplate via the registry.
        """
        pid = resolve_pid("pg") if is_clone else data["pid"]

        inst = cls(
            pid=pid,
            registry=registry,
            pagination_policy=data.get("pagination_policy"),
            name=data.get("name")
        )

        inst._geometry = UnitStrGeometry.from_dict(data["geometry"])
        inst._page_size = data.get("page_size", "custom")
        inst._rows = data.get("rows", 3)
        inst._columns = data.get("columns", 3)
        inst._is_landscape = data.get("is_landscape", False)

        inst._whitespace = [
            UnitStr.from_dict(data["margin_top"]),
            UnitStr.from_dict(data["margin_bottom"]),
            UnitStr.from_dict(data["margin_left"]),
            UnitStr.from_dict(data["margin_right"]),
            UnitStr.from_dict(data["spacing_x"]),
            UnitStr.from_dict(data["spacing_y"]),
        ]
        print("Layout instance created")

        # Correctly handle content deserialization
        inst._content = data.get("content")

        registry.register(inst)
        inst._name = registry.generate_name(inst)
        items = []
        for row in data.get("items"):
            item_row = []
            for idata in row:
                if idata is None:
                    print("[WARNING] Found None in items row during deserialization")
                    continue
                ls = LayoutSlot.from_dict(idata, registry=registry, is_clone=is_clone)
                ls.setParentItem(inst)
                item_row.append(ls)
            items.append(item_row)
        inst.items = items
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
        top_margin, bottom_margin, left_margin, right_margin, spacing_x, spacing_y = self.whitespace_in_units()


        total_w = rect.width() - left_margin - right_margin - spacing_x * (cols - 1)
        total_h = rect.height() - top_margin - bottom_margin - spacing_y * (rows - 1)

        cell_w = total_w / cols if cols > 0 else 0
        cell_h = total_h / rows if rows > 0 else 0

        grid_pen = QPen(Qt.gray, 1, Qt.DashLine)
        painter.setPen(grid_pen)

        # Horizontal grid lines
        for r in range(rows + 1):
            y = rect.top() + top_margin + r * (cell_h + spacing_y) - (spacing_y if r > 0 else 0)
            x_start = rect.left() + left_margin
            x_end = x_start + total_w + spacing_x * (cols - 1)
            painter.drawLine(x_start, y, x_end, y)

        # Vertical grid lines
        for c in range(cols + 1):
            x = rect.left() + left_margin + c * (cell_w + spacing_x) - (spacing_x if c > 0 else 0)
            y_start = rect.top() + top_margin
            y_end = y_start + total_h + spacing_y * (rows - 1)
            painter.drawLine(x, y_start, x, y_end)

    def _change_orientation(self, geom):
        rect = geom.to("px", dpi=self._dpi).rect
        h = rect.width()
        w = rect.height()
        return UnitStrGeometry(width=w, height=h, unit="px", dpi=self._dpi)