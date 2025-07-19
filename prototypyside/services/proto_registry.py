# proto_registry.py

import json
import uuid
import re
from typing import Any, Dict, List, Optional, Union, Tuple, TYPE_CHECKING

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QGuiApplication, QClipboard
from PySide6.QtWidgets import QGraphicsItem

from prototypyside.services.proto_factory import ProtoFactory
from prototypyside.utils.proto_helpers import issue_pid, get_prefix, MODEL_ONLY, OBJECT_ONLY


BASE_NAMES = {
    "ie": "Image Element",
    "te": "Text Element",
    "ct": "Component Template",
    "cc": "Component",
    "lt": "Layout Template",
    "pg": "Page",
    "ls": "Layout Slot",
}

class ProtoRegistry(QObject):

    object_registered = Signal(str)  # pid
    object_deregistered = Signal(str)

    def __init__(self, parent=None, root=None):
        super().__init__(parent)
        self.pid = issue_pid("proto_reg")
        self._factory = ProtoFactory()
        self._is_root = isinstance(self, RootRegistry)
        self.root = self if self._is_root else root
        self._mail_room = None
        self._object_registry = None
        self._store: Dict[str, Any] = {}
        self._orphans: Dict[str, Any] = {}
        self._unique_names = set()
        self._name_counts = {prefix: 1 for prefix in BASE_NAMES if prefix != "ls"}
        self.set_object_registry()

    def set_object_registry(self):
        self._object_registry = ObjectRegistry()

    @property
    def mail_room(self):
        return self._mail_room

    def set_mail_room(self, mail_room):
        self._maiL_room = mail_room

    def get_registry(self, pid: str):
        prefix = get_prefix(pid)
        if prefix in OBJECT_ONLY:
            return self._object_registry
        return self

    def register(self, obj: Any):
        pid = getattr(obj, "pid", None)
        prefix = get_prefix(pid)
        if not pid or not prefix:
            raise TypeError(f"[Registry] {prefix} is invalid for pid {pid}.")
        # Decide target registry
        target = self.get_registry(pid)

        # Use the right storage dict
        store = getattr(target, "_store", None)
        if store is None:
            raise RuntimeError("[Registry] Target registry missing _store attribute.")

        if pid in store:
            print(f"[Registry] Skipping duplicate: {pid}")
            return

        # Name generation/uniqueness
        if not hasattr(obj, "name") or not self.has_unique_name(obj):
            self.generate_name(obj)

        # Register with mail room if needed
        if hasattr(self, "mail_room"):
            self._mail_room.register_target(pid, obj)  # Or whatever the appropriate method is

        store[pid] = obj
        target.object_registered.emit(pid)




    def find_root(self):
        parent = self.parent()
        while parent:
            if isinstance(parent, RootRegistry):
                return parent
            parent = parent.parent()
        raise RuntimeError("No RootRegistry found in parent chain.")

    def orphans(self):
        return [o for o in self._orphans]

    def has_unique_name(self, obj: object) -> bool:
        return hasattr(obj, 'name') and obj.name is not None and obj.name not in self._unique_names

    def has(self, pid):
        return pid in self._store

    def generate_name(self, obj: object):
        pid_prefix = get_prefix(obj.pid)
        if not hasattr(obj, "name"):
            return

        # If name already exists and is unique in this registry, preserve it
        if self.has_unique_name(obj):
            self._unique_names.add(obj.name)
            return obj.name

        # Use counter to assign a name
        base_name = BASE_NAMES.get(pid_prefix, "Object")
        counter = self._name_counts.get(pid_prefix, 0)

        # Refresh local uniqueness
        existing_names = {
            o.name for o in self._store.values()
            if hasattr(o, 'name') and o.name is not None
        }
        self._unique_names.update(existing_names)

        # Find the next available name
        while True:
            candidate = f"{base_name} {counter}"
            if candidate not in self._unique_names:
                break
            counter += 1

        # Apply and track the new name
        self._name_counts[pid_prefix] = counter + 1
        obj.name = candidate
        self._unique_names.add(candidate)
        return candidate

    def create(self, prefix_or_pid: str, **kwargs) -> Any:
        """
        Factory + register in one call.
        """
        final_pid = issue_pid(prefix_or_pid)
        # print(f"Object created with final_pid {final_pid}")
        obj = self._factory.create(pid=final_pid, **kwargs)
        self.register(obj)
        print ("Obj registered")
        return obj

    def deregister(self, pid: str):
        """
        Remove from store, move to orphans, emit object_deregistered.
        """
        obj = self._store.pop(pid, None)
        if not obj:
            print(f"Warning: cannot deregister missing PID '{pid}'")
            return
        self._orphans[pid] = obj
        self.object_deregistered.emit(obj.pid)
        self.object_orphaned.emit(obj.pid)

    @classmethod
    def from_dict(cls, data, registry, is_clone=False):
        pid = data.get("pid")
        if pid and registry.global_get(pid) and not is_clone:
            return registry.global_get(pid)
        obj = registry._factory.from_dict(data, registry=registry, is_clone=is_clone)
        return obj

    def to_dict(self, obj) -> object:
        # only dump things that know how to to_dict()
        if not hasattr(obj, "to_dict"):
            return None
        data = self._factory.to_dict(obj)
        return data

    # in proto_registry.py
    def clone(self, obj: Any) -> Any:
        """
        Creates a deep clone by round‐tripping through *this* registry’s from_dict,
        ensuring all registration logic runs.
        """
        print(f"Cloning {obj.name}:{obj.pid}")
        if not hasattr(obj, "pid"):
            raise ValueError("Cannot clone object without a 'pid'.")
        payload = self._factory.to_dict(obj)
        # This calls ProtoRegistry.from_dict → factory.from_dict with is_clone=True
        # which in turn invokes your LayoutTemplate.from_dict with is_clone=True
        return self.from_dict(payload, registry=self, is_clone=True)

    def reinsert(self, pid: str):
        """
        Move an orphan back into the store.
        """
        obj = self._orphans.pop(pid, None)
        if not obj:
            raise KeyError(f"PID '{pid}' not found among orphans")
        self.register(obj)

    def is_orphan(self, pid: str) -> bool:
        return True if pid in self._orphans else False

    def get(self, pid, registry=None):
        for r in registry._store:
            item = r._store.get(pid)
            if item:
                return item
        return None

    def global_get(self, pid):
        """
        Globally look up an object by pid, starting from this registry's root.
        """
        root = self.root
        if pid in root._store:
            return root._store[pid]

        for child in getattr(root, "_children", []):
            if pid in child._store:
                return child._store[pid]

        return None

    def get_by_prefix(self, prefix):
        if prefix:           
            return [v for k, v in self._store.items() if get_prefix(k) == prefix]
        else:
            return []

    def global_get_by_prefix(self, prefix=None):
        global_found = []
        children = getattr(self, "children")
        if children:
            for child in self.children:
                global_found += child.get_by_prefix(prefix)
            return global_found


    def get_last(self, prefix=None) -> object:
        vals = list(self._store.values())
        return vals[-1] if vals else None

    def get_first(self) -> object:
        vals = list(self._store.values())
        return vals[0] if vals else None


class ObjectRegistry(ProtoRegistry):
    def __init__(self):
        super().__init__()
        self.pid = issue_pid("obj_reg")
        self._object_registry = None   # Or omit entirely if not needed

    def set_object_registry(self):
        # Prevent recursion: ObjectRegistry does not need its own object registry
        self._object_registry = None 

class RootRegistry(ProtoRegistry):
    object_registered = Signal(str)
    object_deregistered = Signal(str)

    def __init__(self):
        super().__init__()

        self.root = self
        self._children = []
        self.pid = issue_pid("root_reg")

    def add_child(self, child: ProtoRegistry):
        self._children.append(child)
        child.object_registered.connect(self._repeat_registered)
        child.object_deregistered.connect(self._repeat_deregistered)

    def has(self, pid):
        if pid in self._store:
            return True
        for child in self._children:
            if child.has(pid):
                return True
        return False

    def _repeat_registered(self, pid):
        self.object_registered.emit(pid)

    def _repeat_deregistered(self, pid):
        self.object_deregistered.emit(pid)

    def global_get_by_prefix(self, prefix):
        results = self.get_by_prefix(prefix)
        for child in self._children:  # FIXED
            results += child.get_by_prefix(prefix)
        return results

    def global_get(self, pid):
        obj = self._store.get(pid)
        if obj:
            return obj
        for child in self._children:
            if pid in child._store:
                return child._store[pid]
        return None
