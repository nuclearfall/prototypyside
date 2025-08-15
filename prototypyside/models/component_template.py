# component_template.py
from PySide6.QtCore import Qt, QObject, QRectF, QPointF, Signal # Import QObject and Signal
from PySide6.QtGui import QPainter, QPixmap, QColor, QImage, QBrush, QPen, QPainterPath
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject
from typing import List, Dict, Any, Optional, Callable, TYPE_CHECKING
import csv
import json
from pathlib import Path
from PySide6.QtWidgets import QMessageBox
import weakref
import gc
import traceback
from prototypyside.services.shape_factory import ShapeFactory
from prototypyside.models.component_element import ComponentElement
from prototypyside.models.image_element import ImageElement
from prototypyside.models.text_element import TextElement
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.units.unit_str_helpers import geometry_with_px_pos, geometry_with_px_rect
from prototypyside.utils.proto_helpers import get_prefix, resolve_pid
# Use TYPE_CHECKING for type hinting
if TYPE_CHECKING:
    from prototypyside.services.proto_registry import ProtoRegistry


class ComponentTemplate(QGraphicsObject):
    template_changed = Signal()
    item_z_order_changed = Signal()
    item_name_change = Signal()

    def __init__(
        self,
        pid: str,
        geometry: UnitStrGeometry = UnitStrGeometry(width="2.5in", height="3.5in", unit="in", dpi=300),
        shape_factory: Callable[[QRectF], QPainterPath] = None,
        parent=None,
        name: Optional[str] = None,
        registry=None,
        shape="rounded_rectangle",
        corner_radius: UnitStr = UnitStr("0.125in", unit="in", dpi=300),
        border_width: UnitStr = UnitStr("0.125in", unit="in", dpi=300),
        bleed=UnitStr("0.125in", unit="in", dpi=300)
    ):
        super().__init__(parent)
        self.pid = pid
        self.tpid = None
        self._name = name
        self.registry = registry

        # Unit geometry
        self._geometry = geometry
        self._dpi = 300
        self._unit = "px"

        # Shape path generator
        self._shape_factory = shape_factory or self._default_shape_factory

        # Visual properties
        self._corner_radius = corner_radius
        self._border_width = border_width
        self._bleed = bleed
        self._include_bleed = False
        self._border_color = QColor(Qt.black)
        self._bg_color = QColor(Qt.white)
        self._background_image: Optional[Path] = None
        self._shape = QPainterPath  
        # Children
        self.items: List[ComponentElement] = []

        self.include_bleed = False
        self._csv_path = None
        self._bleed_rect: UnitStrGeometry = None

    # ——— Shape Factory ———
    def _default_shape_factory(self, rect: QRectF) -> QPainterPath:
        path = QPainterPath()
        radius = self._corner_radius.to(self._unit, dpi=self._dpi)
        if radius > 0:
            path.addRoundedRect(rect, radius, radius)
        else:
            path.addRect(rect)
        return path

    # ——— Properties & Setters ———
    @property
    def bleed(self):
        return self._bleed

    @bleed.setter
    def bleed(self, value):
        if value != self._bleed:
            self._bleed = value
            if self._include_bleed:
                self.prepareGeometryChange()
                self.setBleedRect()
                self.template_changed.emit()
                self.update()
    
    @property
    def bleed_rect(self):
        if not self._bleed_rect:
            self.setBleedRect()
        return self._bleed_rect
    
    @bleed_rect.setter
    def bleed_rect(self, values):
        if values == None:
            width = self._geometry.width + 2 * self._bleed
            height = self._geometry.height + 2 * self._bleed
        else:
            width, height = values
        self._bleed_rect = UnitStrGeometry(width=width, height=height, unit="in", dpi=self._dpi)
    
    def setBleedRect(self, values=None):
        if values == None:
            width = self._geometry.width + 2 * self._bleed
            height = self._geometry.height + 2 * self._bleed
        else:
            width, height = values
        self._bleed_rect = UnitStrGeometry(width=width, height=height, unit="in", dpi=self._dpi)
    
    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if value != self._name:
            self._name = value

    @property
    def dpi(self) -> int:
        return self._dpi

    @dpi.setter
    def dpi(self, new: int):
        if self._dpi != new:
            self._dpi = new
            for item in self.items:
                item.unit = self._unit

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
    def geometry(self):
        return self._geometry

    @geometry.setter
    def geometry(self, new_geom: UnitStrGeometry):
        if self._geometry == new_geom:
            return

        self.prepareGeometryChange()
        self._geometry = new_geom
        super().setPos(self._geometry.px.pos)
        if not self.tpid:
            self.template_changed.emit()
        self.setBleedRect()
        self.update()

    @property
    def width(self): return self._geometry.width

    @width.setter
    def width(self, value: UnitStr):
        if value != self._geometry.width:
            h = self._geometry.height
            self.geometry = UnitStrGeometry(width=value, height=height, unit=self._unit, dpi=self._dpi)

    @property
    def height(self): return self._geometry.height

    @height.setter
    def height(self, value: UnitStr):
        if value != self._geometry.height:
            w = self._geometry.width
            self.geometry = UnitStrGeometry(width=w, height=value, unit=self._unit, dpi=self._dpi)

    def setRect(self, new_rect: QRectF):
        # Do not emit signals here. setRect shouldn't be called directly.
        if self._geometry.px.rect == new_rect:
            return
        self.prepareGeometryChange()
        geometry_with_px_rect(self._geometry, new_rect, dpi=self.dpi)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        if change == QGraphicsItem.ItemPositionChange and value != self.pos():
            # Block signals to prevent a recursive loop if a connected item
            # also tries to set the position.
            signals_blocked = self.signalsBlocked()
            self.blockSignals(True)
            geometry_with_px_pos(self._geometry, value, dpi=self.dpi)
            self.blockSignals(signals_blocked)

        # If other signals are emitted or updates called for, it breaks the undo stack.
        return super().itemChange(change, value)

    # ——— Bounding Rect ———
    def boundingRect(self) -> QRectF:
        # Use pixel dimensions for scene, so convert geometry to pixels directly
        base_rect: QRectF = self._geometry.px.rect
        # Build the shape in pixel coords
        shape: QPainterPath = self._shape_factory(base_rect)
        if self._include_bleed:
            bleed_px = self._bleed.to("px", dpi=self._dpi)
            br = shape.boundingRect()
            return QRectF(
                br.x() - bleed_px,
                br.y() - bleed_px,
                br.width() + 2 * bleed_px,
                br.height() + 2 * bleed_px
            )
        return shape.boundingRect()

    # allows dynamic shape transformation of components
    @property
    def shape_factory(self) -> Callable[[QRectF], QPainterPath]:
        """Get or set the shape factory to change the component shape on the fly."""
        return self._shape_factory

    @shape_factory.setter
    def shape_factory(self, factory: Callable[[QRectF], QPainterPath]):
        if self._shape_factory == factory:
            return
        self.prepareGeometryChange()
        self._shape_factory = factory
        self.update()

    @property
    def include_bleed(self) -> bool:
        return self._include_bleed

    @include_bleed.setter
    def include_bleed(self, val: bool):
        val = bool(val)
        if val == self._include_bleed:
            return
        self.prepareGeometryChange()                 # boundingRect changes
        self._include_bleed = val
        # (Re)compute bleed rect if you keep that state, see item #3 below
        self.setBleedRect()                          # or skip if you compute on the fly
        self.template_changed.emit()
        self.update()


    @property
    def bg_color(self) -> QColor:
        return QColor(self._bg_color)

    @bg_color.setter
    def bg_color(self, val):
        if isinstance(val, QColor):
            c = val
        else:
            c = QColor(val)
        if c != self._bg_color:
            self._bg_color = c
            self.update()

    @property
    def background_image(self) -> Optional[str]:
        return str(self._background_image) if self._background_image else None

    @background_image.setter
    def background_image(self, path):
        if not path:
            self._background_image = None
        else:
            p = Path(path)
            self._background_image = p if p.exists() else None
        self.update()

    @property
    def border_width(self):
        return self._border_width

    @border_width.setter
    def border_width(self, value):
        if value != self._border_width:
            self._border_width = value
            self.update()

    @property
    def corner_radius(self):
        return self._corner_radius

    @corner_radius.setter
    def corner_radius(self, value: UnitStr):
        if value != self._corner_radius:
            self._corner_radius = value
            self.update()
    
    @property
    def csv_path(self):
        return self._csv_path

    @csv_path.setter
    def csv_path(self, value):
        if value != self._csv_path:
            try:
                path = Path(value)
                self._csv_path = path
                self.template_changed.emit()
                self.update()
            except Exception:
                self._csv_path = None

    def add_item(self, item):
        item.nameChanged.connect(self.item_name_change)
        
        if item.pid in self.registry.orphans():
            self.registry.reinsert(item.pid)
        elif not self.registry.get(item.pid):
            self.registry.register(item)
        max_z = max([e.zValue() for e in self.items], default=0)
        item.setZValue(max_z + 100)
        self.items.append(item)
        self.item_z_order_changed.emit()

    def remove_item(self, item: 'ComponentElement'):
        if item in self.items:
            self.items.remove(item)
            self.template_changed.emit()
            self.item_z_order_changed.emit()
            self.registry.deregister(item)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)

        # --- Get size in px, but anchor at (0,0) for local painting ---
        geom_px = self._geometry.px
        w = geom_px.rect.width()
        h = geom_px.rect.height()

        base_rect = QRectF(0.0, 0.0, w, h)                  # <<— local!
        shape = self._shape_factory(base_rect)

        # (1) Early-out: if not including the rect overlay, do the original no-bleed path
        if not self._include_bleed:
            # Background clipped to shape
            painter.save()
            painter.setClipPath(shape)
            painter.setPen(Qt.NoPen)
            if self._background_image:
                img = QImage(str(self._background_image))
                if not img.isNull():
                    painter.drawImage(shape.boundingRect(), img)
                else:
                    painter.fillPath(shape, QBrush(self._bg_color))
            else:
                painter.fillPath(shape, QBrush(self._bg_color))
            painter.restore()

            # Border fully inside base_rect
            if self._border_width.value > 0:
                thickness_px = self._border_width.to("px", dpi=self._dpi)
                half_thick = thickness_px * 0.5
                inner_rect = base_rect.adjusted(half_thick, half_thick, -half_thick, -half_thick)

                if isinstance(self._corner_radius, UnitStr):
                    orig_rad = self._corner_radius.to("px", dpi=self._dpi)
                else:
                    orig_rad = float(self._corner_radius)
                adj_rad = max(0.0, orig_rad - half_thick)

                if self._shape_factory == self._default_shape_factory:
                    border_shape = QPainterPath()
                    border_shape.addRoundedRect(inner_rect, adj_rad, adj_rad)
                else:
                    border_shape = self._shape_factory(inner_rect)

                painter.save()
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(self._border_color, thickness_px))
                painter.drawPath(border_shape)
                painter.restore()
            return

        # (2) Bleed pass (include_bleed) — ignore corner_radius for bleed fill
        if self._include_bleed:
            bleed_px = self._bleed.to("px", dpi=self._dpi)
            bleed_rect = QRectF(-bleed_px, -bleed_px, w + 2*bleed_px, h + 2*bleed_px)

            thickness_px = self._border_width.to("px", dpi=self._dpi)
            painter.save()
            painter.setPen(Qt.NoPen)
            if thickness_px > 0.0:
                painter.setBrush(QBrush(self._border_color))
                painter.drawRect(bleed_rect)                 # full-bleed flood
            else:
                if self._background_image:
                    img = QImage(str(self._background_image))
                    if not img.isNull():
                        painter.drawImage(bleed_rect, img)
                    else:
                        painter.fillRect(bleed_rect, QBrush(self._bg_color))
                else:
                    painter.fillRect(bleed_rect, QBrush(self._bg_color))
            painter.restore()

        # (3) Normal background clipped to the *base* shape
        painter.save()
        painter.setClipPath(shape)
        painter.setPen(Qt.NoPen)
        if self._background_image:
            img = QImage(str(self._background_image))
            if not img.isNull():
                painter.drawImage(shape.boundingRect(), img)
            else:
                painter.fillPath(shape, QBrush(self._bg_color))
        else:
            painter.fillPath(shape, QBrush(self._bg_color))
        painter.restore()

        # (4) Optional border fully inside base_rect
        if self._border_width.value > 0:
            thickness_px = self._border_width.to("px", dpi=self._dpi)
            half_thick = thickness_px * 0.5
            inner_rect = base_rect.adjusted(half_thick, half_thick, -half_thick, -half_thick)

            if isinstance(self._corner_radius, UnitStr):
                orig_rad = self._corner_radius.to("px", dpi=self._dpi)
            else:
                orig_rad = float(self._corner_radius)
            adj_rad = max(0.0, orig_rad - half_thick)

            if self._shape_factory == self._default_shape_factory:
                border_shape = QPainterPath()
                border_shape.addRoundedRect(inner_rect, adj_rad, adj_rad)
            else:
                border_shape = self._shape_factory(inner_rect)

            painter.save()
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(self._border_color, thickness_px))
            painter.drawPath(border_shape)
            painter.restore()

    def to_dict(self) -> Dict[str, Any]:
        data = {
            'pid': self.pid,
            'name': self.name,
            'geometry': self._geometry.to_dict(),
            'bg_color': self._bg_color.rgba(),
            'border_color': self._border_color.rgba(),
            'background_image': str(self.background_image) if self.background_image else None,
            'items': [e.to_dict() for e in self.items],
            'border_width': self.border_width.to_dict(),
            'corner_radius': self.corner_radius.to_dict(),
            'bleed': self._bleed.to_dict(),
            'csv_path': str(self.csv_path) if self.csv_path and Path(self.csv_path).exists else None,
            'tpid': self.tpid,
            'include_bleed': self._include_bleed,
            'bleed_rect': self.bleed_rect
        }
        return data

    @classmethod
    def from_dict(
        cls,
        data: dict,
        registry: "ProtoRegistry",
        is_clone: bool = False,
    ) -> "ComponentTemplate":
        # 1) Core properties & PID

        pid = resolve_pid("cc") if is_clone else data["pid"]
        geom = UnitStrGeometry.from_dict(data["geometry"])
        inst = cls(
            pid=pid,
            registry=registry,
            geometry=geom,
            name=data.get("name"),
            border_width=UnitStr.from_dict(data.get("border_width")),
            corner_radius=UnitStr.from_dict(data.get("corner_radius")),
            bleed=UnitStr.from_dict(data.get("bleed"))
        )
        inst.tpid = data.get("pid") if is_clone else None
        csv_path = data.get("csv_path")
        inst.csv_path = Path(csv_path) if csv_path else None
        bg_color = data.get("bg_color", None)
        border_color = data.get("border_color", None)
        bleed = data.get("bleed")
        inst.bleed = UnitStr.from_dict(data.get("bleed")) if bleed else UnitStr("0.125 in", "in", dpi=300)
        inst.include_bleed = data.get("include_bleed", False)
        inst.setBleedRect()
        inst._bg_color = QColor.fromRgba(bg_color) if bg_color else None
        inst._border_color = QColor.fromRgba(border_color) if border_color else None
        registry.register(inst)
        inst.name = registry.generate_name(inst)
        # 3) Child elements (images/text)
        inst.items = []
        for e in data.get("items", []):
            prefix = get_prefix(e.get("pid"))
            if prefix == "ie":
                el = ImageElement.from_dict(e, registry=registry, is_clone=is_clone)
            elif prefix == "te":
                el = TextElement.from_dict(e, registry=registry, is_clone=is_clone)
            elif prefix == "ve":
                from prototypyside.models.vector_element import VectorElement
                el = VectorElement.from_dict(e, registry=registry, is_clone=is_clone)
            else:
                raise ValueError(f"Unknown prefix {prefix}")
            inst.add_item(el)
            el.setParentItem(inst)

            
        return inst
