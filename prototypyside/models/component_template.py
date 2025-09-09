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
import weakref
import gc
import traceback
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
    "circle":           ShapeFactory.circle,
    "hexagon":          ShapeFactory.hexagon,
    "diamond":          ShapeFactory.diamond,
    "pentagon":         ShapeFactory.pentagon,
    "octagon":          ShapeFactory.octagon,
    "polygon":          ShapeFactory.polygon,
    "default":          None
}

class ComponentTemplate(QGraphicsObject, RotatableMixin):
    template_changed = Signal()
    item_z_order_changed = Signal()
    item_name_change = Signal()

    def __init__(
        self,
        proto:ProtoClass,
        pid: str,
        registry: ProtoRegistry,
        geometry: UnitStrGeometry = None,
        name: Optional[str] = None,
        shape: str = "circle",
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
        self._corner_radius = UnitStr("0.125in", unit="in", dpi=self.dpi)
        self._border_width = UnitStr("0.125in", unit="in", dpi=self.dpi)
        self._border_color = QColor(Qt.black)

        self._bg_color = QColor(Qt.white)
        self._background_image: Optional[Path] = None

        self._bleed = UnitStr("0.125in", unit="in", dpi=self.dpi)
        self._bleed_rect: UnitStrGeometry = self.setBleedRect(self._geometry)
        self._include_bleed = False
        self._set_print_mode = False
        
        # Shape path generator
        self._shape = shape
        self._shape_factory = SHAPES.get(self._shape)
        # shape_factory or self._default_shape_factory   # store callable (bound method)

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


    def _default_shape_factory(self, rect: QRectF) -> QPainterPath:
        path = QPainterPath()
        radius_px = self._corner_radius.to("px", dpi=self._dpi)
        if radius_px > 0.0:
            path.addRoundedRect(rect, radius_px, radius_px)  # both x & y radii
        else:
            path.addRect(rect)
        return path

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
            print(f"[CT] Target ID: {self.pid}, Prop: geometry, New: {new_geom}.\n - value remains unchanged")
            return
        self.prepareGeometryChange()
        rect_px = self._geometry.to("px", dpi=self.dpi).rect
        self.setTransformOriginPoint(rect_px.center())
        self._geometry = new_geom
        print(f"[CT] Target ID: {self.pid}, Prop: geometry, New: {new_geom}.\n - value changed to {self._geometry}")
        if not self.tpid:
            self.template_changed.emit()
        self.setBleedRect()
        self._update_border_path()
        self.update()

    @property
    def width(self): return self._geometry.width

    def width(self, value: UnitStr):
        if value != self._geometry.width:
            h = self._geometry.height
            self.geometry = UnitStrGeometry(width=value, height=h, dpi=self._dpi)

    @property
    def height(self): return self._geometry.height

    @height.setter
    def height(self, value: UnitStr):
        if value != self._geometry.height:
            w = self._geometry.width
            self.geometry = UnitStrGeometry(width=w, height=value, dpi=self._dpi)

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
            # geometry_with_px_pos(self._geometry, value, dpi=self.dpi)
            self.blockSignals(signals_blocked)

        # If other signals are emitted or updates called for, it breaks the undo stack.
        return super().itemChange(change, value)

    # def boundingRect(self) -> QRectF:
    #     if self._include_bleed:
    #         br = self._geometry.to("px", dpi=self.dpi).rect
    #         b = float(self._bleed.to("px", dpi=self.dpi))
    #         return QRectF(
    #             br.x() - b, br.y() - b,
    #             br.width() + 2*b, br.height() + 2*b
    #         )
    #     rotated = self._geometry.to("px", dpi=self.dpi).rect
    #     return self.rotated_bounding_rect_px(rotated)

    # --- rotation-aware boundingRect (handles bleed and no-bleed) ---
    def boundingRect(self) -> QRectF:
        if self._include_bleed:
            base = self.bleed_rect.to("px", dpi=self.dpi).rect
        else:
            base = self._geometry.to("px", dpi=self.dpi).rect
        return self.rotated_bounding_rect_px(base)


    # allows dynamic shape transformation of components
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
    def shape(self):
        # Use the same geometry you expose in boundingRect
        if self._include_bleed:
            rect_px = self.bleed_rect.to("px", dpi=self.dpi).rect
            path = self.bleed_path()
        else:
            rect_px = self._geometry.to("px", dpi=self.dpi).rect
            path = self.shape_path()

        # Map the unrotated path by the current rotation transform
        return self.map_path_with_rotation(path, rect_px)

    # def shape(self, s):
    #     if s != self._shape and s in SHAPES:
    #         self._shape = s
    #         self.shape_factory = SHAPES.get(s)
    #         self._update_border_path()
    #         self._update_border_style()  #

    @property
    def shape_factory(self) -> Callable[[QRectF], QPainterPath]:
        return self._shape_factory

    @shape_factory.setter
    def shape_factory(self, factory: Callable[[QRectF], QPainterPath]):
        if self._shape_factory is factory:
            return
        self.prepareGeometryChange()
        self._shape_factory = factory
        self.update()


    def shape_path(self) -> QPainterPath:
        rect_px = self.geometry.to("px", dpi=self.dpi).rect
        path = (self._shape_factory or self._default_shape_factory)(rect_px)
        path.setFillRule(Qt.WindingFill)
        return path

    def bleed_path(self) -> QPainterPath:
        base_rect = self._geometry.to("px", dpi=self.dpi).rect
        b = float(self._bleed.to("px", dpi=self.dpi))
        bleed_rect = QRectF(
            base_rect.x() - b, base_rect.y() - b,
            base_rect.width() + 2*b, base_rect.height() + 2*b
        )

        path = QPainterPath()
        using_default = (self._shape_factory is None) or (self._shape in ("default", "rounded_rect"))
        if using_default:
            cr = float(self._corner_radius.to("px", dpi=self.dpi))
            r_bleed = max(0.0, cr + b)
            if r_bleed > 0.0:
                path.addRoundedRect(bleed_rect, r_bleed, r_bleed)
            else:
                path.addRect(bleed_rect)
        else:
            path = (self._shape_factory or self._default_shape_factory)(bleed_rect)

        path.setFillRule(Qt.WindingFill)
        return path

    def _update_border_path(self):
        if not self._border_item:
            return
        self._border_item.setPath(self._inner_border_path())

    # 2) In _update_border_style (for the always-on-top path item)
    def _update_border_style(self):
        border_px = float(self._border_width.to("px", dpi=self.dpi))
        pen = QPen(self._border_color)
        pen.setWidthF(border_px)
        pen.setJoinStyle(Qt.MiterJoin)       # <-- was Qt.RoundJoin
        # pen.setMiterLimit(10.0)            # optional
        # pen.setCapStyle(Qt.SquareCap)      # optional
        self._border_item.setPen(pen)
        self._border_item.setBrush(Qt.NoBrush)


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
            self._update_border_style()
            self._update_border_path()
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
            self._update_border_path()
            self.update()



    @property
    def set_print_mode(self):
        return self._set_print_mode

    @set_print_mode.setter
    def set_print_mode(self, val):
        self._set_print_mode = val
        for item in self.items:
            item.display_border = False

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
            'background_image': str(self.background_image) if self.background_image else None,
            'items': [e.to_dict() for e in self.items],
            'border_width': self.border_width.to_dict(),
            'corner_radius': self.corner_radius.to_dict(),
            'bleed': self._bleed.to_dict(),
            'csv_path': str(self.csv_path) if self.csv_path and Path(self.csv_path).exists else None,
            'tpid': self.tpid,
            'include_bleed': self._include_bleed,
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

        # --- 3) Optional colors ---
        bg_color = data.get("bg_color")
        border_color = data.get("border_color")
        inst._bg_color = QColor.fromRgba(bg_color) if bg_color is not None else None
        inst._border_color = QColor.fromRgba(border_color) if border_color is not None else None

        # --- 4) File/CSV paths (robust but non-fatal) ---
        csv_path = data.get("csv_path")
        inst.csv_path = csv_path

        file_path = data.get("file_path")
        inst.file_path = file_path

        # Compute bleed rect after bleed is set
        inst.setBleedRect()

        return inst



    # --- convenience switches you can call from tabs when the tab/render mode changes ---
    def configure_render_context(self, *, render_mode: RenderMode, tab_mode: TabMode, route: RenderRoute | None = None):
        self.render_mode = render_mode
        self.tab_mode = tab_mode
        if route is not None:
            self.render_route = route

        # ComponentTab GUI => free drawing, no clipping
        if self.render_mode == RenderMode.GUI and self.tab_mode == TabMode.COMPONENT:
            self.setFlag(QGraphicsItem.ItemClipsChildrenToShape, False)
            if self._border_item:
                self._border_item.setVisible(True)

            # LayoutTab GUI => the slot will rasterize; keep as-is
            # Export => composite/vector routes; clipping is handled in export pipeline
    # ----------------------------------------------------------------
    def _update_border_path(self):
        """Update the border path based on current geometry"""
        rect_px = self._geometry.to("px", dpi=self._dpi).rect
        path = self._shape_factory(rect_px) if self._shape_factory else QPainterPath()
        self._border_item.setPath(path)
        
    def _update_border_style(self):
        """Update border pen style"""
        border_px = self._border_width.to("px", dpi=self._dpi)
        pen = QPen(self._border_color)
        pen.setWidthF(float(border_px))
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        self._border_item.setPen(pen)
        self._border_item.setBrush(Qt.NoBrush)
        

    # --- Shape Path ---
 
    def render(self, painter: QPainter, context: RenderContext):
        rect_px = self._geometry.to("px", dpi=self.dpi).rect

        # 0) Bleed behind everything
        if self._include_bleed:
            self._paint_bleed(painter)

        # 1) Background clipped to main shape
        self._paint_background(painter, rect_px)

        # 2) Elements
        if context.is_gui and context.is_component_tab:
            self._paint_elements(painter, context, clip=False)
        else:
            path = self.shape_path()
            painter.save()
            painter.setClipPath(path, Qt.ReplaceClip)
            self._paint_elements(painter, context, clip=True)
            painter.restore()

        # 3) Border on top
        self._paint_border(painter)

    def _paint_bleed(self, painter: QPainter):
        path = self.bleed_path()
        painter.save()
        fill_color = self._border_color if self._border_color else self._bg_color 
        if fill_color is not None:
            painter.fillPath(path, QBrush(fill_color))
        painter.restore()

    def _paint_elements(self, painter: QPainter, context: RenderContext, clip: bool):
        """
        Paint elements in the correct order based on rendering route
        """
        elements = sorted(self.items, key=lambda e: e.zValue())
        
        if context.route == RenderRoute.VECTOR_PRIORITY and context.is_export:
            # Separate vector and raster elements for vector priority mode
            vectors = [e for e in elements if getattr(e, 'is_vector', False)]
            rasters = [e for e in elements if getattr(e, 'is_raster', False)]
            others = [e for e in elements if not getattr(e, 'is_vector', False) and 
                                           not getattr(e, 'is_raster', False)]
            
            # Draw rasters first, then others, then vectors on top
            for element in rasters + others:
                self._paint_element(element, painter, context, clip)
            
            for element in vectors:
                self._paint_element(element, painter, context, clip)
        else:
            # Standard z-order rendering
            for element in elements:
                self._paint_element(element, painter, context, clip)
    
    def _paint_element(self, element, painter: QPainter, context: RenderContext, clip: bool):
        """
        Paint a single element with appropriate context
        """
        # Save painter state
        painter.save()
        
        # Apply element transformation
        painter.translate(element.pos())
        
        # Set up clipping if needed
        if clip and hasattr(element, 'shape_path'):
            painter.setClipPath(element.shape_path(), Qt.ReplaceClip)
        
        # Let element handle its own rendering with context
        if hasattr(element, 'render_with_context'):
            element.render_with_context(painter, context)
        else:
            # Fallback to standard paint
            element.paint(painter, None, None)
        
        # Restore painter state
        painter.restore()

    def _inner_border_path(self) -> QPainterPath:
        bw = float(self._border_width.to("px", dpi=self.dpi))
        inset = bw * 0.5
        rect = self._geometry.to("px", dpi=self.dpi).rect.adjusted(inset, inset, -inset, -inset)

        # Use the selected shape factory; only apply radius math for rounded shapes.
        if (self._shape_factory is None) or (self._shape in ("default", "rounded_rect")):
            # Rounded-rect semantics (or default)
            cr = float(self._corner_radius.to("px", dpi=self.dpi))
            cr = max(0.0, cr - inset)  # keep stroke fully inside
            path = QPainterPath()
            if cr > 0.0:
                path.addRoundedRect(rect, cr, cr)
            else:
                path.addRect(rect)
        else:
            # EXACT shape from the current factory (rect, circle, hex, polygon, etc.)
            path = (self._shape_factory or self._default_shape_factory)(rect)

        path.setFillRule(Qt.WindingFill)
        return path

    # 1) In _paint_border
    def _paint_border(self, painter: QPainter):
        bw = float(self._border_width.to("px", dpi=self.dpi))
        if bw <= 0:
            return
        painter.save()
        pen = QPen(self._border_color)
        pen.setWidthF(bw)
        pen.setJoinStyle(Qt.MiterJoin)       # <-- was Qt.RoundJoin
        # pen.setMiterLimit(10.0)            # optional: ensure crisp sharp corners
        # pen.setCapStyle(Qt.SquareCap)      # optional: cap style irrelevant for closed paths
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self._inner_border_path())
        painter.restore()
    
    def to_raster_image(self, context: RenderContext) -> QImage:
        """Render to raster image with the given context"""
        rect_px = self._geometry.to("px", dpi=self.dpi).rect
        w = max(1, int(rect_px.width()))
        h = max(1, int(rect_px.height()))
        
        img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        
        p = QPainter(img)
        p.setRenderHints(
            QPainter.Antialiasing | 
            QPainter.TextAntialiasing | 
            QPainter.SmoothPixmapTransform, 
            True
        )
        
        # Render with the provided context
        self.render(p, context)
        
        p.end()
        return img

    def _paint_background(self, painter: QPainter, rect: QRectF):
        """
        Paint the template background clipped to the shape
        """
        path = self.shape_path()

        painter.save()
        # Fill background color inside the rounded shape
        if self._bg_color is not None:
            painter.fillPath(path, self._bg_color)

        # Draw background image inside the rounded shape
        if self._background_image:
            img = QImage(str(self._background_image))
            if not img.isNull():
                painter.setClipPath(path, Qt.ReplaceClip)
                painter.drawImage(rect, img)
                painter.setClipping(False)
        painter.restore()
        
    # Replace the existing paint method
    # def paint(self, painter: QPainter, option, widget=None):
    #     # Default to GUI rendering for scene display
    #     context = RenderContext(
    #         mode=RenderMode.GUI,
    #         tab_mode=TabMode.COMPONENT,
    #         route=self.render_route,
    #         dpi=self.dpi
    #     )
    #     self.render(painter, context)
    # --- wrap painting in the rotation helper; GUI uses native QGraphicsItem rotation,
    # --- offscreen/export uses a painter transform automatically.
    def paint(self, painter: QPainter, option, widget=None):
        # Default to GUI rendering for scene display (ComponentTab)
        context = RenderContext(
            mode=RenderMode.GUI,
            tab_mode=TabMode.COMPONENT,
            route=self.render_route,
            dpi=self.dpi
        )

        rect_px = self._geometry.to("px", dpi=self.dpi).rect

        # IMPORTANT:
        # - In GUI mode, begin_rotated_paint() will sync self.setTransformOriginPoint/ setRotation(...)
        #   and NOT apply a painter transform (so picking/handles stay correct).
        # - In export/offscreen modes (when you call render(...) elsewhere with RenderMode.EXPORT),
        #   begin_rotated_paint() will apply a painter transform instead.
        with self.begin_rotated_paint(
            painter,
            rect_px,
            context.mode,           # your RenderMode enum is fine here
            item_for_gui_sync=self  # let mixin set QGraphicsItem rotation in GUI
        ):
            self.render(painter, context)


