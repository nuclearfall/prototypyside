from typing import Optional, Dict, TYPE_CHECKING
from pathlib import Path

from PySide6.QtCore import Qt, QRectF
from PySide6.QtWidgets import QGraphicsItem

from prototypyside.models.component_template import ComponentTemplate

if TYPE_CHECKING:
    from prototypyside.models.layout_slot import LayoutSlot
    from prototypyside.services.proto_class import ProtoClass
    from prototypyside.services.proto_registry import ProtoRegistry
    from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry


class Component(ComponentTemplate):
    """
    A movable, selectable instance created from a ComponentTemplate
    to be placed inside a LayoutSlot.
    """
    def __init__(
        self,
        proto: "ProtoClass",
        pid: str,
        registry: "ProtoRegistry",
        geometry: "UnitStrGeometry" = None,
        name: Optional[str] = None,
        shape: str = "default",
        file_path: Optional[Path] = None,
        csv_path: Optional[Path] = None,
        csv_row: Optional[Dict] = None,
        parent=None,
    ):
        super().__init__(
            proto=proto,
            pid=pid,
            registry=registry,
            geometry=geometry,
            name=name,
            shape=shape,
            file_path=file_path,
            csv_path=csv_path,
            parent=parent,
        )

        # Will be set by the slot that owns/hosts this component
        self._csv_row: csv_row
        self._has_csv_conent = False
        if csv_row:
            self.set_csv_content()

        self._slot_pid: Optional[str] = None
        # Flags
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemClipsChildrenToShape, True)

    # ---- QGraphicsItem overrides ------------------------------------------

    def boundingRect(self) -> QRectF:
        # assuming UnitStrGeometry exposes a pixel-space QRectF at .px.rect
        return self._geometry.px.rect  # type: ignore[return-value]

    # ---- Slot binding ------------------------------------------------------

    @property
    def slot_pid(self) -> Optional[str]:
        return self._slot_pid

    @slot_pid.setter
    def slot_pid(self, pid: Optional[str]) -> None:
        if pid != self._slot_pid:
            self._slot_pid = pid

    @property
    def has_csv_content(self):
        return self._has_csv_content

    @has_csv_content.setter
    def has_csv_content(self, state):
        if state == self._has_csv_content:
            return
        self._has_csv_content = not self._has_csv_content
    
    # Components (instances) are not cloneable; clone the template instead.
    def clone(self):
        obj = super().clone(self, register=True)
        for item in self.items:
        	obj._display_outline = False

    def set_csv_content(self):
        for el in self.items:
            content = self.csv_row.get(el.name, None)
            if content:
                self.has_csv_content = True
                el.content = content
