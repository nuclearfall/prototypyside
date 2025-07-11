# proto_registry.py

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QGuiApplication, QClipboard
from PySide6.QtWidgets import QGraphicsItem

from prototypyside.services.proto_factory import ProtoFactory
from prototypyside.utils.proto_helpers import get_prefix, issue_pid
BASE_NAMES: Dict[str, str] = {
    "ct": "Component Template",
    "cc": "Component",
    "ie": "Image Element",
    "te": "Text Element",
    "lt": "Layout Template",
    "ls": "Layout Slot",
}

class ProtoRegistry(QObject):
    """
    A per‐template registry. Manages its own `_store` of objects,
    emits three core signals, and supports lookup & JSON serialization.
    """

    _registries = []  # Shared list across all instances
    _factory = ProtoFactory()
    object_registered = Signal(object)    # Emits the object that was added
    object_deregistered = Signal(object)  # Emits the object that was removed
    object_orphaned = Signal(object)      # Emits the object that was orphaned

    def __init__(self, parent=None):
        super().__init__(parent)
        # Automatically register this instance when constructed
        print("Constructing registry...")
        self.__class__._registries.append(self)

        self._unique_names: set = set()
        self._name_counts: Dict[str, int] = {prefix: 1 for prefix in BASE_NAMES if prefix != "ls"}
        self._store: Dict[str, Any] = {}
        self._orphans: Dict[str, Any] = {}
        # print(f"Registries in existence: {self.all()}")

    @classmethod
    def all(cls, index=None):
        """Return all active registries (shared list)."""
        if index and index < len(cls._registries):
            return cls._registries[index]
        return cls._registries

    @classmethod
    def new(cls, class_prefix, **kwargs):
        # Create the object via factory
        registry = cls()
        obj = registry.create(class_prefix, **kwargs)
        # Create a fresh registry instance
        
        return obj, registry

    def orphans(self):
        return [o for o in self._orphans]

    def has_unique_name(self, obj: object) -> bool:
        return hasattr(obj, 'name') and obj.name is not None and obj.name not in self._unique_names

    @classmethod
    def has(cls, pid):
        return any(pid in r._store for r in cls._registries)

    def generate_name(self, obj: object):
        pid_prefix = get_prefix(obj.pid)

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
        return obj

    def register(self, obj: Any):
        """
        Add obj to the registry. Emits object_registered.
        """
        pid = getattr(obj, "pid", None)
        if not pid:
            raise ValueError("Object must have a .pid attribute")

        if pid in self._store:
            print(f"Warning: not re-registering PID '{pid}'")
            return

        # Only generate a name if it's missing or not unique
        if not hasattr(obj, "name") or obj.name is None or not self.has_unique_name(obj):
            self.generate_name(obj)

        self._store[pid] = obj
        self.object_registered.emit(obj)

    def deregister(self, pid: str):
        """
        Remove from store, move to orphans, emit object_deregistered.
        """
        obj = self._store.pop(pid, None)
        if not obj:
            print(f"Warning: cannot deregister missing PID '{pid}'")
            return
        self._orphans[pid] = obj
        self.object_deregistered.emit(obj)
        self.object_orphaned.emit(obj)

    @classmethod
    def from_dict(cls, data, registry=None, is_clone=False):
        pid = data.get("pid")
        if not registry:
            registry = cls()
        print(f"[from_dict] Checking pid {pid}. Registry has? {registry.has(pid)}")
        if pid and registry.has(pid):
            print(f"[from_dict] Object already exists: {pid}")
            return registry.get(pid), registry
        obj = cls._factory.from_dict(data, registry=registry, is_clone=is_clone)
        return obj, registry

    def to_dict(self, obj) -> object:
        # only dump things that know how to to_dict()
        if not hasattr(obj, "to_dict"):
            return None
        data = self._factory.to_dict(obj)
        return data

    def clone(self, obj: Any) -> Any:
        if not hasattr(obj, "pid"):
            raise ValueError("Cannot clone object without a 'pid'.")
        # serialize the existing object
        payload = self._factory.to_dict(obj)
        # rehydrate in “clone” mode—your from_dict must handle is_clone=True
        return self._factory.from_dict(
            payload,
            registry=self,
            is_clone=True
        )

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

    @classmethod
    def get(cls, pid):
        for r in cls._registries:
            item = r._store.get(pid)
            if item:
                return item
        return None


    def get_by_prefix(self, prefix):
        if prefix:           
            return [v for k, v in self._store.items() if get_prefix(k) == prefix]
        else:
            return []

    def global_get_by_prefix(self, prefix=None):
        global_found = []
        for child in self._registries:
            global_found += child.get_by_prefix(prefix)
            return global_found

    def get_last(self, prefix=None) -> object:
        vals = list(self._store.values())
        return vals[-1] if vals else None

    def get_first(self) -> object:
        vals = list(self._store.values())
        return vals[0] if vals else None

