<<<<<<< Updated upstream
# proto_factory.py
from typing import Optional, Dict, Type, Union, List
import importlib

# Import your model classes
from prototypyside.models.component_template import ComponentTemplate
from prototypyside.models.component_elements import TextElement, ImageElement
from prototypyside.models.layout_template import LayoutTemplate
from prototypyside.models.layout_slot import LayoutSlot


# Import helper functions related to PIDs
from prototypyside.utils.proto_helpers import MODEL_ONLY, get_prefix


def get_class_from_name(module_path, class_name):
    module = importlib.import_module(module_path)
    return getattr(module, class_name)
=======
from typing import Any, Dict, Optional
from pydantic import ValidationError
import uuid

from your_module_path.schema_registry import SchemaRegistry # Adjust import path as needed
from prototypyside.models.component_template_model.py import ComponentTemplateModel
# Assume ComponentTemplateModel is defined in app.models
# For this example, let's define a minimal version if app.models isn't available
# In a real application, this would be imported from your models module.
try:
    from app.models 
except ImportError:
    # Fallback for demonstration if app.models is not set up
    from pydantic import BaseModel, Field
    class ComponentTemplateModel(BaseModel):
        pid: str = Field(..., description="Unique persistent identifier for the component.")
        geometry: str = Field(..., description="Serialized geometry data.") # Using str for simplicity
        name: str = "Unnamed Component"
        description: Optional[str] = None

# Assume UnitStr and UnitStrGeometry are defined types or classes elsewhere.
# For demonstration, we'll treat them as strings.
>>>>>>> Stashed changes

# Import the SchemaRegistry. In a real application, this might be passed via DI.
_PROTO_OBJECT_CLASSES: Dict[str, Type] = {
    "te": TextElement,
    "ie": ImageElement,
    "ct": ComponentTemplate,
    "cc": ComponentTemplate,
    "lt": LayoutTemplate,
    "pg": LayoutTemplate,
    "ls": LayoutSlot,
}

class PidGenerator:
    """
    A simple service responsible for generating unique Persistent Identifiers (PIDs).
    This could be a more complex service interacting with a database or a distributed ID system.
    """
<<<<<<< Updated upstream

    _PROTO_OBJECT_CLASSES: Dict[str, Type] = {
        "te": TextElement,
        "ie": ImageElement,
        "ct": ComponentTemplate,
        "cc": ComponentTemplate,
        "lt": LayoutTemplate,
        "pg": LayoutTemplate,
        "ls": LayoutSlot,
        "ug": UnitStrGeometry,
        "us": UnitStr,
    }
=======
>>>>>>> Stashed changes


class ComponentFactory:
    def __init__(self, schema_registry: SchemaRegistry, pid_generator: PidGenerator):
        """
        Initializes the ComponentFactory with a SchemaRegistry and a PidGenerator.
        These dependencies are injected to maintain separation of concerns and testability.
        """
<<<<<<< Updated upstream
        if prefix in self._PROTO_OBJECT_CLASSES:
            raise ValueError(f"Prefix '{prefix}' is already registered with {self._PROTO_OBJECT_CLASSES[prefix].__name__}.")
        if prefix not in REGISTERED_PREFIXES:
             raise ValueError(f"Prefix '{prefix}' is not a valid ID prefix. Must be one of {REGISTERED_PREFIXES}.")
        self._PROTO_OBJECT_CLASSES[prefix] = cls
=======
        self.schema_registry = schema_registry
        self.pid_generator = pid_generator

    def issue_pid(self, prefix: str = None, model_name: str) -> str:
        """Generates a unique PID with an optional prefix."""
        if not prefix and not model_name:
            raise E
        if prefix not in VALID_ID_PREFIXES:
            raise ValueError(f"Invalid prefix '{prefix}'. Valid: {VALID_ID_PREFIXES}")
        return f"{prefix}_{uuid.uuid4().hex}"
>>>>>>> Stashed changes

    def create(self,
               model_cls: Type[Struct],
               **overrides) -> Struct:
        # merge defaults, auto-PID, auto-name, etc.
        merged = { **schema_defaults, **overrides }
        
        # (optional) validate the *merged* dict too,
        # if you want to ensure your default injection hasn't broken the schema:
        ok, err = self.validator.validate(merged)
        if not ok:
            raise ValueError(f"Schema validation after defaults failed: {err}")

        # finally instantiate
        return model_cls(**merged)

    def load(self,
             model_cls: Type[Struct],
             data: dict) -> Struct:
        # 1) Structural check against JSON Schema
        ok, err = self.validator.validate(data)
        if not ok:
            raise ValueError(f"Schema validation failed: {err}")

        # 2) msgspec will now enforce no extra fields and correct types
        model = model_cls(**data)

        return model

    def dumps(self, obj: object) -> dict:
        # for JSON serialization
        return msgspec.json.encode(obj, indent=2)


# Example usage (these lines would typically be in your main application setup or a test file):
# from your_module_path.schema_registry import SchemaRegistry # Ensure this import is correct
# schema_registry = SchemaRegistry()
# pid_generator = PidGenerator()
# component_factory = ComponentFactory(schema_registry, pid_generator)

# # Create a component with minimal data, letting factory handle defaults and pid generation
# # For this to work, you'd need a 'ComponentTemplateModel.json' file in your 'schemas' directory
# # For example: {"properties": {"name": {"type": "string", "default": "Default Component"}}}
# try:
#     my_component = component_factory.create_component("ComponentTemplateModel", {"geometry": "some_geometry_string"})
#     print(f"Created component: {my_component.pid}, Name: {my_component.name}, Geometry: {my_component.geometry}")
# except Exception as e:
#     print(f"Error creating component: {e}")

# # Create another component with more specific data, overriding defaults
# try:
#     another_component = component_factory.create_component("ComponentTemplateModel", {
#         "pid": "custom-123",
#         "geometry": "another_geometry_string",
#         "name": "My Custom Widget",
#         "description": "A widget created with specific parameters."
#     })
#     print(f"Created component: {another_component.pid}, Name: {another_component.name}, "
#           f"Description: {another_component.description}, Geometry: {another_component.geometry}")
# except Exception as e:
#     print(f"Error creating another component: {e}")

# # Example of missing mandatory field
# try:
#     missing_geometry_component = component_factory.create_component("ComponentTemplateModel", {"name": "Invalid Component"})
#     print(missing_geometry_component)
# except ValueError as e:
#     print(f"Successfully caught expected error: {e}")

# # proto_factory.py
# import uuid
# import json
# from typing import Optional, Dict, Type, Union, List
# from pathlib import Path

# # Import your model classes
# from prototypyside.models.component_template import ComponentTemplate
# from prototypyside.models.component_elements import TextElement, ImageElement
# from prototypyside.models.layout_template import LayoutTemplate
# from prototypyside.models.layout_slot import LayoutSlot

# # Import helper functions related to PIDs
# from prototypyside.utils.proto_helpers import (
#     VALID_ID_PREFIXES,
#     parse_pid,
#     issue_pid, # For generating new PIDs
#     get_prefix,
#     is_pid_prefix # For checking if a string is just a prefix
# )

# class ProtoFactory:
#     """
#     A class responsible *only* for creating and validating individual proto objects
#     based on their PID prefix and data.
#     It does NOT manage collections of objects, their relationships, or naming.
#     """


#     def __init__(self):
#         # The factory itself doesn't need to hold state about created objects
#         # or manage name counters. Those are registry concerns.
#         pass

#     def create_model(self,
#                      model_cls: Type,
#                      data: dict,
#                      auto_name: bool = True) -> Any:
#         # 1) Pull schema defaults
#         schema = self.get_schema_for(model_cls)
#         defaults = extract_defaults(schema)

#         # 2) Merge defaults + incoming data
#         merged = {**defaults, **data}

#         # 3) Ensure pid
#         if "pid" not in merged:
#             merged["pid"] = self._generate_pid()

#         # 4) Auto-name only for create()
#         if auto_name and not merged.get("name"):
#             merged["name"] = self._generate_name(model_cls)

#         # 5) Instantiate
#         model = model_cls.from_dict(merged)
#         return model

#     # def create_model(self, model_cls, data: dict, auto_name=True):
#     #     schema  = self.get_schema_from_model_cls(model_cls)
#     #     defaults = extract_schema_defaults(schema)
        
#     #     merged = {**defaults, **data}
#     #     if "pid" not in merged:
#     #         merged["pid"] = self._generate_pid()
#     #     if auto_name and not merged.get("name"):
#     #         merged["name"] = self._generate_name(model_cls)
        
#     #     # optional: jsonschema.validate(merged, schema)
#     #     return model_cls.from_dict(merged)

#     def _get_prefix_from_schema(self, data):
#         if data.get("")
#         for prefix, model_cls_str in self._PROTO_OBJECT_CLASSES.items():
#             if 
#             if isinstance(model_cls, model):
#                 return prefix

#     def create_model(self,
#                      model_cls: Type,
#                      data: dict,
#                      registry=None,
#                      auto_name: bool = True):
#         # 1) pull in schema defaults
#         schema   = self.get_schema_for(model_cls)
#         defaults = extract_schema_defaults(schema)

#         # 2) merge defaults + user data
#         merged = {**defaults, **(data or {})}

#         # 3) ensure pid
#         if "pid" not in merged:
#             merged["pid"] = self._generate_pid()

#         # 4) only auto-name on create
#         if auto_name and not merged.get("name"):
#             merged["name"] = self._generate_name(model_cls)

#         # 5) hand off to your low-level from_dict
#         return self.from_dict(merged,
#                               registry=registry,
#                               is_clone=False)

#     def load_model(self,
#                    model_cls: Type,
#                    data: dict,
#                    registry=None):
#         # Exactly the same, but suppress auto-naming so
#         # we preserve the serialized 'name'
#         return self.create_model(model_cls,
#                                  data,
#                                  registry=registry,
#                                  auto_name=False)

#     # def register_class(self, prefix: str, cls: Type):
#     #     """
#     #     Registers a new class with a given PID prefix.
#     #     Raises ValueError if the prefix is already registered.
#     #     """
#     #     if prefix in self._PROTO_OBJECT_CLASSES:
#     #         raise ValueError(f"Prefix '{prefix}' is already registered with {self._PROTO_OBJECT_CLASSES[prefix].__name__}.")
#     #     if prefix not in VALID_ID_PREFIXES:
#     #          raise ValueError(f"Prefix '{prefix}' is not a valid ID prefix. Must be one of {VALID_ID_PREFIXES}.")
#     #     self._PROTO_OBJECT_CLASSES[prefix] = cls

#     def get_object_type(self, pid_str: str) -> Optional[Type]:
#         """
#         Returns the Python class/type associated with a given PID's prefix.
#         Returns None if no type is mapped for the prefix.
#         """
#         prefix = get_prefix(pid_str) # Assume get_prefix handles invalid PID_STR formats by returning None or raising
#         return self._PROTO_OBJECT_CLASSES.get(prefix)

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
        

#     def from_dict(self, data: dict, registry=None, is_clone=False) -> object:
#         pid = data.get("pid")
#         if not pid:
#             raise ValueError("Missing 'pid' in object data for factory reconstruction.")

#         obj_type = self.get_object_type(pid)
#         if not obj_type or not hasattr(obj_type, "from_dict"):
#             raise TypeError(f"Cannot reconstruct object for PID '{pid}'")

#         try:
#             # Keyword args guard against signature changes
#             return obj_type.from_dict(data=data, registry=registry, is_clone=is_clone)
#         except Exception as e:
#             raise RuntimeError(f"Error reconstructing {obj_type.__name__} (PID={pid}): {e}") from e

#     def to_dict(self, obj: object) -> dict:
#         if not hasattr(obj, "to_dict") or not callable(obj.to_dict):
#             raise TypeError(f"{type(obj).__name__} has no callable to_dict()")
#         return obj.to_dict()


