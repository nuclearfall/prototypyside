# component_template.py
from PySide6.QtCore import Qt, QObject, QRectF, QPointF, Signal # Import QObject and Signal
from PySide6.QtGui import QPainter, QPixmap, QColor, QImage, QBrush, QPen, QPainterPath, QPainterPathStroker
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QGraphicsPathItem
from typing import List, Dict, Any, Optional, Callable, TYPE_CHECKING
from enum import Enum, auto
import csv
import json
from pathlib import Path
from PySide6.QtWidgets import QMessageBox
from prototypyside.models.proto_paintable import ProtoPaintable
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.units.unit_str_helpers import geometry_with_px_pos, geometry_with_px_rect
from prototypyside.services.proto_registry import ProtoRegistry
from prototypyside.services.proto_class import ProtoClass
from prototypyside.utils.valid_path import ValidPath
from prototypyside.utils.render_context import RenderContext, RenderMode, RenderRoute, TabMode
from prototypyside.services.shape_factory import ShapeFactory

pc = ProtoClass

class ComponentTemplate(ProtoPaintable):
    template_changed = Signal()
    template_name_changed = Signal()
    item_z_order_changed = Signal()
    item_name_change = Signal()

    def __init__(
        self,
        proto:ProtoClass,
        pid: str,
        registry: ProtoRegistry,
        geometry: UnitStrGeometry = UnitStrGeometry(
            width="2.5in", height="3.5in"),
        name: Optional[str] = None,
        shape: str = "rounded_rect",
        file_path: Optional[Path] = None,
        csv_path: Optional[Path] = None,
        rotation: float = 0,
        parent: Optional[QGraphicsObject] = None,
    ):
        super().__init__(
            proto=proto, 
            pid=pid, 
            registry=registry,  
            geometry=geometry, 
            name=name, 
            parent=parent
        )
        self.tpid = None
        has_file_path = ValidPath.check(file_path, must_exist=True)
        has_csv_path = ValidPath.check(csv_path, must_exist=True)
        self._file_path = file_path
        self._csv_path = csv_path
        if has_file_path:
            self._name = ValidPath.file(self._file_path, stem=True)
        if has_csv_path:
            self._csv_path = ValidPath.file(self._file_path, stem=True)
        self._corner_radius = UnitStr(".125in", dpi=self._ctx.dpi)
        self._border_width = UnitStr(".125in", dpi=self._ctx.dpi)
        self._border_color = QColor(Qt.black)
        self._bg_color = QColor(Qt.white)
        # Children
        self.items: List[ComponentElement] = []

        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)

    @property
    def file_path(self):
        return self._file_path

    @file_path.setter
    def file_path(self, path):
        self._file_path = ValidPath.file(path, must_exist=True)

    @property
    def include_bleed(self) -> bool:
        return self._include_bleed

    @include_bleed.setter
    def include_bleed(self, val: bool):
        if val == self._include_bleed:
            return
        self._include_bleed = val                
        self.template_changed.emit()
        self.update()

    @property
    def border_z(self) -> float:
        return self._border_z

    @border_z.setter
    def border_z(self, z: float) -> None:
        self._border_z = float(z)
        self.update()

    @property
    def csv_path(self):
        return self._csv_path

    @csv_path.setter
    def csv_path(self, value):
        # normalize prior to comparison
        is_file = ValidPath.check(value, require_file=True)
        if str(value) != str(self._csv_path):
            self._csv_path = ValidPath.file(value, must_exist=True)
            self.template_changed.emit()
            self.update()

    def add_item(self, item):
        item.nameChanged.connect(self.item_name_change)
        if item.proto == pc.TE:
            item._component = self
        if item.pid in self.registry.orphans():
            self.registry.reinsert(item.pid)
        elif not self.registry.get(item.pid):
            self.registry.register(item)
        max_z = max([e.zValue() for e in self.items], default=0)
        item.setZValue(max_z + 100)
        item.ctx = self._ctx
        self.items.append(item)
        self.template_changed.emit()
        self.item_z_order_changed.emit()

    def remove_item(self, item: 'ComponentElement'):
        if item in self.items:
            self.items.remove(item)
            self.template_changed.emit()
            self.item_z_order_changed.emit()

    def clone(self, register=True, registry=None):
        this_reg = self.registry
        return this_reg.clone(self, register=register, registry=registry, component=True)

    def to_dict(self) -> Dict[str, Any]:
        sup_data = super().to_dict()
        data = {
            'tpid': self.tpid,
            'file_path': str(self._file_path),
            'items': [e.to_dict() for e in self.items],
            'csv_path': str(self.csv_path) if self.csv_path and Path(self.csv_path).exists else None,
            'tpid': self.tpid,
        }
        for key, (_, to_fn, default) in self._serializable_fields.items():
            val = getattr(self, f"_{key}", default)
            data[key] = to_fn(val) if (val is not None) else None

        return {**sup_data, **data}

    @classmethod
    def from_dict(
        cls,
        data: dict,
        registry: "ProtoRegistry",
        clone: bool = False
    ) -> "ComponentTemplate":
        # --- 1) PID & provenance ---
        # For clones we intentionally mint a new 'cc_<uuid>' and record the original PID as tpid.

        serial_pid = data.get("pid")
        proto = pc.from_prefix(serial_pid)
        if not serial_pid:
            raise ValueError(f"Invalid or missing pid for ComponentTemplate: {original_pid!r}")

        # --- 2) Geometry & core fields ---
        geom = UnitStrGeometry.from_dict(data["geometry"])

        inst = cls(
            proto=proto,
            pid=serial_pid,
            registry=registry,
            geometry=geom,
            name=data.get("name"),  # final naming is delegated to registry below
        )
        inst.tpid = data.get("tpid")
        # --- 4) File/CSV paths (robust but non-fatal) ---
        csv_path = data.get("csv_path")
        inst.csv_path = csv_path
        file_path = data.get("file_path")
        inst.file_path = file_path

        return inst

    # ---------------- rendering (single source of truth) ---------------- #

    def boundingRect(self) -> QRectF:
        base = self._geometry.to(self.ctx.unit, dpi=self.ctx.dpi).rect
        if self._include_bleed:
            base = base.outset(self._bleed, self._bleed)
        return QRectF(0, 0, base.width(), base.height())

