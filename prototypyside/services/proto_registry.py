# proto_registry.py

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QGuiApplication, QClipboard
from PySide6.QtWidgets import QGraphicsItem

from prototypyside.services.proto_factory import ProtoFactory
from prototypyside.utils.proto_helpers import get_prefix, issue_pid
from prototypyside.models.component_template import ComponentTemplate

BASE_NAMES: Dict[str, str] = {
    "ct": "Component Template",
    "ci": "Component",
    "ie": "Image",
    "te": "Text",
    "lt": "Layout Template",
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

        self.root = parent
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
        pid_prefix = get_prefix(obj.pid)

        # If name already exists and is unique in this registry, preserve it
        if self.has_unique_name(obj):
            self._unique_names.add(obj.name)
            return obj.name

        # Determine classification
        is_local_type = pid_prefix in {"ls", "te", "ie"}
        is_root_registry = self.parent() is None
        is_template_clone = hasattr(obj, "template_pid") and obj.template_pid is not None

        # If this registry shouldn't name it, delegate to parent
        if not is_local_type and not is_template_clone and not is_root_registry:
            return self.parent().generate_name(obj)

        # Use this registry's counter to assign a name
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
        Add obj to this registry. Emits object_registered.
        """
        pid = getattr(obj, "pid", None)
        if not pid:
            raise ValueError("Object must have a .pid attribute")
        if pid in self._store:
            print(f"Warning: re-registering PID '{pid}'")

        # Only generate a name if it's missing or not unique
        if not hasattr(obj, "name") or obj.name is None or not self.has_unique_name(obj):
            self.generate_name(obj)

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

    def clone(self, obj: Any) -> Any:
        """
        Clone an object (ComponentTemplate or LayoutTemplate), assign a new PID,
        register it, and recursively clone children (elements or slots).

        - If the object is a ComponentTemplate without a template_pid, mark this
          clone as a clone by setting template_pid = original_pid.
        - Do not retroactively assign template_pid to originals.
        - Only add clones (not originals) to root.clone_components.
        """
        if not hasattr(obj, "pid"):
            raise ValueError("Cannot clone object without a 'pid' attribute.")

        data = self._factory.to_dict(obj)
        old_pid = data["pid"]
        new_pid = issue_pid(get_prefix(old_pid))
        data["pid"] = new_pid

        template_pid = data.get("template_pid", None)
        clones = self.root.clone_components

        # If original (no template_pid) and it's a ComponentTemplate, mark clone with template_pid
        if isinstance(obj, ComponentTemplate) and not template_pid:
            data["template_pid"] = old_pid
            clones.append(new_pid)

        # If this is already a clone (has template_pid), also track it (but avoid duplicates)
        elif template_pid and new_pid not in clones:
            clones.append(new_pid)

        # Clone children
        if isinstance(data.get("elements"), list):
            data["elements"] = self.clone_children(data["elements"], issue_pid)
        elif isinstance(data.get("slots"), list):
            data["slots"] = self.clone_children(data["slots"], issue_pid)

        # Reconstruct and register the clone
        clone = self._factory.from_dict(data)
        if clone is None:
            raise ValueError("Factory failed to reconstruct cloned object.")

        self.generate_name(clone)
        self.register(clone)
        return clone

        
    def clone_children(self, items: Any, issue_pid) -> Any:
        """
        Recursively clones child objects (elements or 2D list of slots).
        Generates new PIDs and rebuilds structure using to_dict/from_dict.
        """
        if isinstance(items, list) and all(isinstance(row, list) for row in items):
            # 2D grid of slots
            new_slots = []
            for row in items:
                new_row = []
                for slot_data in row:
                    slot = self._factory.from_dict(slot_data)
                    cloned = self.clone(slot)  # Recursively clones via `clone()`
                    new_row.append(self._factory.to_dict(cloned))
                new_slots.append(new_row)
            return new_slots
        else:
            # Flat list of elements
            new_elements = []
            for elem_data in items:
                elem = self._factory.from_dict(elem_data)
                cloned = self.clone(elem)  # Recursively clones via `clone()`
                new_elements.append(self._factory.to_dict(cloned))
            return new_elements

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

    def find(self, pid: str):
        obj = self._store.get(pid)
        if obj:
            return obj
        for child_registry in self.child_registries:
            found = child_registry.find(pid)
            if found:
                return found
        return None

    def get(self, pid: str) -> Any:
        """
        Retrieve a locally registered object by PID.
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

    def get_last(self, prefix=None):
        if not self._store:
            return None
        keys = list(self._store.keys())
        if prefix:
            for key in reversed(keys):
                if get_prefix(key) == prefix:
                    return self.get(key)
        return self.get(keys[-1])

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
    A global registry that tracks all child_registries registries.
    Mirrors every child’s registrations → a single _store,
    and coordinates copy/cut/paste via the Qt clipboard.
    """

    def __init__(self, settings):
        super().__init__(parent=None, settings=settings)
        self._store: Dict[str, Any] = {}
        self._global_orphans: Dict[str, Any] = {}
        self.child_registries: List[ProtoRegistry] = []
        self.clone_components = []
        # watch the system clipboard for copy/cut/paste
        cb: QClipboard = QGuiApplication.clipboard()
        cb.dataChanged.connect(self._on_clipboard_event)

    def create_child_registry(self):
        child = ProtoRegistry(parent=self, settings=self.settings)
        child.object_registered.connect(self._add_global)
        child.object_deregistered.connect(self._remove_global)
        child.object_orphaned.connect(self._orphan_global)
        self.child_registries.append(child)
        return child

    def _add_global(self, obj):
        self._store[obj.pid] = obj
        self.object_registered.emit(obj)  # This is OK

    def _remove_global(self, obj):
        self._store.pop(obj.pid, None)
        self.object_deregistered.emit(obj)  # <-- Only emits to root listeners; OK if not connected back to self!

    def _orphan_global(self, obj):
        self._global_orphans[obj.pid] = obj
        self.object_orphaned.emit(obj)

    def get_global(self, pid: str) -> Any:
        """Retrieve any object from the unified global store."""
        try:
            return self._store[pid]
        except KeyError:
            raise KeyError(f"PID '{pid}' not found in global registry")

    def get_global_by_type(self, prefix: str):
        return [obj for obj in self._store.values() if get_prefix(obj.pid) == prefix]

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the entire global store plus each child registry.
        """
        return {
            "global": super().to_dict(),
            "child_registries": [child.to_dict() for child in self.child_registries]
        }

    def from_dict(self, data: Dict[str, Any]):
        """
        Rebuild both global and child registries from a dict produced
        by this registry’s to_dict().
        """
        # rebuild global portion
        global_data = data.get("global", {})
        super().from_dict(global_data)
        # clear out old child_registries
        self.child_registries.clear()
        # rebuild each child
        for child_data in data.get("child_registries", []):
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
            if pid in self._store:
                orig = self._store[pid]
                if hasattr(orig, "clone"):
                    clone = orig.clone()
                    # by default, register into the originating child registry
                    if hasattr(orig, "tpid"):
                        # find the child registry managing orig.tpid
                        for child in self.child_registries:
                            if pid in child._store:
                                child.register(clone)
                                break
                    else:
                        # fallback: register globally
                        self.register(clone)

