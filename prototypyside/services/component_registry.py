# component_registry.py (Updated)
import json
from pathlib import Path
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QGraphicsItem
from typing import Dict, Type, Union, List, Optional # Added Optional

# Import your refactored ComponentFactory
from prototypyside.services.component_factory import ComponentFactory

# Import model classes (these are needed for type hints, but not directly mapped here)
from prototypyside.models.component_template import ComponentTemplate
from prototypyside.models.component_elements import TextElement, ImageElement
from prototypyside.models.layout_template import LayoutSlot, LayoutTemplate
from prototypyside.models.component_instance import ComponentInstance

# Import helper functions related to PIDs
from prototypyside.utils.proto_helpers import (
    VALID_ID_PREFIXES,
    ELEMENT_PREFIXES, # Still useful for registry logic like deregister
    parse_pid,
    issue_pid, # Used by registry to create new PIDs
    is_pid_prefix, # Used by registry for initial PID check in create
    get_prefix
)

# Define what prefixes correspond to elements and templates.
# These are REGISTRY-SPECIFIC concerns, not factory concerns.
ELEMENT_PID_PREFIXES = {"te", "ie"}
TEMPLATE_PID_PREFIXES = {"ct", "lt"}
INSTANCE_PID_PREFIX = "ci" # Assuming 'ci' for ComponentInstance

### All Proto Objects Must be Created Through the Registry ###
class ComponentRegistry(QObject):
    object_changed = Signal(str)  # pid
    object_removed = Signal(str)  # pid
    object_added = Signal(str)    # pid
    object_reparented = Signal(object, str, str) # obj, old_template_pid, new_template_pid

    def __init__(self):
        super().__init__()
        self._factory = ComponentFactory() # The registry holds the factory instance
        self._objects: dict[str, object] = {}
        self._name_counters = {
            'ie': [1, 'Image'],
            'te': [1, 'Text'],
            'ct': [1, 'Template'],
            'ci': [1, 'Component'] # Consistent with 'ci' prefix for ComponentInstance
        }
        self._orphans: dict[str, object] = {}
        self._unique_names: set[str] = set() # For faster name lookup and validation

    def _get_object_by_pid(self, pid: str) -> object:
        """Internal helper to get any object by PID, raising an error if not found."""
        obj = self._objects.get(pid)
        if obj is None:
            raise KeyError(f"Object with PID '{pid}' not found in registry.")
        return obj
        
    def is_orphan(self, pid):
        if pid in self._orphans:
            return True
        return False
    # --- Type-specific Getters ---
    def get_element(self, pid: str) -> Union[TextElement, ImageElement]:
        """Retrieves an Element object by its PID."""
        prefix = get_prefix(pid)
        if prefix not in ELEMENT_PID_PREFIXES:
            raise TypeError(f"PID '{pid}' (prefix: '{prefix}') is not an Element PID.")
        return self._get_object_by_pid(pid)

    def get_template(self, pid: str) -> Union[ComponentTemplate, LayoutTemplate]:
        """Retrieves a Template object by its PID."""
        prefix = get_prefix(pid)
        if prefix not in TEMPLATE_PID_PREFIXES:
            raise TypeError(f"PID '{pid}' (prefix: '{prefix}') is not a Template PID.")
        return self._get_object_by_pid(pid)

    def get_instance(self, pid: str) -> ComponentInstance:
        """Retrieves a ComponentInstance object by its PID."""
        prefix = get_prefix(pid)
        if prefix != INSTANCE_PID_PREFIX:
            raise TypeError(f"PID '{pid}' (prefix: '{prefix}') is not a ComponentInstance PID.")
        return self._get_object_by_pid(pid)

    def get_last(self):
        return list(self._objects.values())[-1]

    def get(self, pid: str) -> Optional[object]:
        """
        Generic getter for any registered object.
        Returns the object or None if not found. Use specific getters (get_element, get_template)
        if you need type guarantees.
        """
        return self._objects.get(pid)

    def has(self, pid:str) -> bool:
        return True if self.get(pid) else False

    def has_unique_name(self, obj: object) -> bool:
        """Checks if an object's current name is unique within the registry."""
        return hasattr(obj, 'name') and obj.name is not None and obj.name not in self._unique_names

    def generate_name(self, obj: object):
        """Generates and assigns a unique name to the object."""
        if self.has_unique_name(obj):
            return obj.name

        pid_prefix = get_prefix(obj.pid) # Use pid_prefix instead of just prefix
        counter, base_name = self._name_counters.get(pid_prefix, [1, pid_prefix.capitalize()])

        # If a new name is generated, ensure it's not a name of a current object
        # that already exists but might not be in _unique_names (e.g., loaded without registration)
        # This check is less critical if all object creation/loading goes through register.
        # However, for robustness, it's safer to cross-check.
        existing_names_in_registry = {o.name for o in self._objects.values() if hasattr(o, 'name') and o.name is not None}
        self._unique_names.update(existing_names_in_registry) # Ensure _unique_names is up-to-date

        while True:
            candidate = f"{base_name} {counter}"
            if candidate not in self._unique_names:
                break
            counter += 1

        self._name_counters[pid_prefix][0] = counter + 1 # Update counter for this prefix
        obj.name = candidate # Assign the generated name to the object
        self._unique_names.add(candidate) # Add the new name to the set of unique names
        return candidate

    def register(self, obj: object):
        """Registers an object in the registry."""
        pid = obj.pid
        if not pid:
            raise ValueError("Object must have a pid to be registered.")
        if pid in self._objects:
            # This case might happen during deserialization if an object is added
            # to a template and then registered. Decide if this should overwrite or error.
            # For now, it overwrites but prints a warning.
            print(f"Warning: Object with PID '{pid}' is being re-registered. Overwriting existing entry.")

        self._objects[pid] = obj
        if hasattr(obj, 'name') and obj.name:
            self._unique_names.add(obj.name)

        self.object_added.emit(pid)
        # Connect known signals. Consider defining a method on ComponentBase
        # (if you have one) that connects its signals to the registry,
        # or a dedicated signal connector.
        if hasattr(obj, "element_changed"):
            obj.element_changed.connect(lambda: self.object_changed.emit(pid))
        if hasattr(obj, "template_changed"):
            obj.template_changed.connect(lambda: self.object_changed.emit(pid))
        if hasattr(obj, "update_cache"):
            obj.update_cache.connect(lambda: self.object_changed.emit(pid))

    def create(self, prefix_or_pid: str, **kwargs) -> object:
        """
        Creates a new object using the factory and registers it.
        If prefix_or_pid is a prefix (e.g., 'te'), a new PID will be issued by proto_helpers.
        If prefix_or_pid is a full PID, it will be used (e.g., for deserialization/re-creation).
        """
        final_pid = prefix_or_pid
        if is_pid_prefix(prefix_or_pid):
            final_pid = issue_pid(prefix_or_pid) # Registry's responsibility to issue PIDs

        # Factory creates the raw object instance
        obj = self._factory.create(pid=final_pid, **kwargs)

        # Registry handles name generation and registration
        self.generate_name(obj)
        self.register(obj)
        # Registry handles initial parenting/relationship wiring
        template_pid = getattr(obj, "template_pid", None)
        if template_pid:
            try:
                template = self.get_template(template_pid) # Ensure it's a valid template
                template.add_element(obj) # Template's add_element should manage its internal list and set obj.template_pid
            except (KeyError, TypeError) as e:
                print(f"Warning: Object '{obj.pid}' created with invalid template_pid '{template_pid}': {e}. Object is now unparented (orphan).")
                self._orphans[obj.pid] = obj
                setattr(obj, "template_pid", None) # Clear invalid template reference

        return obj

    def clone(self, obj: object = None) -> object:
        """Clones an existing object, generates a new PID, and registers the clone."""
        if not hasattr(obj, 'pid'):
            raise ValueError("Object to clone must have a 'pid' attribute.")

        prefix = get_prefix(obj.pid)
        new_pid = issue_pid(prefix) # Registry uses proto_helpers to issue a new PID

        # Factory creates the raw clone object (assuming obj.clone() returns a new instance)
        if not hasattr(obj, 'clone') or not callable(obj.clone):
            raise TypeError(f"Object type {type(obj).__name__} does not have a callable 'clone' method.")
        clone_data = obj.to_dict() # Serialize to dict
        clone_data["pid"] = new_pid # Override PID for the clone
        
        clone = obj.from_dict(clone_data) # Reconstruct using factory
        # clone.pid = new_pid
        self.generate_name(clone) # Registry handles name generation
        self.register(clone) # Registry registers the clone
        # If the original object had a parent, attempt to attach the clone to the same parent
        template_pid = getattr(obj, "template_pid", None)
        if template_pid:
            try:
                template = self.get(template_pid)
                # `set_template` should handle updating clone's template_pid (if your elements have it)
                # and template.add_element should ensure its internal list is updated.
                template.add_element(clone)
            except (KeyError, TypeError) as e:
                print(f"Warning: Could not attach cloned object '{clone.pid}' to original template '{template_pid}': {e}. Clone is orphaned.")
                self._orphans[clone.pid] = clone
                setattr(clone, "template_pid", None) # Ensure clone is marked as unparented if parent fails

        return clone

    def replace(self, pid: str, new_obj: object):
        """
        Replaces the object with the given pid with a new instance.
        The new_obj must already be an instantiated object (likely from factory or other source).
        """
        if not self.contains(pid):
            raise KeyError(f"No object with pid '{pid}' found to replace.")
        if not hasattr(new_obj, 'pid') or new_obj.pid != pid:
            raise ValueError(f"New object must have a 'pid' attribute matching '{pid}' for replacement.")

        old_obj = self._objects[pid]
        # Clean up old name from _unique_names set if it was unique
        if hasattr(old_obj, 'name') and old_obj.name and old_obj.name in self._unique_names:
            self._unique_names.discard(old_obj.name)

        # Disconnect signals (assuming PySide6's QObject parent-child or explicit disconnects in models)
        # For a truly robust signal disconnection, you'd need to store the connection objects
        # when registering and disconnect them explicitly here. For now, rely on QObject lifecycle.

        # Replace object in internal dictionary
        self._objects[pid] = new_obj

        # Add new object's name to set (if it has one)
        if hasattr(new_obj, 'name') and new_obj.name:
            self._unique_names.add(new_obj.name)

        # Reconnect signals for the new object (similar to register)
        if hasattr(new_obj, "element_changed"):
            new_obj.element_changed.connect(lambda: self.object_changed.emit(pid))
        if hasattr(new_obj, "template_changed"):
            new_obj.template_changed.connect(lambda: self.object_changed.emit(pid))
        if hasattr(new_obj, "update_cache"):
            new_obj.update_cache.connect(lambda: self.object_changed.emit(pid))

        self.object_changed.emit(pid)

    def deregister(self, pid: str):
        """Deregisters an object. If it's an element, it's moved to orphans and detached from its template."""
        if not self.has(pid):
            print(f"Warning: Attempted to deregister non-existent object with PID '{pid}'.")
            return

        obj = self.get(pid)
        template = None

        # Try to get template (if available)
        if getattr(obj, "template_pid", None):
            try:
                template = self.get(obj.template_pid)
            except KeyError:
                print(f"Warning: No template found for template_pid '{obj.template_pid}'")

        # Remove element from template if possible
        if template:
            try:
                template.remove_element(obj)
            except (AttributeError, ValueError):
                print(f"Warning: Could not remove element '{obj.pid}' from template '{obj.template_pid}'")

        # Move to orphans
        self._orphans[obj.pid] = obj

        # Clean up name from _unique_names set
        if hasattr(obj, 'name') and obj.name and obj.name in self._unique_names:
            self._unique_names.discard(obj.name)

        del self._objects[pid]
        self.object_removed.emit(pid)


    def reinsert(self, pid: str):
        """Reinserts an orphaned object back into the registry and its template."""
        if pid not in self._orphans:  # FIX: Changed to self._orphans
            raise KeyError(f"Object with PID '{pid}' is not in orphans.")
        if pid in self._objects:
            print(f"Warning: Object with PID '{pid}' is already registered. Not reinserting.")
            return

        obj = self._orphans.pop(pid)
        self.register(obj) # Re-register
        template_pid = getattr(obj, "template_pid", None)
        if template_pid:
            try:
                template = self.get(template_pid)
                template.add_element(obj) # Template should manage its element_pids and set child's template_pid
            except (KeyError, TypeError) as e:
                print(f"Warning: Could not re-attach object '{pid}' to template '{template_pid}' after reinsert: {e}. Object remains in registry but unparented.")
                setattr(obj, "template_pid", None) # Ensure it's marked as unparented if parent fails

    def reparent(self, element_pid: str, new_template_pid: str):
        """
        Move an element to a new template.

        Parameters
        ----------
        element_pid : str
            The PID of the object (must be an Element) to reparent.
        new_template_pid : str
            The PID of the new parent template.

        Raises
        ------
        ValueError
            If the element or new template are not found in the registry.
        TypeError
            If the provided PIDs do not correspond to the expected types (Element, Template).
        """
        element = self.get_element(element_pid)
        new_template = self.get_template(new_template_pid)

        old_template_pid = getattr(element, "template_pid", None)

        if old_template_pid == new_template_pid:
            print(f"Info: Element '{element_pid}' is already parented to '{new_template_pid}'. No action taken.")
            return

        # Remove from old parent if it exists
        if old_template_pid:
            try:
                old_template = self.get_template(old_template_pid)
                old_template.remove_element(element_pid)
            except (KeyError, TypeError) as e:
                print(f"Warning: Data inconsistency for element '{element_pid}'. Old template PID '{old_template_pid}' is invalid or not found during reparent: {e}")

        # Add to new parent
        new_template.add_element(element)

        # Emit signals
        self.object_reparented.emit(element, old_template_pid, new_template_pid)
        self.object_changed.emit(element_pid)
        self.object_changed.emit(new_template_pid)
        if old_template_pid:
            self.object_changed.emit(old_template_pid)

    def parent_of(self, pid: str) -> Optional[Union[QObject, QGraphicsItem, object]]:
        """
        Determines the parent of an object based on logical (template_pid),
        QObject, or QGraphicsItem parenting.
        """
        obj = self.get(pid)
        if obj is None:
            return None

        # 1. Logical parenting first (preferred for elements & slots)
        tpl_pid = getattr(obj, "template_pid", None)
        if tpl_pid:
            try:
                return self.get_template(tpl_pid)
            except (KeyError, TypeError):
                pass # This PID existed but wasn't a template, or wasn't found in registry

        # 2. Fallback: QObject parenting
        if isinstance(obj, QObject):
            q_parent = obj.parent()
            if q_parent and hasattr(q_parent, 'pid') and self.contains(q_parent.pid):
                return q_parent

        # 3. Fallback: QGraphicsItem hierarchy
        if isinstance(obj, QGraphicsItem):
            qgi_parent = obj.parentItem()
            if qgi_parent and hasattr(qgi_parent, 'pid') and self.contains(qgi_parent.pid):
                return qgi_parent

        return None

    def contains(self, pid: str) -> bool:
        """Checks if an object with the given PID is in the registry."""
        return pid in self._objects

    def get_all(self, prefix: str = None) -> Dict[str, object]:
        """
        Gets all registered objects, optionally filtered by PID prefix.
        Returns a dictionary of PID -> object.
        """
        if prefix is None:
            return self._objects.copy()
        elif prefix in VALID_ID_PREFIXES:
            return {
                pid: obj for pid, obj in self._objects.items()
                if pid.startswith(prefix)
            }
        else:
            raise ValueError(f"{prefix} is not a valid ProtoObject prefix")

    def clear(self):
        """Clears all objects from the registry."""
        self._objects.clear()
        self._orphans.clear()
        self._unique_names.clear()
        # Reset name counters if desired, e.g., self._name_counters = initial_state_dict

    # --- Serialization ---
    def obj_to_dict(self, pid: str) -> dict:
        """Converts a single object to its dictionary representation using the factory."""
        obj = self._get_object_by_pid(pid)
        return self._factory.to_dict(obj)

    def obj_from_dict(self, data: dict):
        """Instantiates and registers an object from dictionary data using the factory."""
        # Factory handles reconstruction from dict data
        obj = self._factory.from_dict(data)
        # Registry handles name generation and registration after factory creates
        self.generate_name(obj)
        self.register(obj)
        return obj

    def to_dict(self) -> dict:
        """Serializes the entire registry to a dictionary using the factory."""
        return {pid: self._factory.to_dict(obj) for pid, obj in self._objects.items()}

    def from_dict(self, data: dict):
        """
        Rebuilds the registry from a dict of pid -> obj_data.
        1. Clear any existing objects.
        2. Instantiate & register every object using the factory.
        3. Wire up relationships (parenting).
        """
        
        self.clear() # Clear existing objects and internal states

        # Pass 1: Instantiate and register all objects
        for pid_str, obj_data in data.items():
            try:
                # Factory reconstructs the object from its dict data
                obj = self._factory.from_dict(obj_data)
                self.register(obj) # Register the reconstructed object
            except Exception as e:
                print(f"Error loading object with PID '{pid_str}' during deserialization: {e}. Skipping this object.")
                continue

        # Pass 2: Wire up relationships (parenting)
        for obj in self._objects.values():
            tpl_pid = getattr(obj, "template_pid", None)
            if tpl_pid:
                try:
                    tpl = self.get_template(tpl_pid) # Ensure it's a valid template
                    # obj.set_template(tpl) # Uncomment if your object models need this direct reference
                    tpl.add_element(obj) # Template manages its element_pids and ensures child's template_pid is set
                except (KeyError, TypeError) as e:
                    print(f"Warning: During deserialization, object '{obj.pid}' referenced an invalid template '{tpl_pid}': {e}. Object marked as unparented.")
                    setattr(obj, "template_pid", None) # Clear invalid template reference
                    self._orphans[obj.pid] = obj # Mark as orphan

    # --- File-level save/load with root ---
    def save_to_file(self, root_pid: str, path: Union[str, Path]):
        """Saves the entire registry to a JSON file, including the root PID."""
        if not self.contains(root_pid):
            raise ValueError(f"Root PID '{root_pid}' not found in registry. Cannot save with a non-existent root.")

        data = {
            "root": root_pid,
            "objects": self.to_dict() # Uses registry's to_dict, which uses factory's to_dict
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_from_file(self, path: Union[str, Path]) -> object:
        """
        Loads the registry from a JSON file.
        Returns the root component object.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        root_pid = data.get("root")
        if not root_pid:
            raise ValueError("Saved file is missing 'root' PID.")
        if "objects" not in data:
            raise ValueError("Saved file is missing 'objects' data.")

        self.from_dict(data["objects"]) # This will load all objects and wire them up

        try:
            # Assume root is always a template based on your discussion
            root = self.get_template(root_pid)
        except (KeyError, TypeError) as e:
            raise ValueError(f"Root object with PID '{root_pid}' could not be retrieved as a valid template after loading: {e}")

        # print(f"Root contains elements: {root.elements}") # For debugging/verification
        return root