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
    "ct": "Component",
    "ci": "Component Instance",
    "ie": "Image Element",
    "te": "Text Element",
    "lt": "Layout",
    "li": "Layout Instance",
    "ls": "Layout Slot",
}

class ProtoRegistry(QObject):
    """
    A per‐template registry. Manages its own `_store` of objects,
    emits three core signals, and supports lookup & JSON serialization.
    """
    object_registered = Signal(object)    # Emits the object that was added
    object_deregistered = Signal(object)  # Emits the object that was removed
    object_orphaned = Signal(object)      # Emits the object that was orphaned

    def __init__(self, parent, settings):
        super().__init__()
        self.parent_registry = parent
        self.settings = settings
        self._root_pid = None
        self._store: Dict[str, Any] = {}
        self._orphans: Dict[str, Any] = {}
        self._factory = ProtoFactory()
        self._unique_names: set = set()
        self._name_counts: Dict[str, int] = {prefix: 1 for prefix in BASE_NAMES}

    def has_unique_name(self, obj: object) -> bool:
        return hasattr(obj, 'name') and obj.name is not None and obj.name not in self._unique_names

    def generate_name(self, obj: object):
        if self.has_unique_name(obj):
            return obj.name

        pid_prefix = get_prefix(obj.pid)
        base_name = BASE_NAMES.get(pid_prefix, "Object")
        counter = self._name_counts.get(pid_prefix, 0)

        # Refresh unique names from registry
        existing_names_in_registry = {
            o.name for o in self._store.values() if hasattr(o, 'name') and o.name is not None
        }
        self._unique_names.update(existing_names_in_registry)

        while True:
            candidate = f"{base_name} {counter}"
            if candidate not in self._unique_names:
                break
            counter += 1

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
        Add obj to this registry. Emits object_registered.
        """
        pid = getattr(obj, "pid", None)
        if not pid:
            raise ValueError("Object must have a .pid attribute")
        if pid in self._store:
            # Overwrite existing entry
            print(f"Warning: re-registering PID '{pid}'")
        obj.name = self.generate_name(obj)
        self._store[pid] = obj
        self.object_registered.emit(obj)

    def deregister(self, pid: str):
        """
        Remove from store, move to orphans, emit signals.
        """
        obj = self._store.pop(pid, None)
        if not obj:
            print(f"Warning: cannot deregister missing PID '{pid}'")
            return
        self._orphans[pid] = obj
        self.object_deregistered.emit(obj)
        self.object_orphaned.emit(obj)

    def clone(self, obj: Any, **kwargs) -> Any:
        """
        Clone an object, give it a new PID, register it, and name it.
        """
        # --- validate & issue new PID -----------------------------------------
        pid = getattr(obj, "pid", None)
        if pid is None:
            raise ValueError("Cannot clone object without a 'pid' attribute.")
        new_pid = issue_pid(get_prefix(pid))

        # --- serialize & rebuild via factory ----------------------------------
        data = self._factory.to_dict(obj)
        data["pid"] = new_pid
        clone = self._factory.from_dict(data)

        # --- name & register --------------------------------------------------
        self.generate_name(clone)
        self.register(clone)
        if get_prefix(clone.pid) in ["ie", "te"]:
            template = self.get(clone.tpid)
            template.insert_item(clone)

        return clone

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
    def get(self, pid: str) -> Any:
        """
        Retrieve a registered object by PID.
        """
        try:
            return self._store[pid]
        except KeyError:
            raise KeyError(f"PID '{pid}' not found in registry")

    def get_all(self, prefix: Optional[str] = None) -> List[Any]:
        """
        Return all objects, or only those whose PID prefix matches.
        """
        if prefix is None:
            return list(self._store.values())
        return [o for o in self._store.values() if get_prefix(o.pid) == prefix]

    def get_last(self):
        return self.get_all()[-1]

    def to_dict(self) -> Dict[str, dict]:
        """
        Serialize each object via the factory.
        """
        return {pid: self._factory.to_dict(obj) for pid, obj in self._store.items()}

    def from_dict(self, data: Dict[str, dict]):
        """
        Clear and rebuild from serialized dict of pid→data.
        """
        self._store.clear()
        self._orphans.clear()
        # Pass 1: instantiate & register
        for pid, obj_data in data.items():
            try:
                obj = self._factory.from_dict(obj_data)
                self.register(obj)
            except Exception as e:
                print(f"Error loading PID '{pid}': {e}")
        # Pass 2: wire QGraphicsItem parenting if needed
        for obj in self._store.values():
            tpid = getattr(obj, "tpid", None)
            if tpid and tpid in self._store:
                tpl = self._store[tpid]
                if hasattr(tpl, "addItem"):
                    tpl.addItem(obj)


class RootRegistry(ProtoRegistry):
    """
    A global registry that tracks all children registries.
    Mirrors every child’s registrations → a single _global_store,
    and coordinates copy/cut/paste via the Qt clipboard.
    """

    def __init__(self, settings):
        super().__init__(parent=None, settings=settings)
        self._global_store: Dict[str, Any] = {}
        self._global_orphans: Dict[str, Any] = {}
        self.children: List[ProtoRegistry] = []

        # # mirror own signals into the global maps
        # self.object_registered.connect(self._add_global)
        # self.object_deregistered.connect(self._remove_global)
        # self.object_orphaned.connect(self._orphan_global)

        # watch the system clipboard for copy/cut/paste
        cb: QClipboard = QGuiApplication.clipboard()
        cb.dataChanged.connect(self._on_clipboard_event)

    def create_child_registry(self):
        child = ProtoRegistry(parent=self, settings=self.settings)
        child.object_registered.connect(self._add_global)
        child.object_deregistered.connect(self._remove_global)
        child.object_orphaned.connect(self._orphan_global)
        self.children.append(child)
        return child

    def _add_global(self, obj):
        self._global_store[obj.pid] = obj
        self.object_registered.emit(obj)  # This is OK

    def _remove_global(self, obj):
        self._global_store.pop(obj.pid, None)
        self.object_deregistered.emit(obj)  # <-- Only emits to root listeners; OK if not connected back to self!

    def _orphan_global(self, obj):
        self._global_orphans[obj.pid] = obj
        self.object_orphaned.emit(obj)

    def get_global(self, pid: str) -> Any:
        """Retrieve any object from the unified global store."""
        try:
            return self._global_store[pid]
        except KeyError:
            raise KeyError(f"PID '{pid}' not found in global registry")

    def get_global_by_type(self, prefix: str):
        return [obj for obj in self._global_store.values() if get_prefix(obj.pid) == prefix]


    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the entire global store plus each child registry.
        """
        return {
            "global": super().to_dict(),
            "children": [child.to_dict() for child in self.children]
        }

    def from_dict(self, data: Dict[str, Any]):
        """
        Rebuild both global and child registries from a dict produced
        by this registry’s to_dict().
        """
        # rebuild global portion
        global_data = data.get("global", {})
        super().from_dict(global_data)
        # clear out old children
        self.children.clear()
        # rebuild each child
        for child_data in data.get("children", []):
            child = self.create_child_registry()
            child.from_dict(child_data)

    def dump_proto_registry(self,
                            registry: ProtoRegistry,
                            path: Union[str, Path]) -> None:
        """
        Serialize a single child registry (i.e. one tab’s template)
        out to JSON at the given filesystem path.
        """
        data = registry.to_dict()
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_proto_registry(self,
                            path: Union[str, Path]
                            ) -> ProtoRegistry:
        """
        Create a fresh child ProtoRegistry, populate it from the
        JSON in `path`, and return it.  The new registry is
        automatically added as a child of this RootRegistry.
        """
        p = Path(path)
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)

        # create a brand-new child reg
        new_reg = self.create_child_registry()
        # populate it with exactly the objects we dumped earlier
        new_reg.from_dict(data)
        return new_reg

    def _on_clipboard_event(self):
        """
        Handle copy/paste by reading stored PIDs from plain text.
        (Application may choose a richer MIME type if desired.)
        """
        cb: QClipboard = QGuiApplication.clipboard()
        text = cb.text().strip()
        # example convention: when copying, we prefix text with "PID:<pid>"
        if text.startswith("PID:"):
            pid = text[4:]
            if pid in self._global_store:
                orig = self._global_store[pid]
                if hasattr(orig, "clone"):
                    clone = orig.clone()
                    # by default, register into the originating child registry
                    if hasattr(orig, "tpid"):
                        # find the child registry managing orig.tpid
                        for child in self.children:
                            if pid in child._store:
                                child.register(clone)
                                break
                    else:
                        # fallback: register globally
                        self.register(clone)

