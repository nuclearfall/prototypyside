from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QPointF, QSize, Signal, QObject
from PySide6.QtGui import (QColor, QFont, QPen, QBrush, QPainter, QPixmap, QPalette,
            QAbstractTextDocumentLayout, QTransform, QPainterPath, QPainterPathStroker)
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QGraphicsSceneMouseEvent, QGraphicsSceneDragDropEvent, QStyleOptionGraphicsItem, QStyle
from typing import Optional, Dict, Any, Union, TYPE_CHECKING

# from prototypyside.views.graphics_items import ResizeHandle
from prototypyside.views.overlays.element_outline import ElementOutline
from prototypyside.utils.qt_helpers import qrectf_to_list, list_to_qrectf
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.units.unit_str_helpers import geometry_with_px_rect, geometry_with_px_pos
from prototypyside.config import HMAP, VMAP, HMAP_REV, VMAP_REV
from prototypyside.utils.graphics_item_helpers import rotate_by
from prototypyside.services.proto_class import ProtoClass
from prototypyside.utils.render_context import RenderContext, RenderMode, RenderRoute, TabMode
from prototypyside.views.shape_mixin import ShapeableElementMixin
from prototypyside.utils.render_context import RenderContext, RenderMode, TabMode, RenderRoute

if TYPE_CHECKING:
    from prototypyside.services.proto_registry import ProtoRegistry

pc = ProtoClass

def _qrect_close(a: QRectF, b: QRectF, eps: float = 0.25) -> bool:
    return (abs(a.x() - b.x()) <= eps and
            abs(a.y() - b.y()) <= eps and
            abs(a.width() - b.width()) <= eps and
            abs(a.height() - b.height()) <= eps)

class ComponentElement(ShapeableElementMixin, QGraphicsObject):
    _serializable_fields = {
        # dict_key      : (from_fn,             to_fn,                  default)
        # name must call registry for name validation on rehydration. It shouldn't be serialized or rehydrated here.
        "shape_kind":   (str,                  lambda s: s,                 "rect"),
        "shape_params": (
            lambda d: {k: UnitStr.from_dict(v) if isinstance(v, dict) and "unit" in v else v for k, v in (d or {}).items()},
            lambda d: {k: (v.to_dict() if pc.isproto(v, pc.US) else v) for k, v in (d or {}).items()},
            {},
        ),
        "z_order":      (int,                   lambda z: z,                0),
        "color":        (QColor.fromRgba,       lambda c: c.rgba(),         None),
        "bg_color":     (QColor.fromRgba,       lambda c: c.rgba(),         None),
        "border_color": (QColor.fromRgba,       lambda c: c.rgba(),         None),
        "border_width": (UnitStr.from_dict,     lambda u: u.to_dict(),      UnitStr("1pt")),
        "corner_radius":(UnitStr.from_dict,     lambda u: u.to_dict(),      UnitStr("0.0 in")),
        "rotation":     (int,                   lambda v: v,                0),
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
    is_vector: bool = False
    is_raster: bool = False
    _snapping_now: bool = False 
    item_changed = Signal()
    nameChanged = Signal(str)  # Add this signal
    moveCommitted = Signal(object, object, object)
    geometryAboutToChange = Signal(object)  # old UnitStrGeometry
    geometryChanged       = Signal(object)  # new UnitStrGeometry
    rectChanged           = Signal(QRectF)  # convenience (px-space)
    positionChanged       = Signal(QPointF)
    selectionChanged = Signal(bool)
    ### TODO: Should fonts be sticky?
    # new_default_font = Signal(object)
    ###

    def __init__(self,
        proto: ProtoClass,
        pid: str, 
        registry: "ProtoRegistry", 
        geometry: UnitStrGeometry,
        name: Optional[str] = None,   
        parent: Optional[QGraphicsObject] = None
    ):
        super().__init__(parent)
        self._updating_from_itemChange = False  # guard
        # assigned by param
        self.proto = proto
        self._pid = pid
        self._registry = registry
        self._settings = registry.settings
        self._dpi = registry.settings.dpi
        self._ldpi = registry.settings.ldpi
        self._unit = self._settings.unit
        self._geometry = geometry or UnitStrGeometry(width="0.75in", height="0.5in", x="10 px", y="10 px", dpi=self._dpi)
        # Attach the decoupled outline/handle overlay
        self._context = RenderContext(
            mode=RenderMode.GUI,
            tab_mode=TabMode.COMPONENT,
            route=RenderRoute.COMPOSITE,
        )
        
        self._outline = ElementOutline(self, parent=self)
        self._name = registry.validate_name(proto, name)

        # assigned by default or via rehydration
        self._color = QColor(Qt.black)
        self._bg_color = QColor(255,255,255,0)
        self._border_color = QColor(Qt.black)
        self._border_width = UnitStr("0.0 pt", dpi=self._dpi)
        self._content: Optional[str] = ""
        self._rotation = 0
        self._corner_radius = UnitStr("0.0 in")
        self._h_align = HMAP.get("Left")  # Left | Center | Right | Justify
        self._v_align = VMAP.get("Top")   # Top  | Center | Bottom

        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self._group_drag_active = False
        self._group_drag_items = []
        self._group_drag_start_pos = {}
        self._group_anchor_pos = QPointF()

        self.setFlags(
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self._suppress_snap = False  # guard for internal moves
        self.setAcceptHoverEvents(True)
        self.setPos(self._geometry.to(self.unit, dpi=self.dpi).pos)
        self.setSelected(True)
        
    @property
    def outline(self):
        return self._outline

    # ---- UnitStrGeometry rect and position handling ---- #
    @property
    def geometry(self):
        return self._geometry

    @geometry.setter
    def geometry(self, new_geom: UnitStrGeometry):
        if new_geom is self._geometry:
            return

        old = self._geometry
        old_px_rect = old.to(self.unit, dpi=self._dpi).rect if old else None
        new = new_geom
        new_px_pos = new.to(self.unit, dpi=self._dpi).pos
        new_px_rect = new.to(self.unit, dpi=self._dpi).rect

        # Only size changes require prepareGeometryChange
        if old != new_geom:
            self.prepareGeometryChange()

        # --- emit "about to" BEFORE mutation
        self.geometryAboutToChange.emit(old)

        # change geometry
        self._geometry = new_geom

        # keep item position in sync with geometry pos
        if self.pos() != new_px_pos:
            self.setPos(new_px_pos)

        # your existing side-effects
        self._invalidate_shape_cache()
        print (f"Geometry after change:\n - Rect: {new_px_rect}\n - Pos: {new_px_pos}")
        # --- emit "changed" AFTER mutation
        self.geometryChanged.emit(self._geometry)
        self.rectChanged.emit(new_px_rect)
        self.positionChanged.emit(new_px_pos)
        self.update()

    def boundingRect(self) -> QRectF:
        r = self._geometry.to(self.unit, dpi=self._dpi).rect
        return QRectF(0, 0, r.width(), r.height())

    # This method is for when ONLY the rectangle (size) changes,
    # not the position.
    def setRect(self, new_rect: QRectF):
        if self._geometry.to(self.unit, dpi=self.dpi).rect == new_rect:
            return

        # geometry setter will call prepareGeometryChange() if needed and emit signals
        self.geometry = geometry_with_px_rect(self._geometry, new_rect, dpi=self.dpi)
        self._invalidate_shape_cache()

    # component_element.py
    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        # PRE-change: before Qt commits the new position, quantize it
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self.selectionChanged.emit(bool(value))

        if change == QGraphicsItem.ItemPositionChange and not self._snapping_now:
            scn = self.scene()
            if scn:
                snapped = scn.snap_to_grid(QPointF(value))
                return snapped

        # POST-change: your existing geometry/signal updates
        if change == QGraphicsItem.ItemPositionHasChanged and not self._updating_from_itemChange:
            self._updating_from_itemChange = True
            self._outline.update_visibility_policy()
            try:
                old = self._geometry
                new_geom = geometry_with_px_pos(old, self.pos(), dpi=self.dpi)
                if new_geom.to(self.unit, dpi=self.dpi).pos != old.to(self.unit, dpi=self.dpi).pos:
                    # keep signals consistent with setter:
                    self.geometryAboutToChange.emit(old)
                    self._geometry = new_geom
                    self._invalidate_shape_cache()
                    self.geometryChanged.emit(self._geometry)
                    self.positionChanged.emit(self._geometry.to(self.unit, dpi=self._dpi).pos)
            finally:
                self._updating_from_itemChange = False

        return super().itemChange(change, value)

    @property
    def display_outline(self) -> bool:
        return self._display_outline

    @display_outline.setter
    def display_outline(self, state: bool):
        self._display_outline = state      
        self._outline.setEnabled(self._display_outline)
        self._outline.setVisible(self._display_outline)
        self.update() 

    # --- Property Getters and Setters --- #
    # Pid and registry and settings have no setters.
    @property
    def pid(self):
        return self._pid

    @property
    def registry(self):
      return self._registry

    @property
    def ldpi(self) -> int:
      return self._ldpi

    @ldpi.setter
    def ldpi(self, new: int):
        if self._ldpi != new:
            self._ldpi = new
            self._invalidate_shape_cache()
            self.update()

    @property
    def dpi(self):
        return self._dpi
    
    @dpi.setter
    def dpi(self, new: int):
        if self._dpi != new:
            self._dpi = new
            self._invalidate_shape_cache()
            self.update()

    @property
    def unit(self):
        return self._unit
    

    @unit.setter
    def unit(self, new: str):
        if self._unit != new:
            self._unit = new
            self._invalidate_shape_cache()
            # unit change may not require geometry change; update visuals anyway
            self.update()

    @property
    def corner_radius(self):
        return self._corner_radius
    

    @corner_radius.setter
    def corner_radius(self, value):
        if value != self._corner_radius:
            self.prepareGeometryChange()
            self._corner_radius = value
            # only affects path when shape_kind is rounded_rect
            if self.shape_kind == "rounded_rect":
                self._invalidate_shape_cache()
            self.item_changed.emit()
            self.update()

    # ---- precise hit-testing to the shape ---- #


    def contains(self, point) -> bool:
        return self.shape_path().contains(point)

    @property
    def unit(self) -> str:
        return self._unit

    @unit.setter
    def unit(self, new: str):
        if self._unit != new:
            self._unit = new

    @property
    def name(self):
        return self._name

    @name.setter 
    def name(self, value):
        if self._name != value:
            proto = ProtoClass.from_class(self)
            self._name = self.registry.validate_name(proto, self._name)
            self.nameChanged.emit(value)
            self.item_changed.emit()
            self.update()

    # ---- These are default initialized or set during rehydration ---- #

    @property
    def content(self) -> Optional[str]:
        return self._content

    @content.setter
    def content(self, content: str):
        self._content = content
        self.item_changed.emit()
        self.update()

    @property
    def color(self) -> QColor:
        return self._color

    @color.setter
    def color(self, value: QColor):
        if self._color != value:
            self._color = value
            self.item_changed.emit()
            self.update()

    @property
    def bg_color(self) -> QColor:
        return self._bg_color

    @bg_color.setter
    def bg_color(self, value: QColor):
        if self._bg_color != value:
            self._bg_color = value
            self.item_changed.emit()
            self.update()

    @property
    def border_color(self) -> QColor:
        return self._border_color

    @border_color.setter
    def border_color(self, value: QColor):
        if self._border_color != value:
            self._border_color = value
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
            rotate_item(self, value)
            self.item_changed.emit()
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

    # --- SHAPE PATH: build from the effective rect so clipping grows when expanded ---
    def shape_path(self) -> QPainterPath:
        rect_local = self._geometry.to(self.unit, dpi=self.dpi).rect
        path = QPainterPath()
        # TODO: if you support corner radius, draw a rounded rect here instead
        path.addRect(rect_local)

        pen = getattr(self, "_border_pen", None)
        if pen and pen.widthF() > 0:
            stroker = QPainterPathStroker()
            stroker.setWidth(pen.widthF())
            stroker.setJoinStyle(pen.joinStyle())
            stroker.setCapStyle(pen.capStyle())
            path = path.united(stroker.createStroke(path))

        path.setFillRule(Qt.WindingFill)
        return path

   
    def render_with_context(self, painter: QPainter, context: RenderContext):
        """
        Base rendering method that handles background, border, and delegates to content rendering
        """
        geom = self.geometry
        rect = geom.to(self.unit, dpi=self.dpi).rect
        # Paint background
        if self._bg_color.alpha() > 0:
            painter.fillRect(rect, self._bg_color)
        
        # Paint content (delegate to subclass)
        self.render_content(painter, context, geom)
        
        # Paint border
        if self.border_width > 0:
            self.paint_border(painter, geom)
        
    def paint_border(self, painter: QPainter, rect: QRectF):
        """
        Paint the element border fully inside the given rect.
        """
        bw = self.border_width.to(self.unit, dpi=self.dpi)
        if bw <= 0:
            return

        painter.save()
        pen = QPen(self.border_color)
        pen.setWidthF(bw)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        # Shrink rect by half border width so the stroke stays inside
        inset = bw / 2.0
        inner_rect = rect.adjusted(inset, inset, -inset, -inset)

        if hasattr(self, "corner_radius") and self.corner_radius.to(self.unit, dpi=self.dpi) > 0:
            cr = max(0.0, self.corner_radius.to(self.unit, dpi=self.dpi) - inset)
            painter.drawRoundedRect(inner_rect, cr, cr)
        else:
            painter.drawRect(inner_rect)

        painter.restore()

    
    def paint(self, painter: QPainter, option, widget=None):
        """
        Default paint method uses GUI context
        """
        self.render_with_context(painter, self.context)

    def clone(self):
        registry = self.registry
        return registry.clone(self)

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "pid":      self._pid,
            "geometry": self._geometry.to_dict(),
            "name":     self._name,
            "content":  self._content
        }

        for key, (_, to_fn, default) in self._serializable_fields.items():
            val = getattr(self, f"_{key}", default)
            data[key] = to_fn(val) if (val is not None) else None

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any], registry: "ProtoRegistry"):

        geom = UnitStrGeometry.from_dict(data.get("geometry"))
        # any pid errors will be caught by the registry
        pid  = ProtoClass.validate_pid(data.get("pid"))
        inst = cls(
            proto = ProtoClass.from_class(cls),
            pid=pid,
            registry=registry,
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
                
    def shape(self) -> QPainterPath:
        """
        Accurate local shape for clipping/hit tests. Includes stroke if present.
        """
        rect_px: QRectF = self.geometry.to(self.unit, dpi=self.dpi).rect
        path = QPainterPath()
        path.addRect(QRectF(0, 0, rect_px.width(), rect_px.height()))
        pen = getattr(self, "_border_pen", None)
        if pen and pen.widthF() > 0:
            stroker = QPainterPathStroker()
            stroker.setWidth(pen.widthF())
            stroker.setJoinStyle(pen.joinStyle())
            stroker.setCapStyle(pen.capStyle())
            path = path.united(stroker.createStroke(path))
        path.setFillRule(Qt.WindingFill)
        return path

    # def paint(self, painter: QPainter, option, widget=None):
    #     """
    #     IMPORTANT: draw in *local* coordinates at (0,0).
    #     Do not translate by rect.x()/rect.y() here.
    #     """
    #     rect_px: QRectF = self.geometry.to(self.unit, dpi=self.dpi).rect
    #     painter.save()
    #     # background fill if you use it:
    #     bg = getattr(self, "_bg_color", None)
    #     if bg is not None:
    #         painter.fillRect(QRectF(0, 0, rect_px.width(), rect_px.height()), bg)
    #     # subclasses draw content here (no global translations)
    #     painter.restore()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.isSelected():
            items = self.scene().selectedItems() if self.scene() else [self]
            self._group_drag_items = [it for it in items
                                      if (it is self) or (it.flags() & QGraphicsItem.ItemIsMovable)]
            self._group_drag_start_pos = {it: it.pos() for it in self._group_drag_items}
            self._group_anchor_pos = self.pos()
            self._group_drag_active = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._group_drag_active:
            super().mouseMoveEvent(event)  # move the lead item (snapping/constraints happen here)
            delta = self.pos() - self._group_anchor_pos
            if not delta.isNull():
                for it in self._group_drag_items:
                    if it is self: 
                        continue
                    it.setPos(self._group_drag_start_pos[it] + delta)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        try:
            super().mouseReleaseEvent(event)
        finally:
            if self._group_drag_active:
                ends = {it: it.pos() for it in self._group_drag_items}
                # Only emit if anything actually moved
                moved = any(ends[it] != self._group_drag_start_pos[it] for it in self._group_drag_items)
                if moved:
                    self.moveCommitted.emit(self._group_drag_items, self._group_drag_start_pos, ends)
            # cleanup
            self._group_drag_active = False
            self._group_drag_items = []
            self._group_drag_start_pos = {}
            self._group_anchor_pos = QPointF()