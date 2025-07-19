from typing import Dict, Any, TYPE_CHECKING

class PageModel
    pid: str 

    def to_dict(self) -> Dict[str, Any]:
        data = {
            'pid': self._pid,
            'name': self._name,
            'geometry': self._geometry.to_dict(),
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
