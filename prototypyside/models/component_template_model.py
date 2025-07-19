
from typing import TYPE_CHECKING
from prototypyside.utils import UnitStrGeometry
from prototypyside.utils import UntiStr

if TYPE_CHECKING:
    from prototypyside.services.proto_registry import ProtoRegistry
    from prototypyside.models.componet_element import ComponentElement
    from prototypyside.models.property_model import PropertyModel

class ProtoModel:
    pid: str
    name: str
    registry: "ProtoRegistry"
    geometry: UnitStrGeometry
    properties: PropertyModel


class ComponentTemplateModel(ProtoModel):
    pid: str = issue_pid("ct")
    name: str = None
    border: UnitStr =UnitStr("0.125in")
    radius: UnitStr = UnitStr("0.125in")
    corner_radius: UnitStr = UnitStr("0.125in")
    geometry UnitStrGeometry = UnitStrGeometry(width="2.5in", height="3.5in")
    items: List["CompentElement"]

    # def set_registry(self, registry):
    #     self._registry = registry 
    # # borders and corners default to standard MTG card dimensions.
    #     def __init__(self) 
    #     , parent = None, 
    #     name=None, registry=None
    #     super().__init__(parent)
    #     self._tpid = None
    #     self.lpid = None
    #     self._path = None
    #     # associated layouts if any
    #     self._layouts = []
    #     self._pid = pid
    #     self._name = name
    #     self._registry = registry
    #     self._geometry = geometry
    #     self._dpi = 144
    #     self._unit = "px"
    #     self._pixmap = None
    #     self.items: List['ComponentElement'] = []

    #     self._background_image: Optional[str] = None
    #     self._corner_radius = corner_radius
    #     self._csv_row = []
    #     self._csv_path: Path = None 
    #     self.content = None
    #     self.registry.object_registered.connect(self.add_item)

  