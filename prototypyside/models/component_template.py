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
from prototypyside.services.shape_factory import ShapeFactory
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.units.unit_str_helpers import geometry_with_px_pos, geometry_with_px_rect
from prototypyside.services.proto_registry import ProtoRegistry
from prototypyside.services.proto_class import ProtoClass
from prototypyside.utils.valid_path import ValidPath
from prototypyside.utils.render_context import RenderContext, RenderMode, RenderRoute, TabMode
from prototypyside.utils.rotatable_mixin import RotatableMixin



SHAPES = {
    "rect":             ShapeFactory.rect,
    "rounded_rect":     ShapeFactory.rounded_rect,
    "oval":             ShapeFactory.oval,
    "hexagon":          ShapeFactory.hexagon,
    "diamond":          ShapeFactory.diamond,
    "octagon":          ShapeFactory.octagon,
    "polygon":          ShapeFactory.polygon,
    "default":          None
}

class ComponentTemplate(QGraphicsObject, RotatableMixin):
    template_changed = Signal()
    template_name_changed = Signal()
    item_z_order_changed = Signal()
    item_name_change = Signal()

    def __init__(
        self,
        proto:ProtoClass,
        pid: str,
        registry: ProtoRegistry,
        geometry: UnitStrGeometry = None,
        name: Optional[str] = None,
        shape: str = "oval",
        file_path: Optional[Path] = None,
        csv_path: Optional[Path] = None,
        rotation: float = 0,
        parent: Optional[QGraphicsObject] = None,
    ):
        super().__init__(parent)

        SHAPES["default"] = self._default_shape_factory
        self.pid = pid
        self.tpid = None
        self._registry = registry

        self._name = name
        self._file_path = ValidPath.file(file_path, must_exist=True)
        if self._file_path:
            self._name = ValidPath.file(self._file_path, stem=True)
        self._name = registry.validate_name(proto, name)

        self._dpi = registry.settings.dpi
        self._ldpi = registry.settings.ldpi
        self._unit = "px"

        # Unit geometry
        self._geometry = geometry or UnitStrGeometry(width="2.5in", height="3.5in", unit="in", dpi=self._dpi)
        self._rotation = rotation or 0
        # Visual properties
        self._corner_radius = UnitStr("0.0 in", unit="in", dpi=self.dpi)
        self._border_width = UnitStr("0.125in", unit="in", dpi=self.dpi)
        self._border_color = QColor(Qt.black)

        self._bg_color = QColor(Qt.transparent)
        self._bg_image: Optional[Path] = None
        self._bg_qimage: Optional[QImage] = None

        self._bleed = UnitStr("0.125in", unit="in", dpi=self.dpi)
        self._bleed_rect: UnitStrGeometry = self.setBleedRect(self._geometry)
        self._include_bleed = False
        self._context = RenderContext(
            mode=RenderMode.GUI,
            tab_mode=TabMode.COMPONENT,
            route=RenderRoute.COMPOSITE,
            dpi=self.dpi
        )
        # Shape path generator
        self._shape = shape
        self._sides = None # If set to four this is a diamond shape
        self._shape_factory = SHAPES.get(self._shape)
        # shape_factory or self._default_shape_factory   # store callable (bound method)
        if self._sides:  
            self._shape_factory = SHAPES.get(self._shape)

        # Children
        self.items: List[ComponentElement] = []

        # Paths
        self._csv_path = None

        # Rendering configuration
        self.render_mode: RenderMode = RenderMode.GUI
        self.tab_mode: TabMode = TabMode.COMPONENT
        self.render_route: RenderRoute = RenderRoute.COMPOSITE

        # Border item/z (drawn above elements by default)
        # self._border_pen = QPen(Qt.black, 1.0)  # adjust if you already have one
        self._border_z: float = 10_000.0

        # Create a separate border item that will always be on top
        self._border_item = QGraphicsPathItem(self)
        self._border_item.setZValue(self._border_z)
        self._border_item.setVisible(True)
        # Clipping: ComponentTab GUI must NOT clip children
        # LayoutTab GUI renders via raster image in LayoutSlot (so this flag is irrelevant there)
        self.setFlag(QGraphicsItem.ItemClipsChildrenToShape, False)

    # ---- Rotation: delegate to RotatableMixin but emit Qt signals and fix bounds ----
    @property
    def rotation(self) -> float:
        # single source of truth; also mirrors RotatableMixin’s _rotation_deg
        return float(getattr(self, "_rotation", 0.0))

    @rotation.setter
    def rotation(self, degrees: float) -> None:
        import math
        deg = float(degrees) % 360.0
        if math.isclose(deg, getattr(self, "_rotation", 0.0), abs_tol=1e-7):
            return

        # boundingRect/shape depend on rotation; notify scene
        self.prepareGeometryChange()

        # write both so RotatableMixin helpers (if used) see the same value
        self._rotation = deg

        # GUI path (QGraphicsItem) uses the item’s native rotation
        # Offscreen/export paths will be handled by your render wrapper (if using RotatableMixin)
        self.setRotation(deg)

        self.rotationChanged.emit(deg)
        self.update()


    def _default_shape_factory(self) -> QPainterPath:
        return SHAPES.get("rounded_rect")

    # ——— Properties & Setters ———
    @property
    def registry(self):
      return self._registry

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
        self.setBleedRect(values)

    def setBleedRect(self, values=None):
        if values == None:
            width = self._geometry.width + 2 * self._bleed
            height = self._geometry.height + 2 * self._bleed
        else:
            width = values.inch.rect.width()
            height = values.inch.rect.height()
        self._bleed_rect = UnitStrGeometry(width=width, height=height, unit="in", dpi=self._dpi)
    
    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if value != self._name:
            self._name = value
            self.template_name_changed.emit()
            
    @property
    def ldpi(self) -> int:
      return self._ldpi

    @ldpi.setter
    def ldpi(self, new: int):
      if self._ldpi != new:
          self._ldpi = new
          self.update()

    @property
    def dpi(self) -> int:
        return self._dpi

    @dpi.setter
    def dpi(self, new: int):
        if self._dpi != new:
            self._dpi = new
            self.update()

    @property
    def unit(self) -> str:
        return self._unit

    @unit.setter
    def unit(self, new: str):
        if self._unit != new:
            self._unit = new

    @property
    def geometry(self):
        return self._geometry

    @geometry.setter
    def geometry(self, new_geom: UnitStrGeometry):
        if self._geometry == new_geom:
            return
        self.prepareGeometryChange()
        rect = self._geometry.to(self.unit, dpi=self.dpi).rect
        # self.setTransformOriginPoint(rect.center())
        self._geometry = new_geom
        if not self.tpid:
            self.template_changed.emit()
        self.setBleedRect()
        # self._update_border_path()
        self.update()

    def setRect(self, new_rect: QRectF):
        # Do not emit signals here. setRect shouldn't be called directly.
        if self._geometry.to(self.unit, dpi=self.dpi).rect == new_rect:
            return
        self.prepareGeometryChange()
        geometry_with_px_rect(self._geometry, new_rect, dpi=self.dpi)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        if change == QGraphicsItem.ItemPositionChange and value != self.pos():
            print(f"Something is attempting to change the position of the template")
            # Block signals to prevent a recursive loop if a connected item
            # also tries to set the position.
            signals_blocked = self.signalsBlocked()
            self.blockSignals(True)
            # geometry_with_px_pos(self._geometry, value, dpi=self.dpi)
            self.blockSignals(signals_blocked)

        # If other signals are emitted or updates called for, it breaks the undo stack.
        return super().itemChange(change, value)

    @property
    def file_path(self):
        return self._file_path

    @file_path.setter
    def file_path(self, path):
        self._file_path = ValidPath.file(path, must_exist=True)

    @property
    def shape(self):
        return self._shape

    @shape.setter
    def shape(self, s):
        if s != self._shape and s in SHAPES:
            self._shape = s
            self.shape_factory = SHAPES.get(s)
            # self._update_border_path()
            # self._update_border_style()    

    @property
    def shape_factory(self) -> Callable[[UnitStrGeometry], QPainterPath]:
        return self._shape_factory

    @shape_factory.setter
    def shape_factory(self, factory: Callable[[UnitStrGeometry], QPainterPath]) -> None:
        if self._shape_factory is factory:
            return
        self.prepareGeometryChange()
        self._shape_factory = factory
        self.update()

    def shape_path(self) -> QPainterPath:
        geom = self._geometry
        factory = self._shape_factory or self._default_shape_factory
        extra = None
        if self._shape == "rounded_rect":
            extra = self._corner_radius
        elif self._shape == "polygon":
            extra = self._sides
        path = factory(self._geometry, unit=self.unit, extra=extra)
        path.setFillRule(Qt.WindingFill)
        return path

    def bleed_path(self) -> QPainterPath:
        factory = self._shape_factory or self._default_shape_factory

        # Prepare extra param for rounded_rect / polygon
        extra = None
        if self._shape == "rounded_rect":
            # Previous behavior increased corner radius by bleed amount.
            # Compute in the current unit so physical export stays exact.
            cr = float(self._corner_radius.to(self.unit, dpi=self.dpi))
            b  = float(self._bleed.to(self.unit, dpi=self.dpi))
            extra = UnitStr(f"{max(0.0, cr + b)}{self.unit}", unit=self.unit, dpi=self.dpi)
        elif self._shape == "polygon":
            extra = self._sides

        # Use the precomputed UnitStrGeometry for bleed
        path = factory(self.bleed_rect, unit=self.unit, extra=extra)
        path.setFillRule(Qt.WindingFill)
        return path

    @property
    def include_bleed(self) -> bool:
        return self._include_bleed

    @include_bleed.setter
    def include_bleed(self, val: bool):
        val = bool(val)
        if val == self._include_bleed:
            return
        self.prepareGeometryChange()
        self._include_bleed = val
        # (Re)compute bleed rect if you keep that state
        self.setBleedRect()                      
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
    def bg_image(self) -> Optional[str]:
        return self._bg_image

    @bg_image.setter
    def bg_image(self, path):
        print(f"Image path is being set to {path}")
        new_path = ValidPath.file(path, must_exist=True)
        if new_path:
            self._bg_qimage = QImage(str(path))
            self._bg_image = new_path
            # Invalidate cache so we reload next paint
            self.update()
        else:
            self._bg_image = None
            self._bg_qimage = None

    @property
    def border_z(self) -> float:
        return self._border_z

    @border_z.setter
    def border_z(self, z: float) -> None:
        self._border_z = float(z)
        if self._border_item:
            self._border_item.setZValue(self._border_z)

    @property
    def border_width(self):
        return self._border_width

    @border_width.setter
    def border_width(self, value):
        if value != self._border_width:
            self._border_width = value
            # self._update_border_style()
            # self._update_border_path()
            self.update()

    @property
    def corner_radius(self):
        return self._corner_radius

    @property
    def border_color(self): return self._border_color

    @border_color.setter
    def border_color(self, color):
        if color != self._border_color:
            self._border_color = color
    
    @corner_radius.setter
    def corner_radius(self, value: UnitStr):
        if value != self._corner_radius:
            self._corner_radius = value
            self.prepareGeometryChange()
            # self._update_border_path()
            self.update()

    @property
    def context(self) -> RenderContext: return self._context

    @context.setter
    def context(self, new) -> None:
        for el in self.items:
            el.context = new

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
        if item.proto == ProtoClass.TE:
            item._component = self
        if item.pid in self.registry.orphans():
            self.registry.reinsert(item.pid)
        elif not self.registry.get(item.pid):
            self.registry.register(item)
        max_z = max([e.zValue() for e in self.items], default=0)
        item.setZValue(max_z + 100)
        item.context = self._context
        self.items.append(item)
        self.template_changed.emit()
        self.item_z_order_changed.emit()

    def remove_item(self, item: 'ComponentElement'):
        if item in self.items:
            self.items.remove(item)
            self.template_changed.emit()
            self.item_z_order_changed.emit()

    def clone(self):
        registry = self.registry
        return registry.clone(self)

    def to_dict(self) -> Dict[str, Any]:
        self.setBleedRect()
        data = {
            'pid': self.pid,
            'tpid': self.tpid,
            'file_path': str(self._file_path),
            'name': self.name,
            'geometry': self._geometry.to_dict(),
            'bg_color': self._bg_color.rgba(),
            'border_color': self._border_color.rgba(),
            'bg_image': str(self.bg_image) if self.bg_image else None,
            'items': [e.to_dict() for e in self.items],
            'border_width': self.border_width.to_dict(),
            'corner_radius': self.corner_radius.to_dict(),
            'bleed': self._bleed.to_dict(),
            'csv_path': str(self.csv_path) if self.csv_path and Path(self.csv_path).exists else None,
            'tpid': self.tpid,
            'include_bleed': self._include_bleed,
            'shape': self._shape,
            'sides': self._sides,
        }
        return data

    @classmethod
    def from_dict(
        cls,
        data: dict,
        registry: "ProtoRegistry",
    ) -> "ComponentTemplate":
        # --- 1) PID & provenance ---
        # For clones we intentionally mint a new 'cc_<uuid>' and record the original PID as tpid.
        from prototypyside.services.proto_class import ProtoClass  # Enum with PID helpers

        serial_pid = data.get("pid")
        if not serial_pid:
            raise ValueError(f"Invalid or missing pid for ComponentTemplate: {original_pid!r}")

        # --- 2) Geometry & core fields ---
        geom = UnitStrGeometry.from_dict(data["geometry"])

        inst = cls(
            proto=ProtoClass.CT,
            pid=serial_pid,
            registry=registry,
            geometry=geom,
            name=data.get("name"),  # final naming is delegated to registry below
        )
        inst.tpid = data.get("tpid")
        inst.border_width = UnitStr.from_dict(data.get("border_width"))
        inst.corner_radius = UnitStr.from_dict(data.get("corner_radius"))
        inst.bleed = UnitStr.from_dict(data.get("bleed")) or UnitStr("0.125 in", "in", dpi=300)
        inst.shape = data.get("shape")
        inst.sides = data.get("sides")
        # --- 3) Optional colors ---
        bg_color = data.get("bg_color")
        border_color = data.get("border_color")
        inst.bg_color = QColor.fromRgba(bg_color) if bg_color is not None else None
        inst.border_color = QColor.fromRgba(border_color) if border_color is not None else None
        inst.bg_image = data.get("bg_image")
        # --- 4) File/CSV paths (robust but non-fatal) ---
        csv_path = data.get("csv_path")
        inst.csv_path = csv_path

        file_path = data.get("file_path")
        inst.file_path = file_path

        # Compute bleed rect after bleed is set
        inst.setBleedRect()

        return inst

    # ---------------- rendering (single source of truth) ---------------- #

    def boundingRect(self) -> QRectF:
        base = (self._bleed_rect if self._include_bleed else self._geometry).to(self.unit, dpi=self.dpi).rect
        return QRectF(0, 0, base.width(), base.height())

    def paint(self, painter: QPainter, option, widget=None):
        # Scene path (ComponentTab). LayoutSlot will call to_raster_image instead.
        self.render(painter, self._context)

    def render(self, painter: QPainter, context: RenderContext) -> None:
        """
        Single rendering entry point used by both scene painting and offscreen raster/export.
        """
        rect_px = self._geometry.to(self.unit, dpi=self.dpi).rect

        # 0) Bleed behind everything
        if self._include_bleed:
            self._paint_bleed(painter)

        # 1) Background (color + optional image), clipped to shape
        self._paint_background(painter, rect_px)

        # 2) Let ELements paint themselves
        clip_elements = not (context.is_component_tab and context.is_gui)
        self._paint_elements(painter, context, clip=clip_elements)

        # 3) Border on top (inside the shape)
        self._paint_border(painter)

    def to_raster_image(self, context: RenderContext) -> QImage:
        size_px = self._geometry.to(self.unit, dpi=self.dpi).size
        w = max(1, int(round(size_px.width())))
        h = max(1, int(round(size_px.height())))

        img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)

        p = QPainter(img)
        p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform, True)
        self.render(p, context)
        p.end()
        return img


    # ---------------- paint helpers ---------------- #

    def _paint_bleed(self, painter: QPainter):
        path = self.bleed_path()
        painter.save()
        fill_color = self._border_color if self._border_width.to(self.unit, dpi=self.dpi) > 0 else self._bg_color
        if fill_color is not None:
            painter.fillPath(path, QBrush(fill_color))
        painter.restore()

    def _paint_border(self, painter: QPainter):
        bw = float(self._border_width.to(self.unit, dpi=self.dpi))
        if bw <= 0:
            return
        rect = self._geometry.to(self.unit, dpi=self.dpi).rect
        inner_rect = rect.adjusted(bw/2, bw/2, -bw/2, -bw/2)
        if self._shape == "oval":
            bw = self.border_width.to(self.unit, dpi=self.dpi)
            inner_geom = UnitStrGeometry(rect=inner_rect, unit=self.unit, dpi=self.dpi)
            inner_path = SHAPES["oval"](inner_geom, unit=self.unit, extra=None)
            if inner_rect.width() <= 0 or inner_rect.height() <= 0:
                # too thick to fit — just fill the oval with border color
                painter.save()
                painter.setPen(Qt.NoPen)
                painter.setBrush(self._border_color)
                painter.drawPath(self.shape_path())
                painter.restore()
                return

            stroker = QPainterPathStroker()
            stroker.setWidth(bw)
            stroker.setJoinStyle(Qt.RoundJoin)
            stroker.setCapStyle(Qt.RoundCap)
            band = stroker.createStroke(inner_path)

            painter.save()
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setPen(Qt.NoPen)
            painter.setBrush(self._border_color)
            painter.drawPath(band)
            painter.restore()
            return

        # Default (non-oval): keep your stroke-based inner-path logic
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(self._border_color)
        pen.setWidthF(bw)                  # width in the same local units as rect
        pen.setJoinStyle(Qt.MiterJoin)
        # IMPORTANT: do NOT set cosmetic here for export; we want physical width.
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(rect)
        painter.restore()

    def _paint_background(self, painter: QPainter, rect: QRectF):
        path = self.shape_path()
        painter.save()
        # Fill color
        if self._bg_color is not None:
            painter.fillPath(path, self._bg_color)
        # Image (if any) – clipped to shape and scaled to rect
        if self._bg_qimage is not None:
            painter.setClipPath(path, Qt.ReplaceClip)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            painter.drawImage(rect, self._bg_qimage)
        painter.restore()

    def _inner_border_path(self) -> QPainterPath:
        bw = float(self._border_width.to(self.unit, dpi=self.dpi))
        inset = bw * 0.5 if bw > 0 else 0.0
        inner_rect = self._geometry.to(self.unit, dpi=self.dpi).rect.adjusted(inset, inset, -inset, -inset)
        inner_geom = UnitStrGeometry(rect=inner_rect, unit=self.unit, dpi=self.dpi)
        extra = None
        factory = self._shape_factory
        if self._shape == "rounded_rect":
            extra = self._corner_radius
        elif self._shape == "oval":
            extra = self._sides
        path = factory(inner_geom, unit=self.unit, extra=extra)
        path.setFillRule(Qt.WindingFill)
        return path

    def _paint_elements(self, painter: QPainter, context: RenderContext, *, clip: bool):
        if not self.items:
            return

        # Optional clipping to main shape for LayoutTab or Export
        shape = self.shape_path()
        if clip:
            painter.save()
            painter.setClipPath(shape, Qt.IntersectClip)

        # Draw children deterministically by z (ascending)
        for el in sorted(self.items, key=lambda e: e.zValue()):
            painter.save()
            
            # Get element's position relative to the component
            try:
                # Convert element geometry to component's unit and DPI
                el_geom = el.geometry.to(self.unit, dpi=self.dpi)
                el_pos = el_geom.pos
                
                # Translate to element's position relative to component origin
                painter.translate(el_pos)
                
                # Apply element rotation
                try:
                    rot = float(getattr(el, "rotation", 0.0))
                    painter.rotate(rot)
                except Exception:
                    pass

                # Prefer custom render if element provides it; otherwise fallback to paint
                try:
                    # Create a temporary transform for the element to render at (0,0)
                    temp_geom = UnitStrGeometry(
                        width=el_geom.size.width(),
                        height=el_geom.size.height(),
                        x=0, y=0,
                        unit=self.unit,
                        dpi=self.dpi
                    )
                    
                    # Save current context and create element-specific context
                    el_context = RenderContext(
                        mode=context.mode,
                        tab_mode=context.tab_mode,
                        route=context.route,
                        dpi=self.dpi
                    )
                    
                    # Render the element at its proper local coordinates
                    el.render(painter, el_context)
                    
                except Exception:
                    # fallback for any element rendering issues
                    pass
            except Exception:
                # fallback if position translation fails
                pass
                
            painter.restore()

        if clip:
            painter.restore()
