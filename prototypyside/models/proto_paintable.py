from typing import Optional, Dict, Any, TYPE_CHECKING

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject
from PySide6.QtGui import QColor, QPainter

from prototypyside.utils.units.unit_str_helpers import geometry_with_px_rect, geometry_with_px_pos
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.services.proto_class import ProtoClass
from prototypyside.utils.render_context import RenderContext
from prototypyside.services.proto_paint import ProtoPaint
from prototypyside.services.render_cache import RenderCache
from prototypyside.utils.rotatable_mixin import RotatableMixin
from prototypyside.config import HMAP, VMAP, HMAP_REV, VMAP_REV

if TYPE_CHECKING:
    from prototypyside.services.proto_registry import ProtoRegistry

pc = ProtoClass

class ProtoPaintable(QGraphicsObject, RotatableMixin):
    _serializable_fields = {
        # dict_key      : (from_fn,             to_fn,                  default)
        "shape":   		(str,                  		lambda s: s,                 "rect"),
        "z_order":      (int,                   	lambda z: z,                0),
        "color":        (QColor.fromRgba,       	lambda c: c.rgba(),         ),
        "bg_color":     (QColor.fromRgba,       	lambda c: c.rgba(),         None),
        "border_color": (QColor.fromRgba,       	lambda c: c.rgba(),         None),
        "bleed": (UnitStr.from_dict,         lambda u: u.to_dict(),      UnitStr("0.0 in")),
        "border_width": (UnitStr.from_dict,     	lambda u: u.to_dict(),      UnitStr("0.0 in")),
        "corner_radius":(UnitStr.from_dict,     	lambda u: u.to_dict(),      UnitStr("0.0 in")),
        "rotation":     (int,                   	lambda v: v,                0),
        "h_align": (
            # from_fn: accept string OR flag; normalize to flag
            lambda s: HMAP.get(s, s) if isinstance(s, str) else Qt.Alignment(int(s)),
            # to_fn: emit canonical string
            lambda f: HMAP_REV.get(Qt.Alignment(int(f)), Qt.AlignLeft),
            Qt.AlignLeft,
        ),
        "v_align": (
            lambda s: VMAP.get(s, s) if isinstance(s, str) else Qt.Alignment(int(s)),
            lambda f: VMAP_REV.get(Qt.Alignment(int(f)), Qt.AlignTop),
            Qt.AlignTop,
        ),
    }

    item_changed 			= Signal()
    nameChanged 			= Signal(str)
    moveCommitted 			= Signal(object, object, object)
    geometryAboutToChange 	= Signal(object)  # old UnitStrGeometry
    geometryChanged       	= Signal(object)  # new UnitStrGeometry
    rectChanged           	= Signal(QRectF)  # convenience (px-space)
    selectionChanged 		= Signal(bool)
    positionChanged         = Signal(QPointF)

    def __init__(self,
        proto: ProtoClass,
        pid: str, 
        registry: "ProtoRegistry",
        ctx: RenderContext, 
        geometry: UnitStrGeometry=None,
        name: Optional[str] = None,   
        parent: Optional[QGraphicsObject] = None
    ):
        super().__init__(parent)

        self.proto = proto
        self._pid = pid
        self._registry = registry
        self._settings = registry.settings
        self._ctx = ctx
        if getattr(self._ctx, "cache", None) is None:
            self._ctx.cache = RenderCache(self._ctx)
        self._shape = "rect"
        self._geometry = geometry
        self._aspect = "fit"
        self._include_bleed = False
        self._name = registry.validate_name(proto, name)

        # will be either an image path or plain text
        self._content: Optional[str] = ""

        self._color = QColor(Qt.black)
        self._border_color = QColor(Qt.black)
        self._bg_color = QColor(Qt.white)
        self._bleed = UnitStr("0.0 in", dpi=self._ctx.dpi)

        self._border_width = UnitStr("0.0pt", dpi=self._ctx.dpi)
        self._rotation = 0
        self._corner_radius = UnitStr("0.0 in",dpi=self._ctx.dpi)
        self._h_align = HMAP.get("Left")  # Left | Center | Right | Justify
        self._v_align = VMAP.get("Top")   # Top  | Center | Bottom
        self._updating_from_itemChange = False 

        self.setFlag(
            QGraphicsItem.ItemSendsGeometryChanges, True)
        if ctx.is_gui:
            self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
            if ctx.is_component_tab and not self.proto == pc.CT:
                self.setSelected(True)
                self.setFlag(QGraphicsItem.ItemIsSelectable, True)
                self.setFlag(QGraphicsItem.ItemIsMovable, True)
                self.setAcceptHoverEvents(True)
        else:
            self.setCacheMode(QGraphicsItem.NoCache)
        
        registry.settings.ctx_changed.connect(self.update_ctx)
 
        self.setPos(self._geometry.to(self._ctx.unit, dpi=self._ctx.dpi).pos)

    def boundingRect(self) -> QRectF:
        r = self._geometry.to(self.ctx.unit, dpi=self.ctx.dpi).rect
        if self.ctx.is_gui and self.ctx.is_component_tab:
            print("we're reaching this")
            pad_px = 12.0
            # Convert px → current unit
            # (UnitStr knows your dpi; “px” is meaningful in your system)
            pad = UnitStr(f"{pad}px", unit=ctx.unit, dpi=self.ctx.dpi).value
            return r.adjusted(-pad, -pad, pad, pad)
        else:
            return r

    def setRect(self, new_rect: QRectF):
        if self._geometry.to(self.ctx.unit, dpi=self.ctx.dpi).rect == new_rect:
            return

        # geometry setter will call prepareGeometryChange() if needed and emit signals
        self.geometry = geometry_with_px_rect(self._geometry, new_rect, dpi=self.ctx.dpi)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        # Selection -> forward signal
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self.selectionChanged.emit(bool(value))

        # PRE: before Qt commits the move, propose a snapped pos
        if change == QGraphicsItem.ItemPositionChange:
            scn = self.scene()
            if scn:
                snapped = scn.snap_to_grid(value)
                return snapped  # do NOT mutate geometry here

        # POST: after Qt commits the move, reflect pos back into geometry
        if change == QGraphicsItem.ItemPositionHasChanged and not self._updating_from_itemChange:
            self._updating_from_itemChange = True
            try:
                # Build a new geometry with the current scene pos (px)
                new_geom = geometry_with_px_pos(self._geometry, self.pos(), dpi=self.ctx.dpi)
                # Use the setter so it emits signals consistently and
                # only calls prepareGeometryChange() on size changes.
                self.geometry = new_geom
            finally:
                self._updating_from_itemChange = False

        return super().itemChange(change, value)

    @property
    def pid(self):
        return self._pid

    @property
    def registry(self):
      return self._registry

    @property
    def ctx(self):
        return self._ctx

    @ctx.setter
    def ctx(self, ctx):
        # If nothing meaningful changed, bail early
        if ctx == self._ctx:
            return

        # Swap context
        self._ctx = ctx
        if getattr(self._ctx, "cache", None) is None:
            self._ctx.cache = RenderCache(self._ctx)
        interactive = bool(ctx.is_gui and ctx.is_component_tab)
        # Cache mode: GUI uses device cache; export/offscreen = no cache
        self.setCacheMode(
            QGraphicsItem.DeviceCoordinateCache if interactive else QGraphicsItem.NoCache
        )

        # Interactivity only in Component tab (GUI)
        
        self.setFlag(QGraphicsItem.ItemIsSelectable, interactive)
        self.setFlag(QGraphicsItem.ItemIsMovable, interactive)
        self.setAcceptHoverEvents(interactive)

        # Leaving interactive mode? ensure deselected
        if not interactive and self.isSelected():
            self.setSelected(False)

        self.update()

    @property
    def geometry(self):
        return self._geometry

    @geometry.setter
    def geometry(self, new_geom: UnitStrGeometry):
        if new_geom == self._geometry:
            return

        dpi = self.ctx.dpi
        old = self._geometry

        old_rect_px = old.to("px", dpi=dpi).rect if old else None
        old_pos_px  = old.to("px", dpi=dpi).pos  if old else None

        new_rect_px = new_geom.to("px", dpi=dpi).rect
        new_pos_px  = new_geom.to("px", dpi=dpi).pos

        # ✔ size-only: compare QSizeF, not the whole QRectF
        size_changed = (old_rect_px is None) or (old_rect_px.size() != new_rect_px.size())
        pos_changed  = (old_pos_px is None) or (old_pos_px != new_pos_px)

        if size_changed:
            self.prepareGeometryChange()

        self.geometryAboutToChange.emit(old)
        self._geometry = new_geom

        if pos_changed and self.pos() != new_pos_px:
            self.positionChanged.emit()
            self.setPos(new_pos_px)

        self.geometryChanged.emit(self._geometry)
        if size_changed:
            self.rectChanged.emit(new_rect_px)
        if pos_changed:
            self.positionChanged.emit(new_pos_px)

        self.update()

    @property
    def name(self):
        return self._name

    @name.setter 
    def name(self, value):
        if self._name != value:
            self._name = self.registry.validate_name(self.proto, self._name)
            self.nameChanged.emit(value)
            self.item_changed.emit()
            self.update()

    @property
    def content(self) -> Optional[str]:
        return self._content

    @content.setter
    def content(self, content: str):
        self._content = content
        self.item_changed.emit()
        self.update()

    @property
    def shape(self):
        return self._shape

    @shape.setter
    def shape(self, new):
        old_shape = self._shape
        if old_shape == new:
            return
        self._shape = new
        self.update()
    @property
    def include_bleed(self):
        return self._include_bleed

    @include_bleed.setter
    def include_bleed(self, state):
        if self._include_bleed == state:
            return
        self._include_bleed = state
        self.item_changed.emit()
        self.update()
    
    @property
    def bleed(self):
        return self._bleed

    @bleed.setter
    def bleed(self, new):
        if self._bleed == new:
            return
        self._bleed = new
        self.item_changed.emit()
        if self.include_bleed:
            self.update()
    
    @property
    def corner_radius(self):
        return self._corner_radius

    @corner_radius.setter
    def corner_radius(self, value):
        if value != self._corner_radius:
            self.prepareGeometryChange()
            self._corner_radius = value
            if self._shape == "rounded_rect":
                self.item_changed.emit()
                self.update()

    @property
    def aspect(self):
        return self._aspect

    @aspect.setter
    def aspect(self, new):
        if new == self._aspect:
            return
        self._aspect = new 
        self.update()

    @property
    def color(self) -> QColor:
        return self._color

    @color.setter
    def color(self, value: QColor):
        if self._color != value:
            self._color = QColor(value)
            self.item_changed.emit()
            self.update()

    @property
    def bg_color(self) -> QColor:
        return self._bg_color

    @bg_color.setter
    def bg_color(self, value: QColor):
        if self._bg_color != value:
            self._bg_color = QColor(value)
            self.item_changed.emit()
            self.update()

    @property
    def border_color(self) -> QColor:
        return self._border_color

    @border_color.setter
    def border_color(self, value: QColor):
        if self._border_color != value:
            self._border_color = QColor(value)
            self.item_changed.emit()
            self.update()

    @property
    def border_width(self) -> UnitStr:
        return self._border_width

    @border_width.setter
    def border_width(self, value: UnitStr):
        if self._border_width != value:
            self._border_width = value
            self.item_changed.emit()
            self.update()      

    @property
    def rotation(self):
        return self._rotation

    @rotation.setter
    def rotation(self, value: int):
        if value != self._rotation:
            self._rotation = value
            rotator.rotate_item(self, value)
            self.item_changed.emit()
            self.update()

    def update_ctx(self, new):
        if new == self._ctx:
            return
        self.ctx = new
        self.update()

    @property
    def h_align(self) -> Qt.Alignment:
        return self._h_align

    @h_align.setter
    def h_align(self, value: Qt.Alignment):
        if self._h_align != value:
            self._h_align = value
            self.item_changed.emit()
            self.update()

    @property
    def v_align(self) -> Qt.Alignment:
        return self._v_align

    @v_align.setter
    def v_align(self, value: Qt.Alignment):
        if self._v_align != value:
            self._v_align = value
            self.item_changed.emit()
            self.update() 
                   
    def paint(self, painter: QPainter, option, widget=None):
        ctx = self._ctx
 
        # cache is invalidated on self.update() for gui and disabled for export
        painter.save()
        ProtoPaint.render(self, ctx, painter)
        painter.restore()

    def clone(self):
        registry = self.registry
        return registry.clone(self)

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "pid":      self._pid,
            "geometry": self._geometry.to_dict(),
            "name":     self._name,
            "ctx":	self._ctx.to_dict(),
            "content":  self._content
        }

        for key, (_, to_fn, default) in self._serializable_fields.items():
            val = getattr(self, f"_{key}", default)
            data[key] = to_fn(val) if (val is not None) else None

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any], registry: "ProtoRegistry"):
        geom = UnitStrGeometry.from_dict(data.get("geometry"))
        ctx = RenderContext.from_dict(data.get("ctx"))
        # any pid errors will be caught by the registry
        pid  = pc.validate_pid(data.get("pid"))
        inst = cls(
            proto = pc.from_class(cls),
            pid=pid,
            registry=registry,
            ctx=ctx,
            geometry=geom,
            name=data.get("name"),
        )
        inst.content = data.get("content")
        for key, (from_fn, _to_fn, default) in cls._serializable_fields.items():
            raw = data.get(key, default)
            if raw is None:
                continue
            try:
                setattr(inst, f"_{key}", from_fn(raw))
            except Exception:
                setattr(inst, f"_{key}", default)

        return inst