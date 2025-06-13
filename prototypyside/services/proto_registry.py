from PySide6.QtCore import QObject, Signal
import json

from prototypyside.utils.proto_helpers import (
    VALID_ID_PREFIXES,
    ELEMENT_PREFIXES,
    parse_pid,
    get_prefix,
    issue_pid,
    is_pid_prefix,
)
from prototypyside.services.proto_factory import ProtoFactory
# from prototypyside.models.component_template import ComponentTemplate



class ProtoRegistry(QObject):
    object_changed = Signal(str)
    object_removed = Signal(str)
    object_added = Signal(str)

    def __init__(self):
        super().__init__()
        self._factory = ProtoFactory()
        self._objects: dict[str, object] = {}
        self._name_counters = {
            'ie': (1, 'Image'),
            'te': (1, 'Text'),
            'ct': (1, 'Template')
        }

    def has_unique_name(self, obj):
        return (
            hasattr(obj, 'name') and
            obj.name is not None and
            obj.name not in {o.name for o in self._objects.values() if hasattr(o, 'name')}
        )

    def generate_name(self, obj):
        if self.has_unique_name(obj):
            return obj.name

        prefix = get_prefix(obj.pid)
        counter, base_name = self._name_counters.get(prefix, (1, prefix.capitalize()))

        existing_names = {o.name for o in self._objects.values() if hasattr(o, 'name')}
        while True:
            candidate = f"{base_name} {counter}"
            if candidate not in existing_names:
                break
            counter += 1

        self._name_counters[prefix] = (counter + 1, base_name)
        obj.name = candidate
        return candidate

    def register(self, obj):
        pid = getattr(obj, "pid", None)
        if not pid:
            raise ValueError("Object must have a pid")

        self._objects[pid] = obj
        self.object_added.emit(pid)

        if hasattr(obj, "element_changed"):
            obj.element_changed.connect(lambda: self.object_changed.emit(pid))
        if hasattr(obj, "template_changed"):
            obj.template_changed.connect(lambda: self.object_changed.emit(pid))
        if hasattr(obj, "update_cache"):
            obj.update_cache.connect(lambda: self.object_changed.emit(pid))

    def create(self, pid: str, **kwargs) -> object:
        if is_pid_prefix(pid):
            pid = issue_pid(pid)

        obj = self._factory.create(pid=pid, **kwargs)
        self.generate_name(obj)
        self.register(obj)
        print(f"{obj.pid}:{obj.name} registered.")

        template = getattr(obj, "template", None)
        if template:
            template.add_element(obj)

        return obj

    def clone(self, obj):
        template = getattr(obj, "template", None)
        prefix = get_prefix(obj.pid)
        new_pid = self._factory.protoid(prefix)

        clone = obj.clone()
        clone.pid = new_pid

        self.generate_name(clone)
        self.register(clone)

        if template:
            clone.set_template(template)
            template.add_element(clone)

        return clone

    def attach_elements_to_templates(self):
        for obj in self._objects.values():
            if hasattr(obj, "template_pid") and hasattr(obj, "set_template"):
                template = self.get(obj.template_pid)
                if template:
                    obj.set_template(template)
                    if hasattr(template, "add_element"):
                        template.add_element(obj)

    def detach_elements_from_templates(self):
        for obj in self._objects.values():
            if hasattr(obj, "template_pid") and hasattr(obj, "pid"):
                template = self.get(obj.template_pid)
                if template and hasattr(template, "remove_element"):
                    template.remove_element(obj)

    def get_element_and_template(self, pid: str):
        obj = self.get(pid)
        return obj, self.get(obj.template_pid)

    def replace(self, pid: str, new_obj: object):
        if pid not in self._objects:
            raise KeyError(f"No object with pid '{pid}' found to replace.")

        old_obj = self._objects[pid]
        if hasattr(old_obj, "element_changed"):
            try:
                old_obj.element_changed.disconnect()
            except Exception:
                pass

        self._objects[pid] = new_obj

        if hasattr(new_obj, "element_changed"):
            new_obj.element_changed.connect(lambda: self.object_changed.emit(pid))

        self.object_changed.emit(pid)

    def deregister(self, pid: str):
        if self.contains(pid):
            if get_prefix(pid) in ELEMENT_PREFIXES:
                element, template = self.get_element_and_template(pid)
                template.remove_element(element)
            del self._objects[pid]
            self.object_removed.emit(pid)

    def contains(self, pid):
        return pid in self._objects

    def get(self, pid: str):
        return self._objects.get(pid)

    def get_all(self, prefix: str = None):
        if prefix is None:
            return self._objects
        elif prefix in VALID_ID_PREFIXES:
            return {
                pid: obj for pid, obj in self._objects.items()
                if pid.startswith(prefix)
            }
        else:
            raise ValueError(f"{prefix} is not a valid ProtoObject prefix")

    def clear(self):
        self._objects.clear()

    def obj_to_dict(self, pid: str) -> dict:
        obj = self._objects.get(pid)
        if obj is None:
            raise KeyError(f"No object registered with pid '{pid}'")
        return obj.to_dict()

    def obj_from_dict(self, data: dict):
        pid = data.get("pid")
        if not pid:
            raise ValueError("Missing 'pid' in object data")

        obj_type = self._factory.get_object_type(pid)
        if not obj_type:
            raise ValueError(f"Unknown pid prefix for: {pid}")

        obj = obj_type.from_dict(data)
        self.register(obj)

        # ✅ If it's an element and has template_pid, attach it
        if hasattr(obj, "template_pid") and hasattr(obj, "set_template"):
            template = self.get(obj.template_pid)
            if template:
                obj.set_template(template)
                if hasattr(template, "add_element"):
                    template.add_element(obj)

        return obj

    def to_dict(self) -> dict:
        return {pid: self.obj_to_dict(pid) for pid in self._objects}

    def from_dict(self, data: dict):
        self._objects.clear()
        for obj_data in data.values():
            self.obj_from_dict(obj_data)
        self.attach_elements_to_templates()

    def save_to_file(self, root_pid: str, path: str):
        data = {
            "root": root_pid,
            "objects": self.to_dict()
        } 
        with open(path, "w") as f:
            json.dump(data, f, indent=4)

    def load_from_file(self, path: str):
        with open(path, "r") as f:
            data = json.load(f)

        root_pid = data.get("root")
        self.from_dict(data["objects"])
        return self.get(root_pid)

# # proto_registry.py

# from PySide6.QtCore import QObject, Signal

# from prototypyside.utils.proto_helpers import (VALID_ID_PREFIXES, 
#         ELEMENT_PREFIXES, parse_pid, get_prefix, issue_pid, is_pid_prefix)
# from prototypyside.services.proto_factory import ProtoFactory


# ### All Proto Objects Must be Created Through the Registry ###
# class ProtoRegistry(QObject):
#     object_changed = Signal(str)    # pid
#     object_removed = Signal(str)    # pid
#     object_added = Signal(str)      # pid

#     def __init__(self):
#         super().__init__()
#         self._factory = ProtoFactory()
#         self._objects: dict[str, object] = {}
#         self._name_counters = {
#             'ie': (1, 'Image'),
#             'te': (1, 'Text'),
#             'ct': (1, 'Template')
#         }

#     def has_unique_name(self, obj):
#         return (
#             hasattr(obj, 'name') and
#             obj.name is not None and
#             obj.name not in {o.name for o in self._objects.values() if hasattr(o, 'name')}
#         )

#     def generate_name(self, obj):
#         # If the object already has a unique name, return it
#         if self.has_unique_name(obj):
#             return obj.name

#         prefix = get_prefix(obj.pid)
#         counter, base_name = self._name_counters.get(prefix, [1, prefix.capitalize()])

#         existing_names = {o.name for o in self._objects.values() if hasattr(o, 'name')}

#         while True:
#             candidate = f"{base_name} {counter}"
#             if candidate not in existing_names:
#                 break
#             counter += 1

#         self._name_counters[prefix][0] = counter + 1
#         obj.name = candidate
#         return candidate


#     def register(self, obj):
#         pid = getattr(obj, "pid", None)
#         if not pid:
#             raise ValueError("Object must have a pid")

#         self._objects[pid] = obj
#         self.object_added.emit(pid)

#         # Connect known signals
#         if hasattr(obj, "element_changed"):
#             obj.element_changed.connect(lambda: self.object_changed.emit(pid))
#         if hasattr(obj, "template_changed"):
#             obj.template_changed.connect(lambda: self.object_changed.emit(pid))
#         if hasattr(obj, "update_cache"):
#             obj.update_cache.connect(lambda: self.object_changed.emit(pid))

#     def create(self, pid: str, **kwargs) -> object:
#         print(f"pid prefix: {pid}")
#         if is_pid_prefix(pid):
#             pid = issue_pid(pid)
#             print(f"Issued pid: {pid}")
#         print(kwargs)

#         # Create object from factory
#         obj = self._factory.create(pid=pid, **kwargs)

#         # Assign a unique name
#         self.generate_name(obj)

#         # Register the object before wiring up any relationships
#         self.register(obj)

#         # Attach to template if defined
#         template = getattr(obj, "template", None)
#         if template:
#             template.add_item(obj)

#         return obj

#     def clone(self, obj):
#         template = getattr(obj, "template", None)

#         prefix = get_prefix(obj.pid)
#         new_pid = self._factory.protoid(prefix)  # Assuming this is equivalent to issue_pid(prefix)

#         # Perform the clone using the object's own logic
#         clone = obj.clone()
#         clone.pid = new_pid

#         # Optional: rename it to distinguish in UI
#         self.generate_name(clone)

#         self.register(clone)

#         if template is not None:
#             clone.set_template(template)
#             template.add_item(clone)

#         return clone
#     def attach_elements_to_templates(self):
#         """
#         After all objects are loaded, attach elements to their corresponding templates
#         using template_pid references.
#         """
#         for obj in self._objects.values():
#             if hasattr(obj, "template_pid") and hasattr(obj, "set_template"):
#                 template = self.get(obj.template_pid)
#                 if template:
#                     obj.set_template(template)
#                     if hasattr(template, "add_element"):
#                         template.add_element(obj)

#     def detach_elements_from_templates(self):
#         """
#         Detach all elements from their templates by removing them via template.remove_element().
#         This is useful for cleaning up before reattaching or replacing templates.
#         """
#         for obj in self._objects.values():
#             if hasattr(obj, "template_pid") and hasattr(obj, "pid"):
#                 template = self.get(obj.template_pid)
#                 if template and hasattr(template, "remove_element"):
#                     template.remove_element(obj)


#     def get_element_and_template(self, pid:str):
#         obj = self.get(pid)
#         return obj, self.get(obj.template_pid)

#     def replace(self, pid: str, new_obj: object):
#         """Replaces the object with the given pid with a new instance."""
#         if pid not in self._objects:
#             raise KeyError(f"No object with pid '{pid}' found to replace.")

#         # Disconnect old signals if needed
#         old_obj = self._objects[pid]
#         if hasattr(old_obj, "element_changed"):
#             try:
#                 old_obj.element_changed.disconnect()
#             except Exception:
#                 pass

#         # Replace and reconnect
#         self._objects[pid] = new_obj

#         if hasattr(new_obj, "element_changed"):
#             new_obj.element_changed.connect(lambda: self.object_changed.emit(pid))

#         self.object_changed.emit(pid)

#     def deregister(self, pid: str):
#         if self.has(pid):
#             if get_prefix(pid) in ELEMENT_PREFIXES:
#                 element, template = self.get_element_and_template(pid)
#                 template.removeItem(element)
#             del self._objects[pid]
#             self.object_removed.emit(pid)

#     def contains(self, pid):
#         return pid in self._objects

#     def get(self, pid: str):
#         return self._objects.get(pid)

#     def get_all(self, prefix: str = None):
#         if prefix is None:
#             return self._objects
#         elif prefix in VALID_ID_PREFIXES:
#             return {
#                 pid: obj for pid, obj in self._objects.items()
#                 if pid.startswith(prefix)
#             }
#         else:
#             raise ValueError(f"{prefix} is not a valid ProtoObject prefix")


#     def clear(self):
#         self._objects.clear()

#     # --- Object-level (single pid) ---
#     def obj_to_dict(self, pid: str) -> dict:
#         obj = self._objects.get(pid)
#         if obj is None:
#             raise KeyError(f"No object registered with pid '{pid}'")
#         return obj.to_dict()

#     def obj_from_dict(self, data: dict):
#         pid = data.get("pid")
#         if not pid:
#             raise ValueError("Missing 'pid' in object data")

#         obj_type = self._factory.get_object_type(pid)
#         if not obj_type:
#             raise ValueError(f"Unknown pid prefix for: {pid}")

#         obj = obj_type.from_dict(data)
#         self.register(obj)

#         return obj


#     # --- Full registry serialization ---
#     def to_dict(self) -> dict:
#         return {pid: obj.to_dict() for pid, obj in self._objects.items()}

#     def from_dict(self, data: dict):
#         self._objects.clear()

#         # Step 1: Load and register all objects
#         for pid, obj_data in data.items():
#             obj_type = self._factory.get_object_type(pid)
#             obj = obj_type.from_dict(obj_data)
#             self.register(obj)

#         # Step 2: Reattach template-element relationships
#         for obj in self._objects.values():
#             if isinstance(obj, ComponentTemplate) and hasattr(obj, "_pending_element_pids"):
#                 for ep in obj._pending_element_pids:
#                     element = self.get(ep)
#                     if element:
#                         element.set_template(obj)
#                         obj.add_element(element)
#                 del obj._pending_element_pids



#     # --- File-level save/load with root ---
#     def save_to_file(self, root_pid: str, path: str):
#         data = {
#             "root": root_pid,
#             "objects": self.to_dict()
#         }
#         with open(path, "w") as f:
#             json.dump(data, f, indent=2)

#     def load_from_file(self, path: str):
#         with open(path, "r") as f:
#             data = json.load(f)

#         root_pid = data.get("root")
#         self.from_dict(data["objects"])
#         return self.get(root_pid)
