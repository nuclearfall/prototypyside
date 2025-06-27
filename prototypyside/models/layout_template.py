from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
import json
from PySide6.QtWidgets import QGraphicsObject
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QPageSize, QPainter, QPixmap, QColor, QImage, QPen, QBrush
from prototypyside.utils.unit_converter import to_px, page_in_px, page_in_units, compute_scale_factor
from prototypyside.utils.unit_str import UnitStr
@dataclass
class LayoutSlot:
    position: List[float]      # [x, y] in scene coordinates
    component_pid: Optional[str] = None

    def __init__(self, pid, tpid, cpid=None):
        self.pid = pid
        self.tpid = tpid
        self.cpid = cpid

    def to_dict(self) -> Dict:
        return {
            "pid"
            "position": self.position,
            "scale": self.scale,
            "slot_id": self.slot_id,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "LayoutSlot":
        return cls(
            position=list(data.get("position", [0.0, 0.0])),
            rotation=data.get("rotation", 0.0),
            scale=data.get("scale", 1.0),
            slot_id=data.get("slot_id"),
        )


class LayoutTemplate(QGraphicsObject):
    marginsChanged = Signal()
    spacingChanged = Signal()
    export_quantity: Optional[int] = None     # Override for copies per slot
    def __init__(self, pid, registry, parent=None, 
                page_size=QPageSize(QPageSize.Letter), 
                rows=3, cols=3, dpi=300, unit="in", 
                name=None, margin_top="0.5in", margin_bottom = "0.5in",
                margin_left = "0.25in", margin_right = "0.25in",
                spacing_x = "0.0in", spacing_y  = "0.0in"):
        super().__init__(parent)
        self.pid = pid
        self.name = name
        self.registry = registry
        self.page_size = page_size
        self.unit = unit
        self.dpi = dpi
        self._margin_top = UnitStr(margin_top, unit=unit, dpi=dpi)
        self._margin_bottom = UnitStr(margin_bottom, unit=unit, dpi=dpi)
        self._margin_left = UnitStr(margin_left, unit=unit, dpi=dpi)
        self._margin_right = UnitStr(margin_right, unit=unit, dpi=dpi)
        self._spacing_x = UnitStr(spacing_x, unit=unit, dpi=dpi)
        self._spacing_y = UnitStr(spacing_y, unit=unit, dpi=dpi)
        self.rows = rows
        self.columns = cols 
        self.layout_slots: List[List[str]] = None
        self.expand_grid


    @property
    def margin_top(self):
        return self._margin_top

    @margin_top.setter
    def margin_top(self, value):
        if isinstance(value, UnitStr):
            self._margin_top = value
        else:
            self._margin_top = UnitStr(value, unit=self._margin_top.unit, dpi=self._margin_top.dpi)
        self.marginsChanged.emit()
        self.update()

    @property
    def margin_bottom(self):
        return self._margin_bottom

    @margin_bottom.setter
    def margin_bottom(self, value):
        if isinstance(value, UnitStr):
            self._margin_bottom = value
        else:
            self._margin_bottom = UnitStr(value, unit=self._margin_bottom.unit, dpi=self._margin_bottom.dpi)
        self.marginsChanged.emit()
        self.update()

    @property
    def margin_left(self):
        return self._margin_left

    @margin_left.setter
    def margin_left(self, value):
        if isinstance(value, UnitStr):
            self._margin_left = value
        else:
            self._margin_left = UnitStr(value, unit=self._margin_left.unit, dpi=self._margin_left.dpi)
        self.marginsChanged.emit()
        self.update()

    @property
    def margin_right(self):
        return self._margin_right

    @margin_right.setter
    def margin_right(self, value):
        if isinstance(value, UnitStr):
            self._margin_right = value
        else:
            self._margin_right = UnitStr(value, unit=self._margin_right.unit, dpi=self._margin_right.dpi)
        self.marginsChanged.emit()
        self.update()

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
        self.update()

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
        self.update()

    def get_margins(self):
        return self._margin_top, self._margin_bottom, self._margin_left, self._margin_right

    @property
    def rect(self):
        return self.get_page_rect()

    @property
    def settings(self):
        return self.dpi, self.unit

    @settings.setter
    def settings(self):
        self.dpi = self.registry.settings.dpi
        self.unit = self.registry.settings.unit

    def get_page_rect(self) -> "QRectF":
        size = self.page_size
        w, h = page_in_px(size, self.dpi)
        rect = QRectF(0, 0, w, h)
        return rect

    def boundingRect(self):
        return self.get_page_rect()

    ### Grid manipulation ###

    def setGrid(self, rows: int, columns: int) -> None:
        """
        Resize the grid to exactly (target_rows × target_columns).
        Expands first (creating new slots), then contracts (deregistering extras).
        """
        # 1️⃣ Expand as needed
        self.expand_grid(
            self.registry,
            new_rows=target_rows,
            new_columns=target_columns
        )

        # 2️⃣ Contract as needed
        self.contract_grid(
            self.registry,
            new_rows=target_rows,
            new_columns=target_columns
        )

    def expand_grid(self, new_rows: Optional[int] = None, new_columns: Optional[int] = None) -> None:
        """
        Grow to at least new_rows × new_columns, creating real LayoutSlot
        items via the self.registry and positioning them.
        """
        # ensure our 2D list exists
        if self.layout_slots is None:
            self.layout_slots = []

        old_rows, old_cols = self.rows, self.columns
        target_rows = max(self.rows, new_rows or self.rows)
        target_cols = max(self.columns, new_columns or self.columns)

        # 1. add new rows
        for r in range(old_rows, target_rows):
            self.layout_slots.append([])
            for c in range(target_cols):
                slot = self.registry.create("ls", tpid=self.pid, parent=self)
                self.layout_slots[r].append(slot.pid)

        # 2. expand existing rows with new columns
        for r in range(min(old_rows, target_rows)):
            row_list = self.layout_slots[r]
            for c in range(old_cols, target_cols):
                slot = self.registry.create("ls", tpid=self.pid, parent=self)
                row_list.append(slot.pid)

        # 3. update dimensions
        self.rows, self.columns = target_rows, target_cols

        # 4. reposition everything
        for r in range(self.rows):
            for c in range(self.columns):
                pid = self.layout_slots[r][c]
                slot_obj = self.registry.get(pid)
                x_px, y_px = self.get_slot_position_px(r, c)
                slot_obj.setPos(QPointF(x_px, y_px))

    def shrink_grid(self, new_rows: Optional[int] = None, new_columns: Optional[int] = None) -> None:
        """
        Shrink to at most new_rows × new_columns, deregistering any
        dropped LayoutSlot items, and repositioning the remainder.
        """
        if not self.layout_slots:
            return

        old_rows, old_cols = self.rows, self.columns
        target_rows = min(self.rows, new_rows or self.rows)
        target_cols = min(self.columns, new_columns or self.columns)

        # 1. drop extra rows
        for _ in range(old_rows - target_rows):
            removed = self.layout_slots.pop()
            for pid in removed:
                self.registry.deregister(pid)

        # 2. drop extra cols in remaining rows
        for row_list in self.layout_slots:
            for _ in range(old_cols - target_cols):
                pid = row_list.pop()
                self.registry.deregister(pid)

        # 3. update dimensions
        self.rows, self.columns = target_rows, target_cols

        # 4. reposition everything
        for r in range(self.rows):
            for c in range(self.columns):
                pid = self.layout_slots[r][c]
                slot_obj = self.registry.get(pid)
                x_px, y_px = self.get_slot_position_px(r, c)
                slot_obj.setPos(QPointF(x_px, y_px))


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

    def get_slot_position_px(self, row: int, col: int) -> tuple[float, float]:
        rect = self.get_page_rect()
        cell_w, cell_h = self.get_cell_size_px()
        spacing_x = to_px(self.spacing_x)
        spacing_y = to_px(self.spacing_y)
        top, bottom, left, right = self.get_px_margins()

        x = rect.left() + left + col * (cell_w + spacing_x)
        y = rect.top() + top + row * (cell_h + spacing_y)
        return x, y

    def get_slot_at_position(self, scene_pos: QPointF) -> Tuple[Optional[str], Optional[QPointF]]:
        """
        Given a scene-coordinate point, return the (slot_pid, slot_origin)
        whose rect contains it, or (None, None) if no slot matches.
        """
        # uniform slot size in pixels
        cell_w, cell_h = self.get_cell_size_px()

        for row in range(self.rows):
            for col in range(self.columns):
                # slot’s top-left in px
                x_px, y_px = self.get_slot_position_px(row, col)
                slot_rect = QRectF(x_px, y_px, cell_w, cell_h)

                if slot_rect.contains(scene_pos):
                    # now index into the 2D list
                    slot_pid = None
                    if self.layout_slots and len(self.layout_slots) > row:
                        slot_row = self.layout_slots[row]
                        if len(slot_row) > col:
                            slot_pid = slot_row[col]
                    return slot_pid, QPointF(x_px, y_px)

        return None, None

    def slot_positions_map(self) -> Dict[str, QPointF]:
        """
        Return a mapping from each slot’s pid to its origin in scene coords.
        Slots with a None pid are skipped.
        """
        positions: Dict[str, QPointF] = {}
        for row in range(self.rows):
            for col in range(self.columns):
                # look up the pid in our 2D list
                pid = None
                if self.layout_slots and len(self.layout_slots) > row:
                    row_list = self.layout_slots[row]
                    if len(row_list) > col:
                        pid = row_list[col]

                # only include real slots
                if not pid:
                    continue

                # compute its top-left in scene px
                x_px, y_px = self.get_slot_position_px(row, col)
                positions[pid] = QPointF(x_px, y_px)

        return positions

    def get_slot_dimensions_px(self) -> Tuple[float, float]:
        """
        Returns (width_px, height_px) of each slot based on current
        rows, columns, margins, and spacing.
        """
        return self.get_cell_size_px()  # cell_w, cell_h 

    def get_slot_rect_px(self, row: int, col: int) -> QRectF:
        """
        Returns the QRectF (in scene coords) occupied by the slot at (row, col).
        """
        x_px, y_px = self.get_slot_position_px(row, col)
        w_px, h_px = self.get_slot_dimensions_px()
        return QRectF(x_px, y_px, w_px, h_px)

    def get_cell_size_px(self) -> tuple[float, float]:
        rect = self.get_page_rect()
        rows, cols = self.rows, self.columns
        spacing_x = to_px(self.spacing_x)
        spacing_y = to_px(self.spacing_y)
        margins = self.get_px_margins()
        
        total_w = rect.width() - margins[2] - margins[3] - spacing_x * (cols - 1)
        total_h = rect.height() - margins[0] - margins[1] - spacing_y * (rows - 1)
        
        return total_w / cols, total_h / rows

    def resize_component(self, component_instance) -> float:
        slot_w, slot_h = self.get_cell_size_px()
        inst_rect = component_instance.boundingRect()
        cur_w, cur_h = inst_rect.width(), inst_rect.height()

        scale = compute_scale_factor((slot_w, slot_h), (cur_w, cur_h))
        component_instance.setScale(scale)
        return scale

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
        print(f"Page Size enum value {page_size_id}")   

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.boundingRect()
        
        # Add a print statement to confirm this method is being called
        print(f"LayoutTemplate::paint called for rect: {rect}")

        # The main background of the page item should be transparent
        # to allow the scene's background (where the grid is drawn) to show through.
        painter.setBrush(Qt.transparent)  # <-- CRITICAL FIX
        painter.setPen(QPen(Qt.black, 2))
        painter.drawRect(self.boundingRect())
        top_margin_px, bottom_margin_px, left_margin_px, right_margin_px = self.get_px_margins()
        spacing_x_px = to_px(self.spacing_x)
        spacing_y_px = to_px(self.spacing_y)
        rows = self.rows
        cols = self.columns
        # --- IMPORTANT: Remove the grid cell filling logic from here ---
        # If the scene's drawBackground is responsible for the grid,
        # the LayoutTemplate item should NOT draw opaque grid cells that cover it.
        # Remove these lines:
        # painter.setPen(QPen(Qt.darkGray, 3.0))
        # painter.setBrush(QBrush(QColor(240, 240, 240, 255)))

        total_w = rect.width() - left_margin_px - right_margin_px - spacing_x_px * (cols - 1)
        total_h = rect.height() - top_margin_px - bottom_margin_px - spacing_y_px * (rows - 1)

        cell_w = total_w / cols
        cell_h = total_h / rows

        painter.setPen(QPen(Qt.black, 2.0))
        for r in range(rows):
            for c in range(cols):
                x = rect.left() + left_margin_px + c * (cell_w + spacing_x_px)
                y = rect.top() + top_margin_px + r * (cell_h + spacing_y_px)
                painter.drawRect(QRectF(x, y, cell_w, cell_h))

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