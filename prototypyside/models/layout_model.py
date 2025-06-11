from dataclasses import dataclass, field, asdict
from typing import List, Tuple, Optional, Dict
import json


@dataclass
class LayoutSlot:
    position: Tuple[float, float]  # x, y in scene coordinates
    rotation: float = 0.0          # Optional
    scale: float = 1.0             # Optional
    slot_id: Optional[str] = None  # For future identification

    def to_dict(self) -> Dict:
        return {
            "position": list(self.position),
            "rotation": self.rotation,
            "scale": self.scale,
            "slot_id": self.slot_id,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "LayoutSlot":
        return cls(
            position=tuple(data["position"]),
            rotation=data.get("rotation", 0.0),
            scale=data.get("scale", 1.0),
            slot_id=data.get("slot_id"),
        )


@dataclass
class LayoutModel:
    name: str
    page_size: Tuple[float, float]  # Width, height in points or mm
    associated_template_name: str
    layout_slots: List[LayoutSlot] = field(default_factory=list)
    export_quantity: Optional[int] = None  # Global override for no-CSV use

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "page_size": list(self.page_size),
            "associated_template_name": self.associated_template_name,
            "layout_slots": [slot.to_dict() for slot in self.layout_slots],
            "export_quantity": self.export_quantity,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "LayoutModel":
        return cls(
            name=data["name"],
            page_size=tuple(data["page_size"]),
            associated_template_name=data["associated_template_name"],
            layout_slots=[LayoutSlot.from_dict(s) for s in data.get("layout_slots", [])],
            export_quantity=data.get("export_quantity"),
        )

    def save_to_file(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, path: str) -> "LayoutModel":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
