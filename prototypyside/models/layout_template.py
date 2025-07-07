from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import Enum, auto
import json
from PySide6.QtWidgets import QGraphicsObject, QGraphicsItem
from PySide6.QtCore import Qt, QRectF, QPointF, QSizeF, Signal
from PySide6.QtGui import QPageSize, QPainter, QPixmap, QColor, QImage, QPen, QBrush
from prototypyside.utils.unit_converter import to_px, page_in_px, page_in_units, compute_scale_factor
from prototypyside.utils.unit_str import UnitStr
from prototypyside.utils.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.ustr_helpers import with_rect, with_pos
from prototypyside.config import PAGE_SIZES, DISPLAY_MODE_FLAGS, PAGE_UNITS



class LayoutSlot(QGraphicsObject):
    def __init__(self, pid, geometry=None, parent=None):
        super().__init__(parent)
        self._pid = pid
        self._hovered = False
        self._geometry = geometry
        self._dpi = geometry.dpi
        self._geometry = geometry
        self._content = None
        self._display_flag = DISPLAY_MODE_FLAGS.get("stretch").get("aspect")
        self.setPos(geometry.pos_x.px, geometry.pos_y.px)
        self.setAcceptHoverEvents(True)


    # These three methods must be defined for each object.
    @property
    def dpi(self): return self._dpi

    @property
    def geometry(self): return self._geometry

    def boundingRect(self) -> QRectF:
        return self._geometry.px.rect

    def setRect(self, new_rect: QRectF):
        self.prepareGeometryChange()
        self._geometry = with_rect(self._geometry, new_rect)
        self.update()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        if change == QGraphicsItem.ItemPositionChange:
            self._geometry = with_pos(self._geometry, value)
        return super().itemChange(change, value)

    @property
    def pid(self) -> str:
        return self._pid

    @pid.setter
    def pid(self, value):
        self._pid = value
        self.template_changed.emit()

    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, obj):
        self._content = obj
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
        # Draw slot fill and border
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
            if self._cache_image is None:
                self._cache_image = self._render_to_image(dpi=self._dpi)

            painter.drawImage(self.boundingRect(), self._cache_image)

    def _render_to_image(self, dpi):
        rect = self.boundingRect()
        w, h = int(rect.width()), int(rect.height())

        option = QStyleOptionGraphicsItem()
        image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)

        img_painter = QPainter(image)
        img_painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        # Set coordinate system so 1 px in logical unit equals 1 px in image
        img_painter.translate(-rect.topLeft())  # Align drawing to image origin

        # 1. Render the template background + border
        self.content.paint(img_painter, option, widget=None)

        # 2. Render all elements
        for element in sorted(self.content.elements, key=lambda e: e.zValue()):
            img_painter.save()

            # Position & orientation
            pos = element.pos()
            img_painter.translate(pos.x(), pos.y())

            # 🔒 ENFORCE CLIP TO TEMPLATE BOUNDS (in local element space)
            element_bounds = element.boundingRect()
            img_painter.setClipRect(QRectF(0, 0, element_bounds.width(), element_bounds.height()))

            # Optional: rotation
            rotation = getattr(element, "rotation", lambda: 0)()
            if rotation:
                img_painter.rotate(rotation)

            # Draw element
            element.paint(img_painter, option, widget=None)

            img_painter.restore()


    # ---------------------------------------------------------------------
    # private helpers
    # ---------------------------------------------------------------------
    def _render_elements(self, painter: QPainter) -> None:
        """
        Paint every element that lives in ``self.elements`` onto *painter*.

        * The painter has already been scaled so that **1 logical unit
          (inch, mm, etc.) == 1 DPI-scaled pixel**, therefore element
          coordinates/rects can be used directly. :contentReference[oaicite:0]{index=0}
        * Elements must be drawn in z-order (lowest first) to match what the
          live QGraphicsScene does. :contentReference[oaicite:1]{index=1}
        * Each element’s own ``paint`` routine is reused so we don’t have to
          re-implement text/image logic here.  A throw-away
          ``QStyleOptionGraphicsItem`` is sufficient for most custom
          QGraphicsItems.

        Parameters
        ----------
        painter : QPainter
            The QPainter already set up by ``_render_to_image``.
        """
        # A single option object is fine – its values are rarely inspected by
        # custom items, but create one per element if you need per-item state.
        option = QStyleOptionGraphicsItem()

        # 1.  Render back-to-front, exactly like the scene does.
        self.content.paint(painter, option, widget=None)
        for element in sorted(self.content.elements, key=lambda e: e.zValue()):
            painter.save()

            # 2.  Position & orientation (both expressed in logical units).
            pos = element.pos()              # QPointF
            painter.translate(pos.x(), pos.y())

            rotation = getattr(element, "rotation", lambda: 0)()
            if rotation:
                painter.rotate(rotation)

            # 3.  Delegate the actual drawing to the element itself.
            element.paint(painter, option, widget=None)

            painter.restore()

    def _render_background(self, painter: QPainter):
        """
        Draw the template background color or image.
        This assumes the template may define a background_color or background_image.
        """
        rect = QRectF(0, 0, self._width.to("float"), self._height.to("float"))

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
        Updates elements with values from csv_row, only if their name is a data binding.
        If the element already has static content, it is left unchanged unless overridden by csv data.
        """
        for element in self._content.elements:
            if element.name.startswith("@"):
                col = element.name
                if col in csv_row:
                    value = csv_row[col]
                    setattr(element, "content", value)

    def apply_data(row):
        # Update child elements to use new data
        for element in self.content.elements():
            if hasattr(element, "content",):
                element.update_from_merge_data(merge_data)
        self.update()
        # If you want to draw anything *over* the content, you could do it here.


class LayoutTemplate(QGraphicsObject):
    template_changed = Signal()
    marginsChanged = Signal()
    spacingChanged = Signal()
    export_quantity: Optional[int] = None     # Override for copies per slot
    def __init__(self, pid, parent=None, 
                geometry=UnitStrGeometry(width="8.5in", height="11.5in", dpi=144),
                page_size = "Letter (8.5 × 11 in)",
                pagination_policy="InterleaveDatasets",
                pagination_params={},
                rows=3, columns=3, dpi=144,
                name=None, margin_top="0.5in", margin_bottom = "0.5in",
                margin_left = "0.25in", margin_right = "0.25in",
                spacing_x = "0.0in", spacing_y  = "0.0in", landscape=False, auto_fill=True):
        super().__init__(parent)
        self._pid = pid
        self._name = name
        self._geometry = geometry
        print(f"LayoutTemplate geometry {geometry.px.rect}")
        self._dpi = geometry.dpi
        # # Always store page_size as a display string
        if page_size in PAGE_SIZES:
            self.page_size = page_size
        else:
            # fallback: use default if page_size not recognized
            self.page_size = "Letter (8.5 × 11 in)"

        self.pagination_policy = pagination_policy or "InterleaveDatasets"
        self.pagination_params = pagination_params or {}
        self._dpi = dpi
        self._margins = [UnitStr(m, dpi=self._dpi) for m in (margin_top, margin_bottom, margin_left, margin_right)]
        self._spacing = [UnitStr(s, dpi=self._dpi) for s in (spacing_x, spacing_y)]
        self.landscape = landscape
        self.auto_fill = auto_fill
        self._rows = rows
        self._columns = columns 
        self.layout_slots: List[List[LayoutSlot]] = [[]]

    # These three methods must be defined for each object. They maintain consistency.
    @property
    def dpi(self): return self._dpi

    @property
    def geometry(self): return self._geometry

    def boundingRect(self) -> QRectF:
        return self._geometry.px.rect

    def setRect(self, new_rect: QRectF):
        self.prepareGeometryChange()
        self._geometry = with_rect(self._geometry, new_rect)
        self.update()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        if change == QGraphicsItem.ItemPositionChange:
            self._geometry = with_pos(self._geometry, value)
        return super().itemChange(change, value)
        
    @property
    def pid(self) -> str:
        return self._pid

    @pid.setter
    def pid(self, value):
        self._pid = value
        self.template_changed.emit()

    @property
    def rows(self):
        return self._rows

    @rows.setter
    def rows(self, value):
        if value != self._rows:
            self._rows = value
            self.set_grid(self._rows, self._columns)

    @property
    def columns(self):
        return self._columns

    @columns.setter
    def columns(self, value):
        if value != self._columns:
            self._columns = value
            self.set_grid(self._rows, self._columns)

    @property 
    def display_flag(self):
        return self._display_flag

    @display_flag.setter
    def display_flag(self, qflag):
        if qflag != self._display_flag:
            self._display_flag = qflag

    # ---- Margins and Grid Spacing ---- #
    @property
    def margins(self):
        return self._margins

    @property
    def margins(self, new_margins: List[UnitStr]):
        self._margins = new_margins
        self.marginsChanged.emit()

    @property
    def margin_top(self):
        return self._margins[0]

    @margin_top.setter
    def margin_top(self, ustr: UnitStr):
        self._margins[0] = ustr
        self.marginsChanged.emit()

    @property
    def margin_bottom(self):
        return self._margins[1]

    @margin_bottom.setter 
    def margin_bottom(self, ustr: UnitStr):
        self._margins[1] = ustr
        self.marginsChanged.emit()

    @property
    def margin_left(self):
        return self._margins[2]

    @margin_left.setter
    def margin_left(self, ustr: UnitStr):
        self._margins[2] = ustr
        self.marginsChanged.emit()

    @property
    def margin_right(self):
        return self._margins[3]

    @margin_right.setter
    def margin_right(self, ustr: UnitStr):
        self.margins[3] = ustr
        self.marginsChanged.emit()

    @property
    def spacing_x(self):
        return self._spacing[0]

    @spacing_x.setter
    def spacing_x(self, ustr: UnitStr):
        self._spacing[0] = ustr
        self.spacingChanged.emit()

    @property
    def spacing_y(self):
        return self._spacing[1]

    @spacing_x.setter
    def spacing_y(self, ustr: UnitStr):
        self._spacing[1] = ustr
        self.spacingChanged.emit()

    def get_whitespace(self):
        return [w.px for w in self._margins + self._spacing]

    ### Grid manipulation ###
    def setGrid(self, registry, rows=None, columns=None):
        """
        Expands or shrinks the layout_slots grid to match (rows, columns).
        Handles creation, updating, and deregistration of slots as needed.
        """
        # -- 1. Determine new grid size --
        current_rows = len(self.layout_slots) if self.layout_slots else 0
        current_cols = len(self.layout_slots[0]) if self.layout_slots and self.layout_slots[0] else 0

        target_rows = rows if rows is not None else current_rows
        target_cols = columns if columns is not None else current_cols

        if target_rows < 1 or target_cols < 1:
            return  # Nothing to do

        # -- 2. Shrink rows if needed --
        while len(self.layout_slots) > target_rows:
            row = self.layout_slots.pop()
            for slot in row:
                if slot is not None:
                    registry.deregister(slot.pid)
                    if slot.scene() is not None:
                        self.scene.removeItem(slot)

        # -- 3. Shrink columns in each row if needed --
        for row in self.layout_slots:
            while len(row) > target_cols:
                slot = row.pop()
                if slot is not None:
                    registry.deregister(slot.pid)
                    if slot.scene() is not None:
                        self.scene.removeItem(slot)

        # -- 4. Expand rows if needed --
        while len(self.layout_slots) < target_rows:
            self.layout_slots.append([None for _ in range(target_cols)])

        # -- 5. Expand columns in each row if needed --
        for row in self.layout_slots:
            while len(row) < target_cols:
                row.append(None)

        # -- 6. Create/update all slots in the new grid --
        for r in range(target_rows):
            for c in range(target_cols):
                slot = self.layout_slots[r][c]
                slot_width, slot_height = self.compute_slot_size(r, c)
                x_pos, y_pos = self.compute_slot_position(r, c)
                rect = QRectF(0, 0, slot_width, slot_height)
                pos = QPosF(x_pos, y_pos)
                if slot is not None:
                    # Update existing slot
                    slot.geometry.from_px(rect=rect, pos=pos, dpi=self._dpi)
                    slot.update()
                else:
                    # Create new slot and add to scene
                    slot = registry.create(
                        "ls",
                        geometry=UnitStrGeometry.from_px(rect, pos, dpi=self._dpi),
                        parent=self,
                    )
                    self.layout_slots[r][c] = slot
                    print(f"Slot[{r},{c}] x: {x_pos}, y: {y_pos}, width: {slot_width}, height: {slot_height}")
                    if slot.scene() is None:
                        print("Item is being added to scene")
                        self.scene.addItem(slot)
                    slot.update()

    def compute_slot_size(self, row, col):
        """
        Returns slot_width, slot_height in **pixels** for the given grid position.
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

        slot_width_px = max(avail_width / cols, 0)
        slot_height_px = max(avail_height / rows, 0)

        # Debug
        # print(f"compute_slot_size: avail_width={avail_width}, cols={cols}, slot_width_px={slot_width_px}")
        # print(f"compute_slot_size: avail_height={avail_height}, rows={rows}, slot_height_px={slot_height_px}")

        return slot_width_px, slot_height_px

    def compute_slot_position(self, row, col):
        """
        Returns x, y in **pixels** for the given grid position.
        """
        t, b, l, r, sx, sy = self.get_whitespace()  # px
        slot_width_px, slot_height_px = self.compute_slot_size(row, col)

        x_px = l + col * (sx + slot_width_px)
        y_px = t + row * (sy + slot_height_px)

        # Debug:
        # print(f"compute_slot_position: l={l}, col={col}, sx={sx}, slot_width_px={slot_width_px} => x_px={x_px}")
        # print(f"compute_slot_position: t={t}, row={row}, sy={sy}, slot_height_px={slot_height_px} => y_px={y_px}")

        return x_px, y_px

    def get_margins(self):
        return [m for m in self._margins]

    def slots_meet_minimum(self, min_dims: UnitStrGeometry) -> bool:
        """
        Return True if each slot’s width ≥ min_width_in inches
        and height ≥ min_height_in inches; False otherwise.
        """
        slot_size = self.layout_slots[0][0]._geometry.inch.size
        min_size = min_dims.inch.size

        return (
            slot_size.width() >= min_size.width() and
            slot_size.height() >= min_size.height()
        )
        

    def get_slot_position(self, row: int, col: int) -> tuple[float, float]:
        slot = self.layout_slots[row][col]
        return slot.geometry.px.pos

    def get_slot_size(self) -> Tuple[float, float]:
        """
        Returns the uniform cell size (width, height) in pixels for all slots in the grid.
        """
        slot_size = self.layout_slots[0][0]._geometry.to("px", self._dpi).size

    def get_slot_at_position(self, scene_pos: QPointF) -> Optional[LayoutSlot]:
        """
        Given a scene-coordinate point, return the LayoutSlot whose rect contains it,
        or None if no slot matches.
        """
        cell_w, cell_h = self.get_cell_size_px()

        for row in range(self.rows):
            for col in range(self.columns):
                x_px, y_px = self.get_slot_position_px(row, col)
                slot_rect = QRectF(x_px, y_px, cell_w, cell_h)
                if slot_rect.contains(scene_pos):
                    return self.layout_slots[row][col]

        return None

    def iter_slot_geometry(self):
        """
        Yields (row, col, position, rect) for all grid positions.
        """
        for r in range(self.rows):
            for c in range(self.columns):
                pos = self.get_slot_position_px(r, c)
                rect = self.get_slot_rect_px(r, c)
                yield r, c, pos, rect

    def to_dict(self) -> Dict:
        page_size_id = self.page_size.id()
        data = {
            "pid": self._pid,
            "name": self._name,
            "geometry": self._geometry,
            # # Use the enum's value for serialization
            # "page_size_id": page_size_id,   # Convert ID to integer
            # "name": self.page_size.name(),
            # "units": self.page_size.size(QPageSize.Inch),
            "rows": self._rows,
            "columns": self._columns,
            "margin_top": self.margin_top,
            "margin_bottom": self.margin_bottom,
            "margin_left": self.margin_left,
            "margin_right": self.margin_right,
            "spacing_x": self.spacing_x,
            "spacing_y": self.spacing_y,
            "layout_slots": self.layout_slots,
        }
        data["paginationPolicy"] = {
            "type": self.pagination_policy,
            "params": self.pagination_params,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LayoutTemplate":
        pol = data.get("paginationPolicy", {})
        page_size_id = data.get("page_size_id", QPageSize.Letter)
        page_size = QPageSize(QPageSize.PageSizeId(page_size_id))

        template = cls(
            pid=data["pid"],
            name=data.get("name", "Layout Template"),
            geometry=UnitStrGeometry.from_dict(data.get("geometry")),
            # page_size = QPageSize.PageSizeId(data.get("page_size_id", QPageSize.Letter)),
            pagination_policy = pol.get("type"),
            pagination_params = pol.get("params"),
            rows=data.get("rows", 1),
            columns=data.get("columns", 1),
            margin_top=data.get("margin_top", "0.5in"),
            margin_bottom=data.get("margin_bottom", "0.5in"),
            margin_left=data.get("margin_left", "0.25in"),
            margin_right=data.get("margin_left", "0.25in"),
            spacing_x=data.get("spacing_x", "0"),
            spacing_y=data.get("spacing_y", "0"),
            layout_slots=data.get("layout_slots", [[]])
        )

        return template

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.boundingRect()

        # Optional: Debug
        # print(f"LayoutTemplate::paint called for rect: {rect}")

        # Transparent background for page item
        painter.setBrush(Qt.transparent)
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


    def save_to_file(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, path: str) -> "LayoutTemplate":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)