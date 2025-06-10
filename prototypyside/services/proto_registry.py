# proto_registry.py

from PySide6.QtCore import QObject, Signal

from prototypyside.utils.proto_helpers import (VALID_ID_PREFIXES, 
        ELEMENT_PREFIXES, parse_pid, get_prefix, issue_pid, is_pid_prefix)


### All Proto Objects Must be Created Through the Registry ###
class ProtoRegistry(QObject):
    object_changed = Signal(str)    # pid
    object_removed = Signal(str)    # pid
    object_added = Signal(str)      # pid

    def __init__(self, factory):
        super().__init__()
        self._factory = factory
        self._objects: dict[str, object] = {}

    def register(self, obj):
        pid = getattr(obj, "pid", None)
        if not pid:
            raise ValueError("Object must have a pid")

        self._objects[pid] = obj
        self.object_added.emit(pid)

        # Connect known signals
        if hasattr(obj, "element_changed"):
            obj.element_changed.connect(lambda: self.object_changed.emit(pid))
        if hasattr(obj, "template_changed"):
            obj.template_changed.connect(lambda: self.object_changed.emit(pid))
        if hasattr(obj, "update_cache"):
            obj.update_cache.connect(lambda: self.object_changed.emit(pid))

    def create(self, pid: str, **kwargs) -> object:

        prefix, uuid = parse_pid(pid)
        if uuid is None and is_pid_prefix(pid):
            pid = issue_pid(pid)
        print(kwargs)
        obj = self._factory.create(pid, **kwargs)
        self.register(obj)
        return obj

    # def generate_unique_name(self, proto_id):
    #     prefix = self.get_prefix(proto_id)
    #     existing_names = {e.name for e in template.elements}
    #     if base_name not in existing_names:
    #         return base_name

    def clone(self, obj):
        template = None
        if hasattr(obj, "template"):
            template = obj.template

        prefix = get_prefix(obj.pid)
        new_pid = issue_pid(prefix)
        clone = obj.clone()
        clone.pid = new_pid
        self.register(clone)
        if template is not None:
            clone.set_template(template)
            template.add_item(clone)
        return clone

    def get_element_and_template(self, pid:str):
        obj = self.get(pid)
        return obj, self.get(obj.template_pid)

    def replace(self, pid: str, new_obj: object):
        """Replaces the object with the given pid with a new instance."""
        if pid not in self._objects:
            raise KeyError(f"No object with pid '{pid}' found to replace.")

        # Disconnect old signals if needed
        old_obj = self._objects[pid]
        if hasattr(old_obj, "element_changed"):
            try:
                old_obj.element_changed.disconnect()
            except Exception:
                pass

        # Replace and reconnect
        self._objects[pid] = new_obj

        if hasattr(new_obj, "element_changed"):
            new_obj.element_changed.connect(lambda: self.object_changed.emit(pid))

        self.object_changed.emit(pid)

    def deregister(self, pid: str):
        if self.has(pid):
            if get_prefix(pid) in ELEMENT_PREFIXES:
                element, template = self.get_element_and_template(pid)
                template.removeItem(element)
            del self._objects[pid]
            self.object_removed.emit(pid)

    def has(self, pid):
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
        obj_type = self._factory.get_object_type(pid)

        if not obj_type:
            raise ValueError(f"Unknown pid: {pid}")
        obj = obj_type.from_dict(data)
        self.register(obj)
        return obj

    def to_dict(self) -> dict:
        return {
            pid: obj.to_dict()
            for pid, obj in self._objects.items()
        }

    def from_dict(self, data: dict):
        self._objects.clear()
        for pid, obj_data in data.items():
            obj_type = self._factory.get_object_type(pid)
            if obj_type:
                obj = obj_type.from_dict(obj_data)
                self.register(obj)
            else:
                raise ValueError(f"Unknown object type for pid '{pid}'")