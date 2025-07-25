from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Any, Union, TYPE_CHECKING
from enum import Enum, auto
import json

from PySide6.QtWidgets import QGraphicsObject, QGraphicsItem, QStyleOptionGraphicsItem
from PySide6.QtCore import Qt, QRectF, QPointF, QSizeF, QMarginsF, Signal
from PySide6.QtGui import QPainter, QPixmap, QColor, QImage, QPen, QBrush,  QPageLayout

from prototypyside.models.layout_slot import LayoutSlot
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.ustr_helpers import geometry_with_px_rect, geometry_with_px_pos
from prototypyside.config import PAGE_SIZES, DISPLAY_MODE_FLAGS, PAGE_UNITS
from prototypyside.utils.proto_helpers import get_prefix, resolve_pid
from prototypyside.services.pagination.page_manager import PRINT_POLICIES, PAGE_SIZES
from prototypyside.models.component_template import ComponentTemplate
if TYPE_CHECKING:
    from prototypyside.services.proto_registry import ProtoRegistry




class LayoutTemplate(QGraphicsObject):
    template_changed = Signal()
    marginsChanged = Signal()
    spacingChanged = Signal()
    orientationChanged = Signal()
    def __init__(self, pid, registry, name=None, pagination_policy='Letter: 3x3 Standard Cards (2.5"x3.5")', parent=None):
        super().__init__(parent)
        self._pid = pid
        self._registry = registry
        self._name = name
        self._pagination_policy = pagination_policy
        print(f"Policy is {self._pagination_policy}, DETAILS:\n{PRINT_POLICIES.get(self._pagination_policy)}")
        #### All of these are set from PRINT_POLICIES
        pol = PRINT_POLICIES.get(pagination_policy)
        self._rows = pol.get("rows")
        self._columns = pol.get("columns")
        self._page_size = pol.get("page_size")
        self._geometry = PAGE_SIZES.get(self._page_size)
        self._whitespace = pol.get("whitespace")# ordered [top, bottom, left, right, spacing_x, spacing_y]
        self._orientation = pol.get("orientation")
        self.lock_at: int = pol.get("lock_at") # The number of components a given policy will accept.
        ####

        self._dpi = 300
        self._unit = "px"
        self._content = None
        self.items = []
        self.setAcceptHoverEvents(True)

        self.set_policy_props(pagination_policy)

    def set_policy_props(self, policy):
        if policy in PRINT_POLICIES:
            for prop, value in PRINT_POLICIES.get(policy).items():
                fprop = f"_{prop}"
                if hasattr(self, prop):
                    setattr(self, prop, value)

    @property
    def pagination_policy(self):
        return self._pagination_policy
    
    @pagination_policy.setter
    def pagination_policy(self, pol):
        if pol != self._pagination_policy and pol in PRINT_POLICIES:
            self._pagination_policy = pol
            self._rows = pol.get("rows")
            self._columns = pol.get("columns")
            self._geometry = pol.get("geometry")
            self._whitespace = pol.get("whitespace")# ordered [top, bottom, left, right, spacing_x, spacing_y]
            self._orientation = pol.get("orientation")
            self.lock_at: int = pol.get("lock_at") # The number of components a given policy will accept.
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

    def geometry_to_page_size(self, value, orientation):
        geom = PAGE_SIZES[value].get("geometry").to(self.unit, dpi=self.dpi)

    @property
    def dpi(self) -> int:
        return self._dpi

    @dpi.setter
    def dpi(self, new: int):
        if self._dpi != new:
            self._dpi = new
            for item in self.items:
                item.dpi = self._dpi

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

        # block the itemChange override
        self.blockSignals(True)
        super().setPos(self._geometry.to(self.unit, dpi=self.dpi).pos)
        self.blockSignals(False)

    def boundingRect(self) -> QRectF: 
        return self._geometry.to(self.unit, dpi=self.dpi).rect

    def setRect(self, new_rect: QRectF):
        self.prepareGeometryChange()
        self.geometry = geometry_with_px_rect(self._geometry, new_rect)
        self.update()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        if change == QGraphicsItem.ItemPositionChange:
            self._geometry = geometry_with_px_pos(self._geometry, value)
        return super().itemChange(change, value)
   
    @property
    def page_size(self):
       return self._page_size
        
    @page_size.setter
    def page_size(self, key):
        if key != self._page_size and key != "custom" and key in PAGE_SIZES: #custom not implemented
            self._page_size = key
            self.geometry = PAGE_SIZES[key].get("geometry").to(self.unit, dpi=self.dpi)

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
    def orientation(self) -> bool:
        return self._orientation

    @orientation.setter
    def orientation(self, value: bool):
        if value != self._orientation:
            self._orientation = value
            new_h = self._geometry.width
            new_w = self._geometry.height
            new_r = self._columns
            new_c = self._rows
            self.grid = (new_r, new_c)
            self.geometry=UnitStrGeometry(width=new_w, height=new_h)
            self.updateGrid()
            self.scene().setSceneRect(self.boundingRect())
            self.scene().views()[0].fitInView(self.boundingRect(), Qt.KeepAspectRatio)

            self.template_changed.emit()

    @property
    def image(self) -> QImage:
        if not hasattr(self, "_cache_image") or self._cache_image is None:
            self._cache_image = self._render_to_image(dpi=self.dpi, unit=self.unit)
        return self._cache_image

    def _render_to_image(self, dpi=300, unit="in") -> QImage:
        """
        Renders the entire layout page to a single QImage by compositing pre-rendered slot images.
        
        Assumes each slot has a .geometry and .image property.
        """

        # Calculate full page size in pixels
        page_rect = self.geometry.to("px", dpi=dpi).rect
        width = max(1, int(page_rect.width()))
        height = max(1, int(page_rect.height()))

        image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        image.setDotsPerInch(dpi)
        image.fill(Qt.white)  # or Qt.transparent if preferred

        painter = QPainter(image)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        for row in self.items:
            for slot in row:
                if slot.content:
                    slot_img = slot.image  # Cached slot image
                    if isinstance(slot_img, QImage):
                        target_rect = slot.geometry.to("px", dpi=dpi).rect
                        painter.drawImage(target_rect, slot_img)

        painter.end()
        return image

    clear_slot_content(self):
        for item in self.slots:
            # item.content property invalidates cached image and reloads content if any.
            item.content = None
        self.update()

    update_slot_content(self, new_template):
        self.content = new_template
        for item in self.slots:
            # item.content property invalidates and reloads content image if any.
            item.content = self.registry.clone(template)
        self.update()

    # ---- Margins and Grid Spacing ---- #
    @property
    def margins(self) -> List[UnitStr]: return self._whitespace[:4]

    @margins.setter
    def margins(self, new_margins: List[UnitStr]):
        if new_margins != self._whitespace[:4] and len(new_margins) == 4:
            spacing = self._whitespace[4:]
            self._whitespace = new_margins + spacing
        self.updateGrid()
        self.marginsChanged.emit()

    @property
    def margin_top(self):
        return self._whitespace[0]

    @margin_top.setter
    def margin_top(self, ustr: UnitStr):
        self._whitespace[0] = ustr
        self.updateGrid()
        self.marginsChanged.emit()

    @property
    def margin_bottom(self):
        return self._whitespace[1]

    @margin_bottom.setter 
    def margin_bottom(self, ustr: UnitStr):
        self._whitespace[1] = ustr
        self.updateGrid()
        self.marginsChanged.emit()

    @property
    def margin_left(self):
        return self._whitespace[2]

    @margin_left.setter
    def margin_left(self, ustr: UnitStr):
        self._whitespace[2] = ustr
        self.updateGrid()
        self.marginsChanged.emit()

    @property
    def margin_right(self):
        return self._whitespace[3]

    @margin_right.setter
    def margin_right(self, ustr: UnitStr):
        self.margins[3] = ustr
        self.updateGrid()
        self.marginsChanged.emit()

    @property
    def spacing_x(self):
        return self._whitespace[4]

    @spacing_x.setter
    def spacing_x(self, ustr: UnitStr):
        self._whitespace[4] = ustr
        self.updateGrid()
        self.spacingChanged.emit()

    @property
    def spacing_y(self):
        return self._whitespace[5]

    @spacing_y.setter
    def spacing_y(self, ustr: UnitStr):
        self._whitespace[5] = ustr
        self.updateGrid()
        self.spacingChanged.emit()

    @property
    def whitespace(self) -> List[UnitStr]:
        return self._whitespace

    @whitespace.setter
    def whitespace(self, value: Union[List[Any], Dict[str, Any]]):
        """
        Flexible setter:
        - Accepts a full list of 6 values
        - OR a dictionary like {'margin_top': '0.25in', 'spacing_x': '3mm'}
        """
        label_to_index = {
            "margin_top": 0,
            "margin_bottom": 1,
            "margin_left": 2,
            "margin_right": 3,
            "spacing_x": 4,
            "spacing_y": 5,
        }

        changed = False
        if isinstance(value, (list, tuple)) and len(value) == 6:
            new_ws = []
            for old, new in zip(self._whitespace, value):
                if new is None:
                    new_ws.append(old)
                else:
                    new_ws.append(UnitStr(new, dpi=self.dpi))
            if new_ws != self._whitespace:
                self._whitespace = new_ws
                changed = True

        elif isinstance(value, dict):
            for key, index in label_to_index.items():
                if key in value:
                    new_val = UnitStr(value[key], dpi=self.dpi)
                    if self._whitespace[index] != new_val:
                        self._whitespace[index] = new_val
                        changed = True
        if changed:
            self.updateGrid()
            self.marginsChanged.emit()


    def whitespace_in_units(self, unit="px", dpi=300):
        return [v.to(unit, dpi=dpi) for v in self._whitespace]

    def invalidate_cache(self):
        for row in self.items:
            for slot in row:
                slot.invalidate_cache()
    @property
    def slots(self) -> List[LayoutSlot]:
        return [slot for row in self.items for slot in row]

    ### Grid manipulation ###
    def setGrid(self, registry=None, rows=None, columns=None):
        """
        Expands or shrinks the items grid to match (rows, columns).
        Handles creation, updating, and deregistration of items as needed.
        """
        # -- 1. Determine new grid size --
        rows = rows or self.rows
        columns = columns or self.columns
        registry = registry or self._registry
        if not self._registry:
            self._registry = registry
        current_rows = len(self.items) if self.items else 0
        current_cols = len(self.items[0]) if self.items and self.items[0] else 0
        target_rows = rows if rows is not None else current_rows
        target_cols = columns if columns is not None else current_cols
        # print(f"[LAYOUT_TEMPLATE] From setGrid: Setting grid to rows and columns: {target_rows},{target_cols}")
        if target_rows < 1 or target_cols < 1:
            return  # Nothing to do
        t, b, l, r, sx, sy = self.whitespace_in_units(unit="in")
        w, h = self._geometry.inch.size.width(), self._geometry.inch.size.height()

        avail_width = w - l - r - (target_cols - 1) * sx
        avail_height = h - t - b - (target_rows - 1) * sy
        item_width = max(avail_width / target_cols, 0)
        item_height = max(avail_height / target_rows, 0)
        # -- 2. Shrink rows if needed --
        while len(self.items) > target_rows:
            row = self.items.pop()
            for item in row:
                if item is not None:
                    registry.deregister(item.pid)
                    if item.scene() is not None:
                        self.scene().removeItem(item)
        # -- 3. Shrink columns in each row if needed --
        for row in self.items:
            while len(row) > target_cols:
                item = row.pop()
                if item is not None:
                    registry.deregister(item.pid)
                    if item.scene() is not None:
                        self.scene().removeItem(item)
        # -- 4. Expand rows if needed --
        while len(self.items) < target_rows:
            self.items.append([None for _ in range(target_cols)])
        # -- 5. Expand columns in each row if needed --
        for row in self.items:
            while len(row) < target_cols:
                row.append(None)
        # -- 6. Create/update all items in the new grid --
        for r in range(target_rows):
            for c in range(target_cols):
                item = self.items[r][c]
                # Calculate position for this slot
                x = l + c * (sx + item_width)
                y = t + r * (sy + item_height)
                rect = QRectF(0, 0, item_width, item_height)
                pos = QPointF(x, y)
                if item is not None:
                    item.geometry = UnitStrGeometry(width=item_width, height=item_height, x=x, y=y, unit="in", dpi=self._dpi)
                    item.update()
                else:
                    # Create new item and add to scene
                    item = registry.create(
                        "ls",
                        geometry=UnitStrGeometry(width=item_width, height=item_height, x=x, y=y, unit="in", dpi=self._dpi),
                        registry= self._registry,
                        row=r,
                        column=c,
                        parent=self
                    )
                    item.setParentItem(self)
                    print(f"USG.rect for Slot {r}, {c} in pixels {item.geometry.px.rect}")
                    self.items[r][c] = item
                    if item.scene() is None:
                        self.scene().addItem(item)
                    item.update()
        # Update the template's row and column counts

    def updateGrid(self) -> None:
        """
        Recompute and apply each slot’s geometry (size + position) based on:
          • self.geometry   – page size & orientation
          • self.margins    – top, bottom, left, right
          • self.spacing_x  – horizontal gutter
          • self.spacing_y  – vertical gutter
          • self._rows, self._columns

        Does NOT create or remove slots; only updates existing ones.
        """
        # 1. Gather pixel-values for margins & spacing
        top, bottom, left, right, spacing_x, spacing_y = self.whitespace_in_units(unit="in")
        page_rect = self.geometry.inch.rect
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
                # apply it
                slot.geometry = new_geom
                slot.row      = r
                slot.column   = c
                slot.invalidate_cache()   # so that its rendered thumbnail will be rebuilt

                if slot.scene() is None and self.scene() is not None:
                    slot.setParentItem(self)
                    self.scene().addItem(slot)
                print(f"From updateGrid, slot {r},{c}: {new_geom}\nslot is in scene? {True if slot.scene() else False}")
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
            "orientation": self._orientation,
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
        inst._orientation = data.get("orientation", False)

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
        unit : str, default "px"
            The logical unit system (e.g., 'in', 'mm', 'px') to scale layout to.
        dpi : int, default 300
            DPI used for converting units to pixels.
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

    def _applyOrientation(self):
        base = self._geometry

        r = base.to(self.unit, dpi=self.dpi).rect
        w, h = r.width(), r.height()
        if self._orientation:
            r = QRectF(0, 0, h, w)
        else:
            r = QRectF(0, 0, w, h)

        # build a new UnitStrGeometry from that pixel rect
        rotated = UnitStrGeometry.from_px(rect=r, pos=QPointF(0, 0), dpi=self._dpi)
        # shove it back through the setter (this will re-sync page_size if needed)
        self.geometry = rotated