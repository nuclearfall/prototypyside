from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Any, TYPE_CHECKING
from enum import Enum, auto
import json
from PySide6.QtWidgets import QGraphicsObject, QGraphicsItem, QStyleOptionGraphicsItem
from PySide6.QtCore import Qt, QRectF, QPointF, QSizeF, QMarginsF, Signal
from PySide6.QtGui import QPainter, QPixmap, QColor, QImage, QPen, QBrush,  QPageLayout, QPageSize
from prototypyside.models.component_template import ComponentTemplate
from prototypyside.models.component_elements import ImageElement
from prototypyside.utils.unit_converter import to_px, page_in_px, page_in_units, compute_scale_factor
from prototypyside.utils.unit_str import UnitStr
from prototypyside.utils.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.ustr_helpers import geometry_with_px_rect, geometry_with_px_pos
from prototypyside.config import PAGE_SIZES, DISPLAY_MODE_FLAGS, PAGE_UNITS
from prototypyside.utils.proto_helpers import get_prefix, issue_pid
if TYPE_CHECKING:
    from prototypyside.services.proto_registry import ProtoRegistry




class LayoutSlot(QGraphicsObject):
    item_changed = Signal()
    def __init__(self, pid, geometry=None, row=3, column=3, parent=None):
        super().__init__(parent)
        self._pid = pid
        self._template_pid = None # This will hold a reference to the template which will be instanced to fill it.
        self._hovered = False
        self._geometry = geometry
        self._row = row
        self._column = column
        self._content = None
        self._unit = "px"
        self._dpi = 144
        self._display_flag = DISPLAY_MODE_FLAGS.get("stretch").get("aspect")
        self._cache_image = None
        if geometry is None:
            # initGrid, doesn't set position. Once we have a scene we'll setGrid
            self._geometry = UnitStrGeometry(width="0.25in", height="0.25in", dpi=self._dpi)
        self.setAcceptHoverEvents(True)

    # --- Geometric Property Getter/Setters ---#
    @property
    def dpi(self) -> int:
        return self._dpi

    @dpi.setter
    def dpi(self, new: int):
        if self._dpi != new:
            self._dpi = new
            for item in self.content:
                item.dpi = new

    @property
    def unit(self) -> str:
        return self._unit

    @unit.setter
    def unit(self, new: str):
        if self._unit != new:
            self._unit = new
            for item in self.content:
                item.unit = new

    @property
    def geometry(self):
        return self._geometry

    @geometry.setter
    def geometry(self, new_geom: UnitStrGeometry):
        if self._geometry == new_geom:
            return
        self.prepareGeometryChange()
        self._geometry = new_geom
        super().setPos(self._geometry.to(self.unit, dpi=self.dpi).pos)
        self.update()

    def boundingRect(self) -> QRectF:
        return self._geometry.to(self.unit, dpi=self.dpi).rect

    # This method is for when ONLY the rectangle (size) changes,
    # not the position.
    def setRect(self, new_rect: QRectF):
        if self._geometry.to(self.unit, dpi=self.dpi).rect == new_rect:
            return
        self.prepareGeometryChange()
        geometry_with_px_rect(self._geometry, new_rect)
        # self.update()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        # This is called when the scene moves the item.
        if change == QGraphicsItem.ItemPositionChange and value != self.pos():
            # Block signals to prevent a recursive loop if a connected item
            # also tries to set the position.
            signals_blocked = self.signalsBlocked()
            self.blockSignals(True)
            geometry_with_px_pos(self._geometry, value)
            print(f"[ITEMCHANGE] Called with change={change}, value={value}")
            print(f"[ITEMCHANGE] Geometry.pos updated to: {self._geometry.to(self.unit, dpi=self.dpi).pos}")
            self.blockSignals(signals_blocked)

        # It's crucial to call the base class implementation. This will update geometry.
        # If other signals are emitted or updates called for, it breaks the undo stack.
        return super().itemChange(change, value)

    # --- Addiontal Property Getter/Setters ---#
    @property
    def pid(self) -> str:
        return self._pid

    @pid.setter
    def pid(self, value):
        self._pid = value

    @property
    def template_pid(self) -> str: return self._template_pid

    def template_pid(self, value):
        if self._template_pid != value:
            self._template_pid = value
            self.template_changed.emit()

    @property
    def row(self): return self._row

    @row.setter
    def row(self, new):
        if new != self._row:
            self._row = new
            self.item_changed.emit()

    @property
    def column(self): return self._column

    @column.setter
    def column(self, new):
        if new != self._column:
            self._column = new
            self.item_changed.emit()

    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, obj):
        self._content = obj

        ### Next 4 lines are DEBUGGING ONLY 
        geometry = self.geometry if isinstance(self._content, ComponentTemplate) else None
        if geometry:
            print(f"Slot {self._pid} has content sized: {geometry.rect.width()}x{geometry.rect.height()}")
        # print(f"Slot content items are {self._content.items}")

        self.update()

    @property 
    def display_flag(self):
        return self._display_flag

    @display_flag.setter
    def display_flag(self, qflag):
        if qflag != self._display_flag:
            self._display_flag = qflag

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()

    def paint(self, painter, option, widget=None):
        """
        Paints the layout slot including its border, hover state, and rendered content
        (if any). The rendered content is drawn using unit-scaled QImage.

        Parameters:
            painter: QPainter used by the scene or exporter
            option: QStyleOptionGraphicsItem from the scene
            widget: Optional widget context (unused)
            unit (str): 'px', 'in', 'mm', etc.
            dpi (int): Dots-per-inch used for physical unit conversion
        """
        rect = self.geometry.to(self.unit, dpi=self.dpi).rect

        # --- Base fill and border ---
        fill = QBrush(QColor(230, 230, 230, 80))
        border = QPen(QColor(80, 80, 80), 1)
        painter.setPen(border)
        painter.setBrush(fill)
        painter.drawRect(rect)

        # --- Hover overlay ---
        if self._hovered:
            painter.setBrush(QBrush(QColor(70, 120, 240, 120)))
            painter.setPen(Qt.NoPen)
            painter.drawRect(rect)

        # --- Placeholder if no content ---
        if self._content is None:
            pen = QPen(QColor(100, 100, 100, 120), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)
            return

        # --- Content rendering ---
        if self._cache_image is None:
            self._cache_image = self._render_to_image()

        painter.drawImage(rect, self._cache_image)


    def _render_to_image(self):
        """
        Renders the content (ComponentTemplate) of this slot to an offscreen image.

        This image is DPI-aware and scaled based on the logical unit.
        """
        rect = self.geometry.to(self.unit, dpi=self.dpi).rect
        # The value has to be greater than 0 but can't be 1 if we're dealing with physical units
        w, h = max(.01, int(rect.width())), max(.01, int(rect.height()))

        option = QStyleOptionGraphicsItem()
        image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)

        img_painter = QPainter(image)
        img_painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        # Align drawing to image origin
        img_painter.translate(-rect.topLeft())

        # Render template background + border

        self._content.paint(img_painter, option)

        # Render elements in z-order
        for item in sorted(self._content.items, key=lambda e: e.zValue()):
            img_painter.save()
            img_painter.translate(item.pos())

            item_bounds = item.boundingRect()
            img_painter.setClipRect(QRectF(0, 0, item_bounds.width(), item_bounds.height()))

            rotation = getattr(item, "rotation", lambda: 0)()
            if rotation:
                img_painter.rotate(rotation)

            item.paint(img_painter, option, widget=None)
            img_painter.restore()

        return image


    def _render_items(self, painter: QPainter) -> None:
        """
        Paints every item inside this slot's content template onto the given QPainter.

        - The painter is assumed to be pre-scaled for physical units (e.g., 1 inch = dpi pixels).
        - All geometry values should be used in logical units (from `UnitStrGeometry.to(self.unit, dpi)`).
        - Items are drawn in z-order (lowest to highest).
        - Each item's own `paint(...)` method is reused to support custom rendering.

        Parameters
        ----------
        painter : QPainter
            A painter already set up and scaled to match the target export resolution.
        unit : str
            The logical unit system (e.g., 'px', 'in', 'mm'). Used for size/position.
        dpi : int
            The dots-per-inch to convert units into physical pixels.
        """
        option = QStyleOptionGraphicsItem()

        # Draw background/border of template itself
        self._content.paint(painter, option, widget=None)

        # Draw each item in z-order
        for item in sorted(self._content.items, key=lambda e: e.zValue()):
            painter.save()

            # Logical position of the item in the template
            pos = item.geometry.to(self.unit, dpi=self.dpi).pos
            painter.translate(pos.x(), pos.y())

            # Optional rotation
            rotation = getattr(item, "rotation", lambda: 0)()
            if rotation:
                painter.rotate(rotation)

            # Delegate to the item's own unit-aware paint method
            item.paint(painter, option, widget=None)

            painter.restore()

    def _render_background(self, painter: QPainter):
        """
        Draw the background color or image for this slot's content template.

        Parameters
        ----------
        painter : QPainter
            A QPainter instance already aligned with the page coordinate system.
        unit : str
            Logical unit system (e.g., 'px', 'in', 'mm') for resolution conversion.
        dpi : int
            Dots-per-inch to convert unit-based geometry to physical pixels.
        """
        rect = self.geometry.to(self.unit, dpi=self.dpi).rect

        bg_color = getattr(self._content, "background_color", None)
        bg_image_path = getattr(self._content, "background_image", None)

        if bg_color:
            painter.fillRect(rect, QColor(bg_color))

        if bg_image_path:
            pixmap = QPixmap(bg_image_path)
            if not pixmap.isNull():
                painter.drawPixmap(rect, pixmap, pixmap.rect())

    def invalidate_cache(self):
        self._cache_image = None
        self.update()

    def merge_csv_row(self):
        """
        Updates items with values from csv_row, only if their name is a data binding.
        If the item already has static content, it is left unchanged unless overridden by csv data.
        """
        for item in self._content.items:
            if item.name.startswith("@"):
                col = item.name
                if col in csv_row:
                    value = csv_row[col]
                    setattr(item, "content", value)

    def apply_data(self, row):
        for item in self._content.items:
            if hasattr(item, "update_from_merge_data"):
                item.update_from_merge_data(row)
        self.invalidate_cache()

    def to_dict(self):
        return {
            "pid": self._pid,
            "geometry": self._geometry.to_dict(),
            "row": self._row,
            "column": self._column,
            # "content": self._content.to_dict() if self._content else None
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        registry: "ProtoRegistry",
        is_clone: bool = False
    ) -> "LayoutSlot":
        """
        Hydrate or clone a LayoutSlot. Regenerates pid on clone,
        restores geometry, flags, and re‐registers in the registry.
        """
        # 1) PID logic
        original_pid = data["pid"]
        prefix = get_prefix(original_pid)
        pid = issue_pid(prefix) if is_clone else original_pid

        # 2) Geometry
        geom = UnitStrGeometry.from_dict(data["geometry"])
        pos = QPointF(geom.pos_x.px, geom.pos_y.px)

        # 3) Instantiate
        inst = cls(pid=pid,
                   geometry=geom,
                   row=data.get("row", 3),
                   column=data.get("column", 3),
                   parent=None)
        inst.setPos(pos)

        # 4) Restore any display flags, cached images, etc.
        inst._hovered = data.get("hovered", False)
        inst._display_flag = data.get("display_flag", inst._display_flag)

        # 5) Wire registry & register
        inst._registry = registry
        registry.register(inst)

        return inst

class LayoutTemplate(QGraphicsObject):
    template_changed = Signal()
    marginsChanged = Signal()
    spacingChanged = Signal()
    orientationChanged = Signal()
    export_quantity: Optional[int] = None     # Override for copies per item
    def __init__(self, pid, parent=None, registry = None,
                page_size = "letter", geometry=None,
                pagination_policy="InterleaveDatasets",
                rows=3, columns=3, dpi=144,
                name=None, margin_top=UnitStr("0.5in"), margin_bottom = UnitStr("0.5in"),
                margin_left = UnitStr("0.5in"), margin_right = UnitStr("0.5in"),
                spacing_x = UnitStr("0.0in"), spacing_y  = UnitStr("0.0in"), orientation=False):
        super().__init__(parent)
        self._pid = pid
        self._name = name
        self._content = []
        self._page_size = page_size
        self._registry = registry
        self._geometry = PAGE_SIZES[page_size]["geometry"] or UnitStrGeometry(width="8.5in", height="11in")
        self._dpi = 144
        self._unit = "px"
        self.pagination_policy = pagination_policy
        self._rows = rows
        self._columns = columns
        self._margins = [UnitStr(m, dpi=self._dpi) for m in (margin_top, margin_bottom, margin_left, margin_right)]
        self._spacing = [UnitStr(s, dpi=self._dpi) for s in (spacing_x, spacing_y)]
        self._orientation = orientation
        self.items = self.initGrid(self._registry, rows=self._rows, columns=self._columns)

    @property
    def content(self):
        return self.get_template()

    def add_template(self, template):
        self._content.append(template)
        return template

    def remove_template(
        self,
        index:        Optional[int]    = None,
        template_pid: Optional[str]    = None,
        first:        bool             = False,
        last:         bool             = True
    ) -> Optional[ComponentTemplate]:
        """
        Remove and return an item from self.content by:
          1. template_pid – if provided, pop the first item whose .pid matches
          2. index        – if provided and in‐range
          3. first        – if True, pop at 0
          4. last         – if True (default), pop at -1

        Returns the removed item, or None if no match / empty content.
        """
        # nothing to remove
        if not self._content:
            return None

        # 1) PID lookup
        if template_pid is not None:
            for i, item in enumerate(self._content):
                if getattr(item, "pid", None) == template_pid:
                    return self.content.pop(i)
            return None

        # 2) Index lookup
        if index is not None:
            if 0 <= index < len(self._content):
                return self.content.pop(index)
            return None

        # 3) First?
        if first:
            return self._content.pop(0)

        # 4) Last?
        if last:
            return self._content.pop(-1)

        return None

    def get_template(
        self,
        index: Optional[int] = None,
        pid:   Optional[str] = None,
        first: bool = False,
        last:  bool = True
    ) -> Optional[ComponentTemplate]:
        """
        Retrieve an item from self.content by:
          1. pid  — if provided, return the first item whose `.pid` matches
          2. index — if provided and in‐range
          3. first — if True, returns self.content[0]
          4. last  — if True (default), returns self.content[-1]

        Returns None if no match or content is empty.
        """
        # nothing to do if empty
        if not self._content:
            return None

        # 1) PID lookup
        if pid is not None:
            for item in self._content:
                if getattr(item, "pid", None) == pid:
                    return item
            return None

        # 2) Index lookup
        if index is not None:
            if 0 <= index < len(self._content):
                return self._content[index]
            return None

        # 3) First?
        if first:
            return self._content[0]

        # 4) Last?
        if last:
            return self._content[-1]

        return None


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
        super().setPos(self._geometry.to(self.unit, dpi=self.dpi).pos)


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
        self.setGrid(self._registry, self.rows, self.columns)

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


    # ---- Margins and Grid Spacing ---- #
    @property
    def margins(self) -> List[UnitStr]: return self._margins

    @margins.setter
    def margins(self, new_margins: List[UnitStr]):
        self._margins = new_margins
        self.updateGrid()
        self.marginsChanged.emit()

    @property
    def margin_top(self):
        return self._margins[0]

    @margin_top.setter
    def margin_top(self, ustr: UnitStr):
        self._margins[0] = ustr
        self.updateGrid()
        self.marginsChanged.emit()

    @property
    def margin_bottom(self):
        return self._margins[1]

    @margin_bottom.setter 
    def margin_bottom(self, ustr: UnitStr):
        self._margins[1] = ustr
        self.updateGrid()
        self.marginsChanged.emit()

    @property
    def margin_left(self):
        return self._margins[2]

    @margin_left.setter
    def margin_left(self, ustr: UnitStr):
        self._margins[2] = ustr
        self.updateGrid()
        self.marginsChanged.emit()

    @property
    def margin_right(self):
        return self._margins[3]

    @margin_right.setter
    def margin_right(self, ustr: UnitStr):
        self.margins[3] = ustr
        self.updateGrid()
        self.marginsChanged.emit()

    @property
    def spacing_x(self):
        return self._spacing[0]

    @spacing_x.setter
    def spacing_x(self, ustr: UnitStr):
        self._spacing[0] = ustr
        self.updateGrid()
        self.spacingChanged.emit()

    @property
    def spacing_y(self):
        return self._spacing[1]

    @spacing_y.setter
    def spacing_y(self, ustr: UnitStr):
        self._spacing[1] = ustr
        self.updateGrid()
        self.spacingChanged.emit()

    def get_whitespace(self):
        return [w.to(self.unit, dpi=self.dpi) for w in self._margins + self._spacing]

    def invalidate_cache(self):
        for row in self.items:
            for slot in row:
                slot.invalidate_cache()

    def initGrid(self, registry=None, rows=None, columns=None):
        registry = registry or self.registry
        # fall back to instance defaults only if caller passed None
        if rows is None:
            rows = self._rows
        if columns is None:
            columns = self._columns

        # build a list of `rows` lists, each containing `columns` LayoutSlot instances
        self.items = [
            [
                registry.create(
                    'ls',        # your LayoutSlot proto-prefix
                    parent=self
                )
                for c in range(columns)
            ]
            for r in range(rows)
        ]

        return self.items

    ### Grid manipulation ###
    def setGrid(self, registry=None, rows=None, columns=None):
        """
        Expands or shrinks the items grid to match (rows, columns).
        Handles creation, updating, and deregistration of items as needed.
        """
        # -- 1. Determine new grid size --
        registry = registry or self._regsitry
        if not self._registry:
            self._registry = registry
        current_rows = len(self.items) if self.items else 0
        current_cols = len(self.items[0]) if self.items and self.items[0] else 0
        target_rows = rows if rows is not None else current_rows
        target_cols = columns if columns is not None else current_cols
        # print(f"[LAYOUT_TEMPLATE] From setGrid: Setting grid to rows and columns: {target_rows},{target_cols}")
        if target_rows < 1 or target_cols < 1:
            return  # Nothing to do
        # Precompute the slot dimensions and positions for the new grid
        t, b, l, r, sx, sy = self.get_whitespace()  # px
        w, h = self._geometry.to(self.unit, dpi=self.dpi).size.width(), self._geometry.to(self.unit, dpi=self.dpi).size.height()
        avail_width = w - l - r - (target_cols - 1) * sx
        avail_height = h - t - b - (target_rows - 1) * sy
        item_width_px = max(avail_width / target_cols, 0)
        item_height_px = max(avail_height / target_rows, 0)
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
                x_px = l + c * (sx + item_width_px)
                y_px = t + r * (sy + item_height_px)
                rect = QRectF(0, 0, item_width_px, item_height_px)
                pos = QPointF(x_px, y_px)
                if item is not None:
                    # Update existing item
                    item.geometry = UnitStrGeometry(rect=rect, pos=pos, dpi=self._dpi)
                    item.update()
                else:
                    # Create new item and add to scene
                    item = registry.create(
                        "ls",
                        geometry=UnitStrGeometry.from_px(rect=rect, pos=pos, dpi=self._dpi),
                        row=r,
                        column=c,
                        parent=self,
                    )
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
        top_px, bottom_px, left_px, right_px, spacing_x_px, spacing_y_px = self.get_whitespace()
        page_rect = self.geometry.to(self.unit, dpi=self.dpi).rect
        total_w, total_h = page_rect.width(), page_rect.height()

        # 2. Compute available area and per-cell size
        avail_w = total_w - left_px - right_px - (self._columns - 1) * spacing_x_px
        avail_h = total_h - top_px - bottom_px - (self._rows    - 1) * spacing_y_px
        cell_w = max(avail_w / self.columns,  0)
        cell_h = max(avail_h / self.rows,     0)

        # 3. Loop through each slot and assign its new UnitStrGeometry
        for r, row in enumerate(self.items):
            for c, slot in enumerate(row):
                x = left_px + c * (cell_w + spacing_x_px)
                y = top_px  + r * (cell_h + spacing_y_px)

                # rect is local to the slot; pos is the offset on the page
                rect = QRectF(0, 0, cell_w, cell_h)
                pos  = QPointF(x, y)
                new_geom = UnitStrGeometry.from_px(rect=rect, pos=pos, dpi=self.dpi)

                # apply it
                slot.geometry = new_geom
                slot.row      = r
                slot.column   = c
                slot.invalidate_cache()   # so that its rendered thumbnail will be rebuilt

        # 4. Redraw the page and notify listeners
        self.update()
        self.template_changed.emit()

    def compute_item_size(self, rows, cols):
        """
        Returns item_width, item_height in **pixels** for the given grid position.
        Slot sizes are based on page size, margins, spacing, and grid size.
        """
        t, b, l, r, sx, sy = self.get_whitespace()  # Each is a float (pixels)
        w, h = self._geometry.to(self.unit, dpi=self.dpi).size.width(), self._geometry.to(self.unit, dpi=self.dpi).size.height()

        cols = self._columns
        rows = self._rows

        if cols < 1 or rows < 1:
            return 0, 0

        avail_width = w - l - r - (cols - 1) * sx
        avail_height = h - t - b - (rows - 1) * sy

        item_width_px = max(avail_width / cols, 0)
        item_height_px = max(avail_height / rows, 0)

        # Debug
        # print(f"compute_item_size: avail_width={avail_width}, cols={cols}, item_width_px={item_width_px}")
        # print(f"compute_item_size: avail_height={avail_height}, rows={rows}, item_height_px={item_height_px}")

        return item_width_px, item_height_px

    def compute_item_position(self, row, col, total_rows, total_cols):
        t, b, l, r, sx, sy = self.get_whitespace()
        item_w, item_h = self.compute_item_size(row, col, total_rows, total_cols)
        return (
            l + col * (item_w + sx),
            t + row * (item_h + sy)
        )

    def get_margins(self):
        return [m.to(self.unit, dpi=self.dpi) for m in self._margins]
        
    def get_item_position(self, row: int, col: int) -> tuple[float, float]:
        item = self.items[row][col]
        return item.geometry.to(self.unit, dpi=self.dpi).pos

    def get_item_size(self, row, col):
        """
        Returns the uniform cell size (width, height) in pixels for all items in the grid.
        """
        item_size = self.items[row][col].geometry.to(self.unit, dpi=self.dpi).size

    def get_item_at_position(self, scene_pos: QPointF) -> Optional[LayoutSlot]:
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
        # items = [[item.to_dict() for item in row] for row in self.items]
        content = []
        if self._content:
            for c in self._content:
                if isinstance(c, ComponentTemplate):
                    content.append(c.to_dict())
        return {
            "pid": self._pid,
            "name": self._name,
            "page_size": self._page_size,
            "geometry": self._geometry.to_dict(),
            "pagination_policy": self.pagination_policy,
            "rows": self._rows,
            "columns": self._columns,
            "margin_top": self.margin_top.to_dict(),
            "margin_bottom": self.margin_bottom.to_dict(),
            "margin_left": self.margin_left.to_dict(),
            "margin_right": self.margin_right.to_dict(),
            "spacing_x": self.spacing_x.to_dict(),
            "spacing_y": self.spacing_y.to_dict(),
            "orientation": self._orientation,
            "content": content,
            #"items": items,
        }


    @classmethod
    def from_dict(
        cls,
        data: dict,
        registry: "ProtoRegistry",
        is_clone: bool = False
    ) -> "LayoutTemplate":
        """
        Hydrate or clone a LayoutTemplate via the registry.
        """
        # 1) Hydrate the content (ComponentTemplates)
        registry = registry or self._registry
        content: list[ComponentTemplate] = []
        # print (f"Attempting to rehydrate contents {data.get("content")}")
        for cdata in data.get("content", []):
            comp = registry.from_dict(
                cdata,
                registry=registry,
                is_clone=is_clone
            )
            content.append(comp)
            
        # 2) Determine PID (new one for clones)
        pid = issue_pid("pg") if is_clone else data["pid"]

        # 3) Build the LayoutTemplate instance
        geom = UnitStrGeometry.from_dict(data["geometry"])
        inst = cls(
            pid=pid,
            page_size=data.get("page_size", "custom"),
            geometry=geom,
            registry=registry,
            pagination_policy=data.get("pagination_policy", "InterleaveDatasets"),
            rows=data.get("rows", 3),
            columns=data.get("columns", 3),
            margin_top=UnitStr.from_dict(data.get("margin_top", "0.5in")),
            margin_bottom=UnitStr.from_dict(data.get("margin_bottom", "0.5in")),
            margin_left=UnitStr.from_dict(data.get("margin_left", "0.5in")),
            margin_right=UnitStr.from_dict(data.get("margin_right", "0.5in")),
            spacing_x=UnitStr.from_dict(data.get("spacing_x", "0.0in")),
            spacing_y=UnitStr.from_dict(data.get("spacing_y", "0.0in")),
            orientation=data.get("orientation", False),
            name=data.get("name"),
        )

        # 4) Wire up registry, set content, register self
        inst._registry = registry
        inst._content  = content
        registry.register(inst)
        # 5) Create new slots
        # print(f"Layout Template instance created. Creating slots with initGrid: {rows}, {columns} in registry: {registry}...")
        inst._items = inst.initGrid(registry, inst._rows, inst._columns)

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
        dpi : int, default 144
            DPI used for converting units to pixels.
        """

        rect = self.geometry.to(self.unit, dpi=self.dpi).rect
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
        top_margin, bottom_margin, left_margin, right_margin, spacing_x, spacing_y = self.get_whitespace()


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