# proto_registry.py
import re
import json
import uuid
import re
from typing import Any, Dict, List, Optional, Union, Tuple, Type, TYPE_CHECKING
from pathlib import Path
from PySide6.QtCore import QObject, Signal

from prototypyside.utils.valid_path import ValidPath
from prototypyside.services.proto_factory import ProtoFactory
from prototypyside.services.proto_class import ProtoClass

if TYPE_CHECKING:
    from prototypyside.services.app_settings import AppSettings

_SUFFIX_RE = re.compile(r"^(?P<root>.*)\((?P<n>\d+)\)\s*$")

BASE_NAMES = {
    "te": "Text Element",
    "ie": "Image Element",
    "ce": "Component Element", # Should never be used but exists for ProtoClass.
    "ct": "Component Template",
    "cc": "Component",
    "lt": "Layout Template",
    "pg": "Page",
    "ls": "Layout Slot",
}
pc = ProtoClass
class ProtoRegistry(QObject):
    object_registered = Signal(str)  # pid
    object_deregistered = Signal(str)

    def __init__(self, root, settings: "AppSettings", parent=None):
        super().__init__(parent)

        self._factory = ProtoFactory()
        self._settings = settings
        self._ctx = settings.ctx
        self._is_root = isinstance(self, RootRegistry)
        self.root = self if self._is_root else root
        self._template = None
        self._store: Dict[str, Any] = {}
        self._orphans: Dict[str, Any] = {}
        # self._unique_names = set()
        self._name_map = {v:1 for v in BASE_NAMES.values()}

    def get_registry(self, pid: str):
        # 1. Check self
        if pid in self._store:
            return self

        # 2. Check root (if not self)
        root = self.root
        if root is not self and pid in root._store:
            return root

        # 3. Check siblings (other direct children of root, not self)
        for sibling in root._children:
            if sibling is not self and pid in sibling._store:
                return sibling

        # 4. Not found
        return None

    @property
    def is_root(self):
        return True if self.root == self else False

    @property
    def factory(self):
        return self._factory

    @property
    def settings(self) -> "AppSettings":
        return self._settings

    @settings.setter
    def settings(self, obj: "AppSettings"):
        if isinstance(obj, "AppSettings"):
            self._settings = obj  
        else:
            raise TypeError(f"Settings must be an AppSettings object, not {type(obj)}")

    def register(self, obj: object, overwrite: bool = False):
        pid = getattr(obj, "pid", None)
        if not isinstance(pid, str) or not pid:
            raise TypeError(f"[Registry] object {obj!r} missing valid string pid")

        if pid in self._store and not overwrite:
            raise KeyError(f"Attempted duplicate entry of {obj.pid} without overwrite.")
            # Already registered; do nothing.
            return

        self._store[pid] = obj
        self.object_registered.emit(pid)

    def get(self, pid):
        if pid is None:
            raise ValueError("[Registry] Cannot get object: PID is None")
        return self._store.get(pid)

    def find_root(self):
        parent = self.parent()
        while parent:
            if isinstance(parent, RootRegistry):
                return parent
            parent = parent.parent()
        raise RuntimeError("No RootRegistry found in parent chain.")

    def orphans(self):
        return [o for o in self._orphans]

    def find(self, pid):
        return pid in self._store.get("pid", self.global_get("pid"))

    def _split_suffix(self, s: str) -> tuple[str, Optional[int]]:
        m = _SUFFIX_RE.fullmatch(s.strip())
        if not m:
            return s.strip(), None
        root = m.group(1).strip()
        n = int(m.group(2)) if m.group(2) else None
        return root, n

    def map_name(self, proto: ProtoClass, name: str) -> str:
        """
        Ensure uniqueness for `name` within this ProtoClass family.
        First use => 'foo'; then 'foo(2)', 'foo(3)', ...
        Explicit suffix (e.g. 'foo(7)') is honored if free.
        """
        root, n = self._split_suffix(name)
        name_map = self._name_map.setdefault(proto, {})  # dict[str, int], values = max used index

        # When dealing with a template, it's name is mapped in the root registry.
        if proto in [pc.CT, pc.LT]:
            name_map = self.root._name_map.setdefault(proto, {})
        current = name_map.get(root, 0)
        if n is None:
            # No explicit suffix: allocate next
            if current == 0:
                name_map[root] = 1
                return root
            name_map[root] = current + 1
            return f"{root}({name_map[root]})"
        else:
            # Explicit suffix requested
            if n > current:
                name_map[root] = n
                return root if n == 1 else f"{root}({n})"
            name_map[root] = current + 1
            return f"{root}({name_map[root]})"

    def validate_name(
        self,
        proto: ProtoClass,
        name: str | Path | None = None
    ) -> str:
        if not isinstance(proto, ProtoClass):
            raise TypeError("proto must be a ProtoClass")

        # Determine a base string WITHOUT ever doing str(None)
        base: Optional[str] = None
        if name is not None:
            base = ValidPath.file(name, must_exist=True, return_stem=True)
            if not base:
                if isinstance(name, Path):
                    base = (name.stem or name.name).strip()
                elif isinstance(name, str):
                    base = name.strip()

        # Fallback to proto default if needed
        if not base:
            prefix = ProtoClass.get_prefix_of(proto)
            base = BASE_NAMES.get(prefix, proto.name.title())

        # Light sanitization: printable chars only
        base = "".join(ch for ch in base if ch.isprintable()).strip() or proto.name.title()

        return self.map_name(proto, base)

    def found_here(self, pid):
        return self.get("pid")

    def create(self, proto: ProtoClass, **kwargs):
        """
        Create a new model via the enum member.
        """
        if not isinstance(proto, ProtoClass):
            raise TypeError(f"create() expects a ProtoClass member, got {proto}")
        pid = ProtoClass.issue_pid(proto)
        name = kwargs.get("name", None)
        kwargs = {k:v for k, v in kwargs.items() if k not in ["proto", "name", "pid"]}
        registry = self
        obj = self._factory.create(proto=proto, pid=pid, 
            registry=self, name=name, **kwargs)

        return obj

    def load_schema(model_name: str) -> dict:
        if model_name not in _schema_cache:
            path = SCHEMA_DIR / f"{model_name}.json"
            _schema_cache[model_name] = json.loads(path.read_text())
        return _schema_cache[model_name]

    def get_schema_defaults(model_name: str) -> dict:
        if model_name not in _defaults_cache:
            schema = load_schema(model_name)
            _defaults_cache[model_name] = extract_defaults(schema)
        return _defaults_cache[model_name]

    def deregister(self, pid: str):
        """
        Remove from store, move to orphans, emit object_deregistered.
        """
        obj = self._store.get('pid', self.global_get(pid))
        obj = self._store.pop(pid, None)
        if not obj:
            print(f"Warning: cannot deregister missing PID '{pid}'")
            return
        self._orphans[pid] = obj
        self.object_deregistered.emit(obj.pid)

    def to_dict(self, obj) -> object:
        # only dump things that know how to to_dict()
        if not hasattr(obj, "to_dict"):
            print(f"Failed to dump obj: {obj} because it can't be serialized")
            return None
        data = self._factory.to_dict(obj)
        return data

    # recursively rehydrates proto objects
    def from_dict(self, data: dict, registry=None):
        # 1) Construct the parent via factory/model from_dict (parent-only)
        registry = registry if registry else self
        obj = self._factory.from_dict(data, registry=self)

        # 2) Register parent immediately (so children can reference it if needed)
        self.register(obj)

        # 3) Rehydrate 'items' if present (preserve PIDs)
        items_data = data.get("items")
        if isinstance(items_data, (list, tuple)):
            children = []
            for child_data in items_data:
                child = self.from_dict(child_data)  # recursive; registers child
                # If these are QGraphicsObjects, attach them as children in the scene:
                if hasattr(child, "setParentItem") and hasattr(obj, "setParentItem"):
                    child.setParentItem(obj)
                children.append(child)
            # Assign to the obj (both ComponentTemplate and LayoutTemplate expose .items)
            setattr(obj, "items", children)

        # 4) Rehydrate 'content' if present (e.g., LayoutSlot.content)
        #    Support both embedded object dict and pid reference (if you ever add that).
        content_data = data.get("content", None)
        if content_data is not None and hasattr(obj, "content"):
            if isinstance(content_data, dict):
                content_obj = self.from_dict(content_data)
            else:
                # If you later store content by pid string, resolve via registry here.
                content_obj = content_data
            setattr(obj, "content", content_obj)

        return obj

    def clone(self, obj: Any, register: bool = True, registry=None):
        registry = registry if registry else self
        # 1) Serialize source
        data = self._factory.to_dict(obj)

        # 2) Issue fresh PID for the parent clone (preserve prefix via ProtoClass)
        proto = ProtoClass.from_prefix(data.get("pid"))
        if proto == ProtoClass.CT:
            proto = ProtoClass.CC
            
        data["pid"] = ProtoClass.issue_pid(proto)
        print(f"Creating clone with pid: {data.get("pid")}")
        # 3) Lineage (only if type carries tpid)
        if hasattr(obj, "tpid"):
            data["tpid"] = getattr(obj, "tpid", None) or obj.pid
        if proto is ProtoClass.CC:
            print("Pid issued for Component dropped into slot.")

        # 4) Strip children from data before constructing clone
        #    (prevents reusing child PIDs on clone)
        data.pop("items", None)

        # 5) Construct the parent clone
        clone = self._factory.from_dict(data, registry=registry)

        # 6) Clone per-object content (e.g., LayoutSlot.content) if present
        content = getattr(obj, "content", None)
        if content is not None and proto == ProtoClass.LS:
            setattr(clone, "content", self.clone(content, register=register))

        # 7) Clone children (deep) if this type has items
        src_items = getattr(obj, "items", None)

        if isinstance(src_items, (list, tuple)):
            cloned_items = []
            for child in src_items:
                child_clone = self.clone(child, register=register, registry=registry)
                # Parent/scene wiring for QGraphicsItems
                if hasattr(child_clone, "setParentItem") and hasattr(clone, "setParentItem"):
                    child_clone.setParentItem(clone)
                cloned_items.append(child_clone)
            setattr(clone, "items", cloned_items)

        # 8) Register the clone
        registry = registry if registry else self

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
        return True if pid in self._orphans and not self.get(pid) else False

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

    def get_by_prefix(self, prefix: Optional[str]) -> list[object]:
        if not prefix:
            return []
        prefix = prefix.lower()
        return [v for k, v in self._store.items() if isinstance(k, str) and k.lower().startswith(prefix + "_")]

    def global_get_by_prefix(self, prefix: Optional[str] = None) -> list[object]:
        if not prefix:
            return []
        results = self.get_by_prefix(prefix)
        root = self.root
        for child in getattr(root, "_children", []):
            results += child.get_by_prefix(prefix)
        return results

    def get_last(self, prefix=None) -> object:
        vals = list(self._store.values())
        return vals[-1] if vals else None

    def get_first(self) -> object:
        vals = list(self._store.values())
        return vals[0] if vals else None


class RootRegistry(ProtoRegistry):
    object_registered = Signal(str)
    object_deregistered = Signal(str)

    def __init__(self, root, settings: "AppSettings", parent=None):
        super().__init__(root=self, settings=settings, parent=parent)
        self._is_root=True
        self._template = None
        self._children = []

    def new(self):
        return ProtoRegistry(root=self, settings=self.settings, parent=self)

    def new_with_template(self, proto: ProtoClass, **kwargs):
        new = ProtoRegistry(root=self, settings=self.settings)
        pid = ProtoClass.make_pid(proto)
        # name = self.validate_name(proto)
        template = new.create(proto=proto, **kwargs)
        new._template = template
        self.add_child(new)
        self.register(template)
        return new, template

    def load_with_template(self, data):
        new = ProtoRegistry(root=self, settings=self.settings)
        template = new.from_dict(data)
        new._template = template
        self.add_child(new)
        self.register(template)
        return new, template

    def add_child(self, child, template):
        child.root = self
        if template.pid not in child._store:
            child.register(template)
        self._children.append(child)
        self._repeat_registered(template.pid)


    def remove_child(self, child):
        if child in self._children:
            # Deregister all objects
            for key in list(child._store.keys()):
                child.deregister(key)

            # Clean up orphans safely
            for key in list(child._orphans.keys()):
                del child._orphans[key]

            child.root = None
            self._children.remove(child)

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
