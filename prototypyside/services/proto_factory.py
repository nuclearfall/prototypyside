# proto_factory.py
import uuid
import json
from typing import Optional, Dict, Type, Union, List
from pathlib import Path

# Import your model classes
from prototypyside.models.component_template import ComponentTemplate
from prototypyside.models.component import Component
from prototypyside.models.component_elements import TextElement, ImageElement
from prototypyside.models.layout_template import LayoutSlot, LayoutTemplate

# Import helper functions related to PIDs
from prototypyside.utils.proto_helpers import (
    VALID_ID_PREFIXES,
    parse_pid,
    issue_pid, # For generating new PIDs
    get_prefix,
    is_pid_prefix # For checking if a string is just a prefix
)

class ProtoFactory:
    """
    A class responsible *only* for creating and validating individual proto objects
    based on their PID prefix and data.
    It does NOT manage collections of objects, their relationships, or naming.
    """
    _PROTO_OBJECT_CLASSES: Dict[str, Type] = {
        "te": TextElement,
        "ie": ImageElement,
        "ct": ComponentTemplate,
        "ci": Component,
        "lt": LayoutTemplate,
        "ls": LayoutSlot,
    }

    def __init__(self):
        # The factory itself doesn't need to hold state about created objects
        # or manage name counters. Those are registry concerns.
        pass

    def register_class(self, prefix: str, cls: Type):
        """
        Registers a new class with a given PID prefix.
        Raises ValueError if the prefix is already registered.
        """
        if prefix in self._PROTO_OBJECT_CLASSES:
            raise ValueError(f"Prefix '{prefix}' is already registered with {self._PROTO_OBJECT_CLASSES[prefix].__name__}.")
        if prefix not in VALID_ID_PREFIXES:
             raise ValueError(f"Prefix '{prefix}' is not a valid ID prefix. Must be one of {VALID_ID_PREFIXES}.")
        self._PROTO_OBJECT_CLASSES[prefix] = cls

    def get_object_type(self, pid_str: str) -> Optional[Type]:
        """
        Returns the Python class/type associated with a given PID's prefix.
        Returns None if no type is mapped for the prefix.
        """
        prefix = get_prefix(pid_str) # Assume get_prefix handles invalid PID_STR formats by returning None or raising
        return self._PROTO_OBJECT_CLASSES.get(prefix)

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

    def from_dict(self, data: dict, registry=None) -> object:
        pid = data.get("pid")
        if not pid:
            raise ValueError("Missing 'pid' in object data for factory reconstruction.")

        obj_type = self.get_object_type(pid)
        if not obj_type or not hasattr(obj_type, "from_dict"):
            raise TypeError(f"Cannot reconstruct type from PID '{pid}'")

        obj = obj_type.from_dict(data)  # Basic construction

        # Post-process children using factory if needed
        if isinstance(obj, ComponentTemplate) and "elements" in data:
            obj.elements = [self.from_dict(ed, registry) for ed in data["elements"]]
        elif isinstance(obj, LayoutTemplate) and "slots" in data:
            obj.slots = [
                [self.from_dict(sd, registry) for sd in row] for row in data["slots"]
            ]

        return obj

    def to_dict(self, obj: object) -> dict:
        """
        Converts an object to its dictionary representation.
        Assumes the object has a .to_dict() method.
        """
        if not hasattr(obj, "to_dict") or not callable(obj.to_dict):
            raise TypeError(f"Object of type {type(obj).__name__} does not have a callable 'to_dict' method.")
        return obj.to_dict()

