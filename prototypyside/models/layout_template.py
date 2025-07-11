from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import Enum, auto
import json
from PySide6.QtWidgets import QGraphicsObject, QGraphicsItem, QStyleOptionGraphicsItem
from PySide6.QtCore import Qt, QRectF, QPointF, QSizeF, Signal
from PySide6.QtGui import QPageSize, QPainter, QPixmap, QColor, QImage, QPen, QBrush
from prototypyside.models.component_template import ComponentTemplate
from prototypyside.models.component_elements import ImageElement
from prototypyside.utils.unit_converter import to_px, page_in_px, page_in_units, compute_scale_factor
from prototypyside.utils.unit_str import UnitStr
from prototypyside.utils.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.ustr_helpers import with_rect, with_pos
from prototypyside.config import PAGE_SIZES, DISPLAY_MODE_FLAGS, PAGE_UNITS
from prototypyside.utils.proto_helpers import get_prefix, issue_pid




class LayoutSlot(QGraphicsObject):
    item_changed = Signal()
    def __init__(self, pid, geometry, row, column, parent=None):
        super().__init__(parent)
        self._pid = pid
        self._template_pid = None # This will hold a reference to the template which will be instanced to fill it.
        self._hovered = False
        self._geometry = geometry
        self._row = row
        self._column = column
        self._content = None
        self._display_flag = DISPLAY_MODE_FLAGS.get("stretch").get("aspect")
        self._cache_image = None
        self.setPos(geometry.pos_x.px, geometry.pos_y.px)
        self.setAcceptHoverEvents(True)
        print(f"Slot {pid} at positon {self._row}, {self._column} has geometry set to {geometry.rect.width()}x{geometry.rect.height()}")

    # --- Geometric Property Getter/Setters ---#
    @property
    def dpi(self):
        return self.geometry.dpi

    @property
    def geometry(self):
        return self._geometry

    @geometry.setter
    def geometry(self, new_geom: UnitStrGeometry):
        if self._geometry == new_geom:
            return
        self.prepareGeometryChange()
        self._geometry = new_geom
        super().setPos(self._geometry.px.pos)
        self.update()

    def boundingRect(self) -> QRectF:
        return self._geometry.px.rect

    # This method is for when ONLY the rectangle (size) changes,
    # not the position.
    def setRect(self, new_rect: QRectF):
        if self._geometry.px.rect == new_rect:
            return
        self.prepareGeometryChange()
        with_rect(self._geometry, new_rect)
        # self.update()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        # This is called when the scene moves the item.
        if change == QGraphicsItem.ItemPositionChange and value != self.pos():
            # Block signals to prevent a recursive loop if a connected item
            # also tries to set the position.
            signals_blocked = self.signalsBlocked()
            self.blockSignals(True)
            with_pos(self._geometry, value)
            print(f"[ITEMCHANGE] Called with change={change}, value={value}")
            print(f"[ITEMCHANGE] Geometry.pos updated to: {self._geometry.px.pos}")
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
        print(f"Slot content items are {self._content.items}")

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
        rect = self._geometry.px.rect        
        # Draw item fill and border
        fill = QBrush(QColor(230, 230, 230, 80))
        border = QPen(QColor(80, 80, 80), 1)
        painter.setPen(border)
        painter.setBrush(fill)
        painter.drawRect(rect)

        # Hover overlay
        if self._hovered:
            painter.setBrush(QBrush(QColor(70, 120, 240, 120)))
            painter.setPen(Qt.NoPen)
            painter.drawRect(rect)

        # Optionally, if there's no content, you could draw a dashed border or placeholder icon
        if self._content is None:
            pen = QPen(QColor(100, 100, 100, 120), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)
        if self._content is not None:
            # Slots render and draw their content
            rect = self.boundingRect()
            if self._cache_image is None:
                self._cache_image = self._render_to_image(dpi=self.geometry.dpi)

            painter.drawImage(rect, self._cache_image)

    def _render_to_image(self):
        rect = self.boundingRect()
        w, h = max(1, int(rect.width())), max(1, int(rect.height()))

        option = QStyleOptionGraphicsItem()
        image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)

        img_painter = QPainter(image)
        img_painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        # Set coordinate system so 1 px in logical unit equals 1 px in image
        img_painter.translate(-rect.topLeft())  # Align drawing to image origin

        # 1. Render the template background + border
        self.content.paint(img_painter, option, widget=None)

        # 2. Render all items
        for item in sorted(self.content.items, key=lambda e: e.zValue()):

            if isinstance(item, ImageElement) and item._content:
                # Force reload even if same path
                item._pixmap = None
                item.content = item._content

            img_painter.save()

            # Position & orientation
            pos = item.pos()
            img_painter.translate(pos.x(), pos.y())

            # 🔒 ENFORCE CLIP TO TEMPLATE BOUNDS (in local item space)
            item_bounds = item.boundingRect()
            img_painter.setClipRect(QRectF(0, 0, item_bounds.width(), item_bounds.height()))

            # Optional: rotation
            rotation = getattr(item, "rotation", lambda: 0)()
            if rotation:
                img_painter.rotate(rotation)

            # Draw item
            item.paint(img_painter, option, widget=None)

            img_painter.restore()
        return image

    # ---------------------------------------------------------------------
    # private helpers
    # ---------------------------------------------------------------------
    def _render_items(self, painter: QPainter) -> None:
        """
        Paint every item that lives in ``self.items`` onto *painter*.

        * The painter has already been scaled so that **1 logical unit
          (inch, mm, etc.) == 1 DPI-scaled pixel**, therefore item
          coordinates/rects can be used directly. :contentReference[oaicite:0]{index=0}
        * Elements must be drawn in z-order (lowest first) to match what the
          live QGraphicsScene does. :contentReference[oaicite:1]{index=1}
        * Each item’s own ``paint`` routine is reused so we don’t have to
          re-implement text/image logic here.  A throw-away
          ``QStyleOptionGraphicsItem`` is sufficient for most custom
          QGraphicsItems.

        Parameters
        ----------
        painter : QPainter
            The QPainter already set up by ``_render_to_image``.
        """
        # A single option object is fine – its values are rarely inspected by
        # custom items, but create one per item if you need per-item state.
        option = QStyleOptionGraphicsItem()

        # 1.  Render back-to-front, exactly like the scene does.
        self.content.paint(painter, option, widget=None)
        for item in sorted(self.content.items, key=lambda e: e.zValue()):
            painter.save()

            # 2.  Position & orientation (both expressed in logical units).
            pos = item.pos()              # QPointF
            painter.translate(pos.x(), pos.y())

            rotation = getattr(item, "rotation", lambda: 0)()
            if rotation:
                painter.rotate(rotation)

            # 3.  Delegate the actual drawing to the item itself.
            item.paint(painter, option, widget=None)

            painter.restore()

    def _render_background(self, painter: QPainter):
        """
        Draw the template background color or image.
        This assumes the template may define a background_color or background_image.
        """
        rect = self.geometry.px.rect

        bg_color = getattr(self._content, "background_color", None)
        bg_image_path = getattr(self._content, "background_image", None)

        if bg_color:
            painter.fillRect(rect, QColor(bg_color))

        if bg_image_path:
            pixmap = QPixmap(bg_image_path)
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
            "content": self.content.to_dict() if self.content else None
        }

    @classmethod
    def from_dict(cls, data: dict, registry: "ProtoRegistry") -> "LayoutSlot":
        inst = cls(
            pid=data["pid"],
            geometry=UnitStrGeometry.from_dict(data["geometry"]),
            row=data["row"],
            column=data["column"],
            parent=None
        )

        registry.register(inst)

        content_data = data.get("content")
        if content_data:
            # Only has access to local registry. Can't jump the fence.
            comp = ComponentTemplate.from_dict(content_data, registry)
            inst.content = comp

        return inst

class LayoutTemplate(QGraphicsObject):
    template_changed = Signal()
    marginsChanged = Signal()
    spacingChanged = Signal()
    export_quantity: Optional[int] = None     # Override for copies per item
    def __init__(self, pid, parent=None, registry = None,
                page_size = "letter", # if page_size != "custom", no custom_geometry needs be entered.
                custom_geometry=None, # custom_geometry must be of type UnitStrGeometry
                pagination_policy="InterleaveDatasets",
                rows=3, columns=3, dpi=144,
                name=None, margin_top="0.5in", margin_bottom = "0.5in",
                margin_left = "0.5in", margin_right = "0.5in",
                spacing_x = "0.0in", spacing_y  = "0.0in", is_landscape=False):
        super().__init__(parent)
        self._pid = pid
        self._name = name
        self.content = []
        self._page_size = page_size
        self._registry = registry
        if page_size == "custom" and custom_geometry:
                self._page_size = page_size
                self._geometry = custom_geometry 
        elif page_size == "custom" and not custom_geometry:
            self._page_size = "letter"
            self._geometry = PAGE_SIZES["letter"]["geometry"]
        else:
            self._page_size = page_size
            self._geometry = PAGE_SIZES[page_size]["geometry"]
        self._dpi = self._geometry.dpi

        self.pagination_policy = pagination_policy
        self._rows = rows
        self._columns = columns
        self._margins = [UnitStr(m, dpi=self._dpi) for m in (margin_top, margin_bottom, margin_left, margin_right)]
        self._spacing = [UnitStr(s, dpi=self._dpi) for s in (spacing_x, spacing_y)]
        self._is_landscape = is_landscape
        self._first_run = True
        self.items: List[List[LayoutSlot]] = [[]]

    @property
    def dpi(self) ->  int: return self._dpi

    @property
    def geometry(self) -> UnitStrGeometry: return self._geometry

    @geometry.setter
    def geometry(self, new_geom: UnitStrGeometry):
        if self._geometry == new_geom:
            return
        self.prepareGeometryChange()
        self._geometry = new_geom

        # sync page_size key (see above)
        for key, cfg in PAGE_SIZES.items():
            if cfg.get("geometry") == new_geom:
                self._page_size = key
                break
        else:
            self._page_size = "custom"

        super().setPos(self._geometry.px.pos)

        # swap width/height if in landscape
        self._applyOrientation()

        # rebuild your slots
        if hasattr(self, "_registry"):
            self.setGrid(self._registry, self._rows, self._columns)

        self.update()
        # self.geometryChanged.emit()

    def boundingRect(self) -> QRectF: return self._geometry.px.rect

    def setRect(self, new_rect: QRectF):
        self.prepareGeometryChange()
        self.geometry = with_rect(self._geometry, new_rect)
        self.update()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        if change == QGraphicsItem.ItemPositionChange:
            self._geometry = with_pos(self._geometry, value)
        return super().itemChange(change, value)
   
    @property
    def page_size(self):
       return self._page_size
        
    @page_size.setter
    def page_size(self, key):
        if key != self._page_size and key != "custom" and key in PAGE_SIZES: #custom not implemented
            self._page_size = key
            self.geometry = PAGE_SIZES[key].get("geometry")

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
    def is_landscape(self) -> bool:
        return self._is_landscape

    @is_landscape.setter
    def is_landscape(self, value: bool):
        if value == self._is_landscape:
            return
        self._is_landscape = value

        # same swap + rebuild logic
        self._applyOrientation()
        self.setGrid(self._registry, self.rows, self.columns)
        self.update()
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
        return [w.px for w in self._margins + self._spacing]

    ### Grid manipulation ###
    def setGrid(self, registry, rows=None, columns=None):
        """
        Expands or shrinks the items grid to match (rows, columns).
        Handles creation, updating, and deregistration of items as needed.
        """
        # -- 1. Determine new grid size --
        if not self._registry:
            self._registry = registry
        current_rows = len(self.items) if self.items else 0
        current_cols = len(self.items[0]) if self.items and self.items[0] else 0
        target_rows = rows if rows is not None else current_rows
        target_cols = columns if columns is not None else current_cols
        print(f"[LAYOUT_TEMPLATE] From setGrid: Setting grid to rows and columns: {target_rows},{target_cols}")
        if target_rows < 1 or target_cols < 1:
            return  # Nothing to do
        # Precompute the slot dimensions and positions for the new grid
        t, b, l, r, sx, sy = self.get_whitespace()  # px
        w, h = self._geometry.px.size.width(), self._geometry.px.size.height()
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
                        geometry=UnitStrGeometry.from_px(rect, pos, dpi=self._dpi),
                        row=r,
                        column=c,
                        parent=self,
                    )
                    self.items[r][c] = item
                    print(f"Slot[{r},{c}] x: {x_px}, y: {y_px}, width: {item_width_px}, height: {item_height_px}")
                    if item.scene() is None:
                        print("Item is being added to scene")
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
          • self.rows, self.columns

        Does NOT create or remove slots; only updates existing ones.
        """
        # 1. Gather pixel-values for margins & spacing
        top_px, bottom_px, left_px, right_px, spacing_x_px, spacing_y_px = self.get_whitespace()
        page_rect = self.geometry.px.rect
        total_w, total_h = page_rect.width(), page_rect.height()

        # 2. Compute available area and per-cell size
        avail_w = total_w - left_px - right_px - (self.columns - 1) * spacing_x_px
        avail_h = total_h - top_px - bottom_px - (self.rows    - 1) * spacing_y_px
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
                new_geom = UnitStrGeometry.from_px(rect, pos, dpi=self._dpi)

                # apply it
                slot.geometry = new_geom
                slot.row      = r
                slot.column   = c
                slot.invalidate_cache()   # so that its rendered thumbnail will be rebuilt

        # 4. Redraw the page and notify listeners
        self.update()
        self.template_changed.emit()
    # def setGrid(self, registry, rows=None, columns=None):
    #     """
    #     Expands or shrinks the items grid to match (rows, columns).
    #     Handles creation, updating, and deregistration of items as needed.
    #     """
    #     # -- 1. Determine new grid size --
    #     current_rows = len(self.items) if self.items else 0
    #     current_cols = len(self.items[0]) if self.items and self.items[0] else 0

    #     target_rows = rows if rows is not None else current_rows
    #     target_cols = columns if columns is not None else current_cols

    #     if target_rows < 1 or target_cols < 1:
    #         return  # Nothing to do

    #     # -- 2. Shrink rows if needed --
    #     while len(self.items) > target_rows:
    #         row = self.items.pop()
    #         for item in row:
    #             if item is not None:
    #                 registry.deregister(item.pid)
    #                 if item.scene() is not None:
    #                     self.scene().removeItem(item)

    #     # -- 3. Shrink columns in each row if needed --
    #     for row in self.items:
    #         while len(row) > target_cols:
    #             item = row.pop()
    #             if item is not None:
    #                 registry.deregister(item.pid)
    #                 if item.scene() is not None:
    #                     self.scene().removeItem(item)

    #     # -- 4. Expand rows if needed --
    #     while len(self.items) < target_rows:
    #         self.items.append([None for _ in range(target_cols)])

    #     # -- 5. Expand columns in each row if needed --
    #     for row in self.items:
    #         while len(row) < target_cols:
    #             row.append(None)

    #     # -- 6. Create/update all items in the new grid --
    #     for r in range(target_rows):
    #         for c in range(target_cols):
    #             item = self.items[r][c]
    #             item_width, item_height = self.compute_item_size(r, c)
    #             x_pos, y_pos = self.compute_item_position(r, c)
    #             rect = QRectF(0, 0, item_width, item_height)
    #             pos = QPointF(x_pos, y_pos)
    #             if item is not None:
    #                 # Update existing item
    #                 item.geometry = UnitStrGeometry(rect=rect, pos=pos, dpi=self._dpi)
    #                 item.update()
    #             else:
    #                 # Create new item and add to scene
    #                 item = registry.create(
    #                     "ls",
    #                     geometry=UnitStrGeometry.from_px(rect, pos, dpi=self._dpi),
    #                     row=r,
    #                     column=c,
    #                     parent=self,
    #                 )
    #                 self.items[r][c] = item
    #                 print(f"Slot[{r},{c}] x: {x_pos}, y: {y_pos}, width: {item_width}, height: {item_height}")
    #                 if item.scene() is None:
    #                     print("Item is being added to scene")
    #                     self.scene().addItem(item)
    #                 item.update()
    #     self.rows = target_rows
    #     self.columsn = target_cols

    def compute_item_size(self, row, col):
        """
        Returns item_width, item_height in **pixels** for the given grid position.
        Slot sizes are based on page size, margins, spacing, and grid size.
        """
        t, b, l, r, sx, sy = self.get_whitespace()  # Each is a float (pixels)
        w, h = self._geometry.px.size.width(), self._geometry.px.size.height()

        cols = self.columns
        rows = self.rows

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
        return [m for m in self._margins]

    def items_meet_minimum(self, min_dims: UnitStrGeometry) -> bool:
        """
        Return True if each item’s width ≥ min_width_in inches
        and height ≥ min_height_in inches; False otherwise.
        """
        item_size = self.items[0][0]._geometry.inch.size
        min_size = min_dims.inch.size

        return (
            item_size.width() >= min_size.width() and
            item_size.height() >= min_size.height()
        )
        
    def get_item_position(self, row: int, col: int) -> tuple[float, float]:
        item = self.items[row][col]
        return item.geometry.px.pos

    def get_item_size(self, row, col):
        """
        Returns the uniform cell size (width, height) in pixels for all items in the grid.
        """
        item_size = self.items[row][col].geometry.px.size

    def get_item_at_position(self, scene_pos: QPointF) -> Optional[LayoutSlot]:
        """
        Given a scene-coordinate point, return the LayoutSlot whose rect contains it,
        or None if no item matches.
        """

        for row in range(self.rows):
            for col in range(self.columns):
                item = self.items[row][col]
                rect = item.geometry.px.rect
                pos = item.geometry.px.pos
                x, y = pos.x(), pos.y()
                w, h = rect.width(), rect.height()
                item_rect = QRectF(x, y, w, h)
                if item_rect.contains(scene_pos):
                    print(f"Found layout item {item.pid} at {row},{col}")
                    return self.items[row][col]

        return None


    def to_dict(self) -> Dict:
        items = [[item.to_dict() for item in row] for row in self.items]
        return {
            "pid": self._pid,
            "name": self._name,
            "page_size": self._page_size,
            "custom_geometry": self._custom_geometry.to_dict() if self._page_size == "custom" else None,
            "pagination_policy": self.pagination_policy,
            "rows": self._rows,
            "columns": self._columns,
            "margin_top": self.margin_top.to_dict(),
            "margin_bottom": self.margin_bottom.to_dict(),
            "margin_left": self.margin_left.to_dict(),
            "margin_right": self.margin_right.to_dict(),
            "spacing_x": self.spacing_x.to_dict(),
            "spacing_y": self.spacing_y.to_dict(),
            "is_landscape": self._is_landscape,
            "content": self.content.to_dict() if self.content else [],
            "items": items,
        }

    @classmethod
    def from_dict(cls, data: dict, registry, is_clone=False) -> "LayoutTemplate":
        data_content = data.get("content", [])
        content = []

        # Ensure each ComponentTemplate is (re)hydrated and registered
        for ctemp in data_content:
            pid = ctemp.get("pid")
            if not registry.has(pid):
                obj = ComponentTemplate.from_dict(ctemp, registry)
                content.append(obj)
            else:
                content.append(registry.get(pid))

        # Page size & custom geometry logic
        page_size = data.get("page_size", "custom")
        custom_geom = None
        if page_size == "custom":
            custom_geom = UnitStrGeometry.from_dict(data["custom_geometry"])

        # Construct the LayoutTemplate instance
        inst = cls(
            pid=data["pid"],
            page_size=page_size,
            custom_geometry=custom_geom,
            pagination_policy=data.get("pagination_policy", "InterleaveDatasets"),
            rows=data.get("rows", 3),
            columns=data.get("columns", 3),
            margin_top=UnitStr.from_dict(data.get("margin_top", "0.5in")),
            margin_bottom=UnitStr.from_dict(data.get("margin_bottom", "0.5in")),
            margin_left=UnitStr.from_dict(data.get("margin_left", "0.5in")),
            margin_right=UnitStr.from_dict(data.get("margin_right", "0.5in")),
            spacing_x=UnitStr.from_dict(data.get("spacing_x", "0.0in")),
            spacing_y=UnitStr.from_dict(data.get("spacing_y", "0.0in")),
            is_landscape=data.get("is_landscape", False),
            name=data.get("name"),
        )

        # Populate the content list on the instance
        inst.content = content

        # Rehydrate LayoutSlot items
        inst.items = []
        count = 1
        for row_data in data.get("items", []):
            row = []
            for item_dict in row_data:
                item = LayoutSlot.from_dict(item_dict, registry)
                item.setParentItem(inst)
                row.append(item)
                count += 1
            inst.items.append(row)
        print(f"Rehydrated {count} slots.")
        return inst

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.boundingRect()

        # White background for page item
        painter.setBrush(Qt.white)
        painter.setPen(QPen(Qt.black, 2))
        painter.drawRect(rect)

        # Optionally: draw grid lines for visual aid
        top_margin_px, bottom_margin_px, left_margin_px, right_margin_px, spacing_x_px, spacing_y_px = self.get_whitespace()
        rows = self.rows
        cols = self.columns

        total_w = rect.width() - left_margin_px - right_margin_px - spacing_x_px * (cols - 1)
        total_h = rect.height() - top_margin_px - bottom_margin_px - spacing_y_px * (rows - 1)

        cell_w = total_w / cols
        cell_h = total_h / rows

        # Thin, light grid lines (optional)
        grid_pen = QPen(Qt.gray, 1, Qt.DashLine)
        painter.setPen(grid_pen)
        for r in range(rows + 1):
            y = rect.top() + top_margin_px + r * (cell_h + spacing_y_px) - (spacing_y_px if r > 0 else 0)
            painter.drawLine(rect.left() + left_margin_px, y,
                             rect.left() + left_margin_px + total_w + spacing_x_px * (cols - 1), y)
        for c in range(cols + 1):
            x = rect.left() + left_margin_px + c * (cell_w + spacing_x_px) - (spacing_x_px if c > 0 else 0)
            painter.drawLine(x, rect.top() + top_margin_px,
                             x, rect.top() + top_margin_px + total_h + spacing_y_px * (rows - 1))


    def _applyOrientation(self):
        # pick the raw (portrait) base geometry
        if self._page_size == "custom":
            base = self._geometry
        else:
            base = PAGE_SIZES[self._page_size]["geometry"]

        r = base.px.rect
        w, h = r.width(), r.height()
        if self._is_landscape:
            r = QRectF(0, 0, h, w)
        else:
            r = QRectF(0, 0, w, h)

        # build a new UnitStrGeometry from that pixel rect
        rotated = UnitStrGeometry.from_px(r, QPointF(0, 0), dpi=self._dpi)
        # shove it back through the setter (this will re-sync page_size if needed)
        self._geometry = rotated