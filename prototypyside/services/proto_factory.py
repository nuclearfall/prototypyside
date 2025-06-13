import re
import uuid
import json
from typing import Optional, Dict, Tuple, Type, Union, List
from pathlib import Path

from prototypyside.models.component_template import ComponentTemplate
from prototypyside.models.component_elements import TextElement, ImageElement
from prototypyside.models.layout_template import LayoutSlot, LayoutTemplate

from prototypyside.models.component_instance import ComponentInstance
from prototypyside.utils.proto_helpers import (
    VALID_ID_PREFIXES,
    ELEMENT_PREFIXES,
    parse_pid,
    issue_pid,
    is_pid,
    is_pid_prefix,
    get_prefix,
)

PROTO_OBJECTS: Dict[str, Type] = {
"te": TextElement,
"ie": ImageElement,
"ct": ComponentTemplate,
"ci": ComponentInstance,
"lt": LayoutTemplate,
"ls": LayoutSlot,
}

class ProtoFactory:
    """
    A class for generating, validating, and managing proto IDs and proto objects.
    """

    # Validate consistency
    
    def register_class(self, prefix: str, cls: type):
        if prefix in PROTO_OBJECTS:
            raise ValueError(f"Prefix '{prefix}' is already registered.")
        PROTO_OBJECTS[prefix] = cls

    def protoid(self, pid_str: str) -> str:
        prefix, uuid_str = parse_pid(pid_str)

        if prefix is None or prefix not in VALID_ID_PREFIXES:
            raise ValueError(f"'{prefix}' is not a valid prefix. Must be one of {VALID_ID_PREFIXES}")

        if uuid_str:
            try:
                uuid_obj = uuid.UUID(uuid_str, version=4)
                return f"{prefix}_{uuid_obj.hex}"
            except (ValueError, TypeError, AttributeError):
                pass  # Fall through and issue a new one

        return issue_pid(prefix)

    def get_object_type(self, pid_str: str) -> Optional[Type]:
        """
        Returns the Python class/type associated with a given pid's prefix.
        """
        prefix = get_prefix(pid_str)
        if prefix in PROTO_OBJECTS:
            return PROTO_OBJECTS[prefix]
        return None

    def create(self, pid: str, **kwargs):
        obj_type = self.get_object_type(pid)

        if not obj_type:
            raise ValueError(f"No object type mapped for pid prefix in: {pid}")

        # Create the object
        obj = obj_type(pid=pid, **kwargs)

        # Safely add to template if defined
        template = getattr(obj, "template", None)
        if template:
            template.add_item(obj)
        return obj


    def from_dict(self, data: dict):
        final_pid = self.pid(data["pid"])
        obj_type = self.get_object_type(final_pid)
        if obj_type and hasattr(obj_type, "from_dict"):
            return obj_type.from_dict(data)
        raise ValueError(f"Cannot construct object for pid: {final_pid}")

    def save(self, path: Union[str, Path], objects: List[object]):
        """Save a list of proto objects to a file as JSON."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump([obj.to_dict() for obj in objects], f, indent=2)

    def load(self, path: Union[str, Path]) -> List[object]:
        """Load proto objects from a file, reconstructing them by pid."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("Saved proto file must contain a list of objects.")

        objects = []
        for entry in data:
            pid_str = entry.get("pid")
            if not pid_str:
                continue  # or raise
            obj_type = self.get_object_type(pid_str)
            if obj_type and hasattr(obj_type, "from_dict"):
                objects.append(obj_type.from_dict(entry))
        return objects