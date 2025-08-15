# proto_factory.py
from typing import Any, Optional, Dict, Type, Union, List
import importlib
import uuid
# Import your model classes
from prototypyside.models.component_template import ComponentTemplate
from prototypyside.models.component_element import ComponentElement
from prototypyside.models.text_element import TextElement
from prototypyside.models.image_element import ImageElement
from prototypyside.models.vector_element import VectorElement
from prototypyside.models.layout_template import LayoutTemplate
from prototypyside.models.layout_slot import LayoutSlot
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.units.unit_str import UnitStr

# Import helper functions related to PIDs
from prototypyside.utils.proto_helpers import get_prefix


def get_class_from_name(module_path, class_name):
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class ProtoFactory:
    _PROTO_OBJECT_CLASSES: Dict[str, Type] = {
        "te": TextElement,
        "ie": ImageElement,
        "ve": VectorElement,
        "ct": ComponentTemplate,
        "cc": ComponentTemplate,
        "lt": LayoutTemplate,
        "pg": LayoutTemplate,
        "ls": LayoutSlot,
        "ug": UnitStrGeometry,
        "us": UnitStr,
    }
    # def __init__(self, prefix):
    #     if prefix in self._PROTO_OBJECT_CLASSES:
    #         raise ValueError(f"Prefix '{prefix}' is already registered with {self._PROTO_OBJECT_CLASSES[prefix].__name__}.")
    #     if prefix not in REGISTERED_PREFIXES:
    #          raise ValueError(f"Prefix '{prefix}' is not a valid ID prefix. Must be one of {REGISTERED_PREFIXES}.")
    #     self._PROTO_OBJECT_CLASSES[prefix] = cls

    #     # self.schema_registry = schema_registry
    #     # self.pid_generator = pid_generator
    def create(self, pid: str, **kwargs) -> object:
        """
        Creates a new object instance using the provided PID and keyword arguments.
        The PID must be a full, valid object PID (e.g., 'te_abcdef123456...').
        The factory does not issue new PIDs in this method; it assumes the PID is ready.

        Parameters
        ----------
        pid : str
            The full PID for the object to create.
        **kwargs : dict
            Keyword arguments to pass to the object's constructor.

        Returns
        -------
        object
            An instantiated object of the type determined by the PID's prefix.

        Raises
        ------
        ValueError
            If no object type is mapped for the PID's prefix.
        TypeError
            If the object type cannot be instantiated with the provided kwargs.
        """
        obj_type = self.get_object_type(pid)
        if not obj_type:
            raise ValueError(f"No object type mapped for PID prefix: {pid}")

        return obj_type(pid=pid, **kwargs)

    def get_object_type(self, pid_str: str) -> Optional[Type]:
        """
        Returns the Python class/type associated with a given PID's prefix.
        Returns None if no type is mapped for the prefix.
        """
        prefix = get_prefix(pid_str) # Assume get_prefix handles invalid PID_STR formats by returning None or raising
        return self._PROTO_OBJECT_CLASSES.get(prefix)


    def from_dict(self, data: dict, registry=None, is_clone=False) -> object:
        pid = data.get("pid")
        if not pid:
            raise ValueError("Missing 'pid' in object data for factory reconstruction.")

        obj_type = self.get_object_type(pid)
        if not obj_type or not hasattr(obj_type, "from_dict"):
            raise TypeError(f"Cannot reconstruct object for PID '{pid}'")

        try:
            # Keyword args guard against signature changes
            return obj_type.from_dict(data=data, registry=registry, is_clone=is_clone)
        except Exception as e:
            raise RuntimeError(f"Error reconstructing {obj_type.__name__} (PID={pid}): {e}") from e

    def to_dict(self, obj: object) -> dict:
        if not hasattr(obj, "to_dict") or not callable(obj.to_dict):
            raise TypeError(f"{type(obj).__name__} has no callable to_dict()")
        return obj.to_dict()


