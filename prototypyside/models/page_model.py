from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.ustr import UnitStr
@dataclass
class PageModel(LayoutTemplate)
    pid = pid
    name = name
    content = []
    page_size = page_size
    registry = registry
    geometry = PAGE_SIZES[page_size]["geometry"] or UnitStrGeometry(width="8.5in", height="11in")
    dpi = 300
    unit = "inch"
    pagination_policy: str
    rows = rows
    columns = columns
    margins = [UnitStr(m, dpi=dpi) for m in (margin_top, margin_bottom, margin_left, margin_right)]
    spacing = [UnitStr(s, dpi=dpi) for s in (spacing_x, spacing_y)]
    orientation = orientation
    items = []

    def to_dict(self) -> Dict[str, Any]:
        data = {
            'pid': pid,
            'name': name,
            'geometry': geometry.to_dict(),
            'background_image_path': self.background_image_path,
            'elements': [e.to_dict() for e in self.elements]
        }
        return data

    @classmethod
    def from_dict(cls, data: dict, registry: ProtoRegistry) -> "ComponentTemplate":
        geom = UnitStrGeometry.from_dict(data["geometry"])
        inst = cls(pid=data["pid"], geometry=geom, name=data.get("name"))
        inst.background_image_path = data.get("background_image_path")

        registry.create_child_registry(inst)
        registry.register(inst)
        registry = registry.get_child_registry(inst.pid)

        inst.elements = []
        for e in data.get("elements", []):
            prefix = get_prefix(e["pid"])
            if prefix == 'ie':
                inst.elements.append(ImageElement.from_dict(e, registry))
            elif prefix == 'te':
                inst.elements.append(TextElement.from_dict(e, registry))
            else:
                raise ValueError(f"Unknown element prefix {prefix!r}")
        return inst
