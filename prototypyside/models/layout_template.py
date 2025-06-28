from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
import json
from PySide6.QtWidgets import QGraphicsObject
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QPageSize, QPainter, QPixmap, QColor, QImage, QPen, QBrush
from prototypyside.utils.unit_converter import to_px, page_in_px, page_in_units, compute_scale_factor
from prototypyside.utils.unit_str import UnitStr
from prototypyside.config import PAGE_SIZES
from prototypyside.services.undo_commands import AddSlotCommand

class LayoutSlot(QGraphicsObject):
    def __init__(self, pid, width, height, x=0, y=0, parent=None):
        super().__init__(parent)
        self.setAcceptHoverEvents(True)
        self._pid = pid
        self._hovered = False
        # If any of these are UnitStr, convert to float px
        self._width = float(width.to("px")) if hasattr(width, "to") else float(width)
        self._height = float(height.to("px")) if hasattr(height, "to") else float(height)
        self._x = float(x.to("px")) if hasattr(x, "to") else float(x)
        self._y = float(y.to("px")) if hasattr(y, "to") else float(y)
        self.unit = getattr(parent, "unit", None)
        self.dpi = getattr(parent, "dpi", None)
        self.setRect(self.getRect())
        self.setPos(self._x, self._y)

    @property
    def pid(self) -> str:
        return self._pid

    @pid.setter
    def pid(self, value):
        self._pid = value
        self.template_changed.emit()

    def boundingRect(self) -> QRectF:
        # Use pixel floats directly!
        return QRectF(0, 0, self._width, self._height)

    def getRect(self):
        # Returns a QRectF in scene (pixel) coordinates.
        return QRectF(
            self._x,
            self._y,
            self._width,
            self._height,
        )

    def setRect(self, rect: QRectF):
        # Updates pixel float fields based on the given QRectF (in px).
        self._x = rect.x()
        self._y = rect.y()
        self._width = rect.width()
        self._height = rect.height()
        # Optionally self.update()


    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()

    def paint(self, painter, option, widget=None):
        #print(f"Preparing to paint slot at {self.pos()} with rect {self.getRect()}")
        rect = self.boundingRect()
        # Normal fill: light gray, border: dark gray
        fill = QBrush(QColor(230, 230, 230, 80))
        border = QPen(QColor(80, 80, 80), 1)
        painter.setPen(border)
        painter.setBrush(fill)
        painter.drawRect(rect)

        # Hover overlay: transparent blue
        if self._hovered:
            painter.setBrush(QBrush(QColor(70, 120, 240, 120)))
            painter.setPen(Qt.NoPen)
            painter.drawRect(rect)


class LayoutTemplate(QGraphicsObject):
    marginsChanged = Signal()
    spacingChanged = Signal()
    export_quantity: Optional[int] = None     # Override for copies per slot
    def __init__(self, pid, registry, parent=None, 
                page_size="Letter (8.5 × 11 in)", 
                rows=3, columns=3, dpi=300, unit="in", 
                name=None, margin_top="0.5in", margin_bottom = "0.5in",
                margin_left = "0.25in", margin_right = "0.25in",
                spacing_x = "0.0in", spacing_y  = "0.0in", landscape=False, auto_fill=True):
        super().__init__(parent)
        self._pid = pid
        self.name = name
        self.registry = registry
        # Always store page_size as a display string
        if page_size in PAGE_SIZES:
            self.page_size = page_size
        else:
            # fallback: use default if page_size not recognized
            self.page_size = "Letter (8.5 × 11 in)"
        self.unit = unit
        self.dpi = dpi
        self._margin_top = UnitStr(margin_top, unit=unit, dpi=dpi)
        self._margin_bottom = UnitStr(margin_bottom, unit=unit, dpi=dpi)
        self._margin_left = UnitStr(margin_left, unit=unit, dpi=dpi)
        self._margin_right = UnitStr(margin_right, unit=unit, dpi=dpi)
        self._spacing_x = UnitStr(spacing_x, unit=unit, dpi=dpi)
        self._spacing_y = UnitStr(spacing_y, unit=unit, dpi=dpi)
        self._width, self._height = self.get_page_size()
        self.landscape = landscape
        self.auto_fill = auto_fill
        self._rows = rows
        self._columns = columns 
        self.layout_slots: List[List[LayoutSlot]] = [[]]

        # self.setGrid(self.rows, self.columns)

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
    @property
    def columns(self):
        return self._columns

    @columns.setter
    def columns(self, value):
        if value != self._columns:
            self._columns = value

    def get_bounding_rect(self) -> QRectF:
        w, h = self.get_page_size()
        w_px = w.to("px")
        h_px = h.to("px")
        return QRectF(0, 0, w_px, h_px)

    def get_page_size(self) -> tuple[UnitStr, UnitStr]:
        """
        Returns (page_width, page_height) as UnitStr in the template's current unit.
        """
        ps_enum = PAGE_SIZES.get(self.page_size)
        if ps_enum is None:
            ps_enum = QPageSize.Letter
        qpagesize = QPageSize(ps_enum)

        if self.unit == "in":
            size = qpagesize.size(QPageSize.Unit.Inch)
            w = UnitStr(size.width(), unit="in", dpi=self.dpi)
            h = UnitStr(size.height(), unit="in", dpi=self.dpi)
        elif self.unit == "mm":
            size = qpagesize.size(QPageSize.Unit.Millimeter)
            w = UnitStr(size.width(), unit="mm", dpi=self.dpi)
            h = UnitStr(size.height(), unit="mm", dpi=self.dpi)
        elif self.unit == "cm":
            size = qpagesize.size(QPageSize.Unit.Millimeter)
            w = UnitStr(size.width() / 10.0, unit="cm", dpi=self.dpi)
            h = UnitStr(size.height() / 10.0, unit="cm", dpi=self.dpi)
        else:
            size = qpagesize.size(QPageSize.Unit.Inch)
            w = UnitStr(size.width(), unit="in", dpi=self.dpi)
            h = UnitStr(size.height(), unit="in", dpi=self.dpi)
        return w, h

    @property
    def page_width(self) -> UnitStr:
        return self.get_page_size()[0]

    @property
    def page_height(self) -> UnitStr:
        return self.get_page_size()[1]

    def boundingRect(self):
        return self.get_bounding_rect()

    @property
    def margin_top(self):
        return self._margin_top

    @margin_top.setter
    def margin_top(self, value):
        if isinstance(value, UnitStr):
            self._margin_top = value
        else:
            self._margin_top = UnitStr(value, unit=self._margin_top.unit, dpi=self._margin_top.dpi)
        # self.marginsChanged.emit()
        # self.update()

    @property
    def margin_bottom(self):
        return self._margin_bottom

    @margin_bottom.setter
    def margin_bottom(self, value):
        if isinstance(value, UnitStr):
            self._margin_bottom = value
        else:
            self._margin_bottom = UnitStr(value, unit=self._margin_bottom.unit, dpi=self._margin_bottom.dpi)
        # self.marginsChanged.emit()
        # self.update()

    @property
    def margin_left(self):
        return self._margin_left

    @margin_left.setter
    def margin_left(self, value):
        if isinstance(value, UnitStr):
            self._margin_left = value
        else:
            self._margin_left = UnitStr(value, unit=self._margin_left.unit, dpi=self._margin_left.dpi)
        # self.marginsChanged.emit()
        # self.update()

    @property
    def margin_right(self):
        return self._margin_right

    @margin_right.setter
    def margin_right(self, value):
        if isinstance(value, UnitStr):
            self._margin_right = value
        else:
            self._margin_right = UnitStr(value, unit=self._margin_right.unit, dpi=self._margin_right.dpi)
        # self.marginsChanged.emit()
        # self.update()

    @property
    def spacing_x(self):
        return self._spacing_x

    @spacing_x.setter
    def spacing_x(self, value):
        print("spacing set")
        if isinstance(value, UnitStr):
            self._spacing_x = value
        else:
            self._spacing_x = UnitStr(value, unit=self._spacing_x.unit, dpi=self._spacing_x.dpi)
        self.marginsChanged.emit()

    def get_page_dim_px(self):
        return self._width.to("px"), self._height.to("px")

    def get_margins_and_spacing_px(self):
        return [
            self.margin_top.to("px"),
            self.margin_bottom.to("px"),
            self.margin_left.to("px"),
            self.margin_right.to("px"),
            self.spacing_x.to("px"),
            self.spacing_y.to("px")
        ]

    @property
    def spacing_y(self):
        return self._spacing_y

    @spacing_y.setter
    def spacing_y(self, value):
        if isinstance(value, UnitStr):
            self._spacing_y = value
        else:
            self._spacing_y = UnitStr(value, unit=self._spacing_y.unit, dpi=self._spacing_y.dpi)
        self.spacingChanged.emit()
        # self.update()

    def get_margins(self):
        return self._margin_top, self._margin_bottom, self._margin_left, self._margin_right

    @property
    def rect(self):
        return self.get_bounding_rect

    ### Grid manipulation ###

    def setGrid(self, rows=None, columns=None):
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
                    self.registry.deregister(slot.pid)
                    if slot.scene() is not None:
                        self.scene.removeItem(slot)

        # -- 3. Shrink columns in each row if needed --
        for row in self.layout_slots:
            while len(row) > target_cols:
                slot = row.pop()
                if slot is not None:
                    self.registry.deregister(slot.pid)
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
                if slot is not None:
                    # Update existing slot
                    slot._width = float(slot_width)
                    slot._height = float(slot_height)
                    slot._x = float(x_pos)
                    slot._y = float(y_pos)
                    slot.setPos(x_pos, y_pos)
                    slot.setRect(QRectF(0, 0, slot_width, slot_height))
                    slot.update()
                else:
                    # Create new slot and add to scene
                    slot = self.registry.create(
                        "ls",
                        width=slot_width,
                        height=slot_height,
                        x=x_pos,
                        y=y_pos,
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
        t, b, l, r, sx, sy = self.get_margins_and_spacing_px()  # Each is a float (pixels)
        w, h = self.get_page_dim_px()  # floats (pixels)

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
        t, b, l, r, sx, sy = self.get_margins_and_spacing_px()  # px
        slot_width_px, slot_height_px = self.compute_slot_size(row, col)

        x_px = l + col * (sx + slot_width_px)
        y_px = t + row * (sy + slot_height_px)

        # Debug:
        # print(f"compute_slot_position: l={l}, col={col}, sx={sx}, slot_width_px={slot_width_px} => x_px={x_px}")
        # print(f"compute_slot_position: t={t}, row={row}, sy={sy}, slot_height_px={slot_height_px} => y_px={y_px}")

        return x_px, y_px



    def get_px_margins(self):
        return (self.margin_top.to("px", dpi=self.dpi), self.margin_bottom.to("px", dpi=self.dpi), 
                self.margin_left.to("px", dpi=self.dpi), self.margin_right.to("px", dpi=self.dpi))

    def slots_meet_minimum(self, min_width: float, min_height: float) -> bool:
        """
        Return True if each slot’s width ≥ min_width_in inches
        and height ≥ min_height_in inches; False otherwise.
        """
        # convert required inches → pixels
        min_w_px = parse_dimension(min_width, min_height)
        min_h_px = to_px(f"{min_height_in}in")

        slot_w, slot_h = self.get_slot_dimensions_px()

        return slot_w >= min_w_px and slot_h >= min_h_px

    # def get_slot_position_px(self, row: int, col: int) -> tuple[float, float]:
    #     rect = self.boundingRect()
    #     cell_w, cell_h = self.get_cell_size_px()
    #     spacing_x = to_px(self.spacing_x)
    #     spacing_y = to_px(self.spacing_y)
    #     top, bottom, left, right = self.get_px_margins()

    #     x = rect.left() + left + col * (cell_w + spacing_x)
    #     y = rect.top() + top + row * (cell_h + spacing_y)
    #     return x, y

    # def get_slot_at_position(self, scene_pos: QPointF) -> Tuple[Optional[str], Optional[QPointF]]:
    #     """
    #     Given a scene-coordinate point, return the (slot_pid, slot_origin)
    #     whose rect contains it, or (None, None) if no slot matches.
    #     """
    #     # uniform slot size in pixels
    #     cell_w, cell_h = self.get_cell_size_px()

    #     for row in range(self.rows):
    #         for col in range(self.columns):
    #             # slot’s top-left in px
    #             x_px, y_px = self.get_slot_position_px(row, col)
    #             slot_rect = QRectF(x_px, y_px, cell_w, cell_h)

    #             if slot_rect.contains(scene_pos):
    #                 # now index into the 2D list
    #                 slot_pid = None
    #                 if self.layout_slots and len(self.layout_slots) > row:
    #                     slot_row = self.layout_slots[row]
    #                     if len(slot_row) > col:
    #                         slot_pid = slot_row[col]
    #                 return slot_pid, QPointF(x_px, y_px)

    #     return None, None

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
        return {
            "pid": self.pid,
            "name": self.name,
            # Use the enum's value for serialization
            "page_size_id": page_size_id,   # Convert ID to integer
            "name": self.page_size.name(),
            "units": self.page_size.size(QPageSize.Inch), # Convert units enum to int
            "rows": self.rows,
            "columns": self.columns,
            "margin_top": self.margin_top,
            "margin_bottom": self.margin_bottom,
            "margin_left": self.margin_left,
            "margin_right": self.margin_right,
            "spacing_x": self.spacing_x,
            "spacing_y": self.spacing_y,
            "layout_slots": self.layout_slots,
        }
        # print(f"Page Size enum value {page_size_id}")   

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.boundingRect()

        # Optional: Debug
        # print(f"LayoutTemplate::paint called for rect: {rect}")

        # Transparent background for page item
        painter.setBrush(Qt.transparent)
        painter.setPen(QPen(Qt.black, 2))
        painter.drawRect(rect)

        # Optionally: draw grid lines for visual aid
        top_margin_px, bottom_margin_px, left_margin_px, right_margin_px = self.get_px_margins()
        spacing_x_px = to_px(self.spacing_x)
        spacing_y_px = to_px(self.spacing_y)
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


    @classmethod
    def from_dict(cls, data: dict) -> "LayoutTemplate":

        page_size_id = data.get("page_size_id", QPageSize.Letter)
        page_size = QPageSize(QPageSize.PageSizeId(page_size_id))

        template = cls(
            pid=data["pid"],
            name=data.get("name", "Layout Template"),
            page_size = QPageSize.PageSizeId(data.get("page_size_id", QPageSize.Letter)),
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

    def save_to_file(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, path: str) -> "LayoutTemplate":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)