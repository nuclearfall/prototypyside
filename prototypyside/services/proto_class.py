# prototypyside/services/proto_class.py

from __future__ import annotations
from enum import Enum, IntEnum
from functools import lru_cache
from typing import Any, Dict, Optional, Type, Tuple, Iterable
import importlib, inspect, uuid

class PIDState(IntEnum):
    NOT   = 0
    PRE   = 1
    FULL  = 2
    CLONE = 3

def _is_valid_uuid4_str(s: str) -> bool:
    try:
        u = uuid.UUID(s)
        return u.version == 4
    except Exception:
        return False

class ProtoClass(Enum):
    CE   = ("ce",  "prototypyside.models.component_element.ComponentElement")
    IE   = ("ie",  "prototypyside.models.image_element.ImageElement")
    TE   = ("te",  "prototypyside.models.text_element.TextElement")
    EO   = ("eo",  "prototypyside.views.overlays.ElementOutline")

    CC   = ("cc",  "prototypyside.models.component.Component")    
    CT   = ("ct",  "prototypyside.models.component_template.ComponentTemplate")
    LT   = ("lt",  "prototypyside.models.layout_template.LayoutTemplate")
    PG   = ("pg",  "prototypyside.models.layout_template.Page")
    LS   = ("ls",  "prototypyside.models.layout_slot.LayoutSlot")

    PR   = ("pr",  "prototypyside.services.proto_registry.ProtoRegistry")
    RR   = ("rr",  "prototypyside.services.proto_registry.RootRegistry")
    PF   = ("pf",  "prototypyside.services.proto_factory.ProtoFactory")
    EM   = ("em",  "prototypyside.services.export_manager.ExportManager")
    MM   = ("mm",  "prototypyside.services.merge_manager.MergeManager")

    CTAB = ("ctab","prototypyside.views.tabs.component_tab.ComponentTab")
    LTAB = ("ltab","prototypyside.views.tabs.layout_tab.LayoutTab")
    US   = ("us",  "prototypyside.utils.units.unit_str.UnitStr")
    UG   = ("ug",  "prototypyside.utils.units.unit_str_geometry.UnitStrGeometry")

    USF  = ("usf", "prototypyside.widgets.unit_str_field.UnitStrField")
    USSF  = ("ussf", "prototypyside.widgets.unit_strings_field.UnitStringsField")
    USGF  = ("usgf", "prototypyside.widgets.unit_str_geometry_field.UnitStrGeometryField")

    def __new__(cls, prefix: str, fqcn: str):
        obj = object.__new__(cls)
        obj._prefix = prefix
        obj._fqcn = fqcn
        obj._value_ = fqcn   # no import at definition time
        return obj

    @property
    def prefix(self) -> str:
        return self._prefix

    @property
    def fqcn(self) -> str:
        return self._fqcn

    @lru_cache(maxsize=None)
    def resolve(self) -> Type[Any]:
        """Import and return the concrete class lazily (first use), then cache."""
        module_path, _, class_name = self.fqcn.rpartition(".")
        mod = importlib.import_module(module_path)        # uses sys.modules cache
        kls = getattr(mod, class_name)
        if not inspect.isclass(kls):
            raise ImportError(f"{self.fqcn} did not resolve to a class")
        return kls

    def new(self, *args, **kwargs):
        """Instantiate the resolved class."""
        return self.resolve()(*args, **kwargs)

    def class_(self) -> Type[Any]:  # optional alias
        return self.resolve()

    # ---------- reverse maps (lazy) ----------
    @classmethod
    @lru_cache(maxsize=1)
    def _by_prefix(cls) -> Dict[str, "ProtoClass"]:
        return {m.prefix: m for m in cls}

    @classmethod
    @lru_cache(maxsize=1)
    def _by_class(cls) -> Dict[Type[Any], "ProtoClass"]:
        mapping: Dict[Type[Any], ProtoClass] = {}
        for m in cls:
            try:
                mapping[m.resolve()] = m
            except Exception:
                pass
        return mapping

    # ---------- convenience lookups ----------
    @classmethod
    def registered_prefixes(cls) -> Iterable[str]:
        return cls._by_prefix().keys()

    @classmethod
    def is_registered_prefix(cls, prefix):
        return prefix in cls.registered_prefixes()

    @classmethod
    def from_prefix(cls, prefix_or_pid: str) -> Optional["ProtoClass"]:
        if not isinstance(prefix_or_pid, str):
            return None
        prefix = prefix_or_pid.strip().split("_", 1)[0].lower()
        return cls._by_prefix().get(prefix)

    @classmethod
    def from_class(cls, obj_or_cls: Any) -> Optional["ProtoClass"]:
        kls = obj_or_cls if inspect.isclass(obj_or_cls) else type(obj_or_cls)
        return cls._by_class().get(kls)

    @classmethod
    def isproto(cls, obj, pc_type_or_list):
        pc = cls.from_class(obj)
        if isinstance(pc_type_or_list, (list, set, tuple)):
            return any(pc == t for t in pc_type_or_list)
        return pc == pc_type_or_list


    # ---------- PID helpers ----------
    @classmethod
    def split_pid(cls, pid_str: Optional[str]):
        if not isinstance(pid_str, str):
            return PIDState.NOT, None, None

        parts = pid_str.split("_", 1)
        prefix, uid = (parts[0], parts[1] if len(parts) > 1 else None)

        if cls.is_registered_prefix(prefix):
            if _is_valid_uuid4_str(uid):
                return PIDState.FULL, prefix, uid.lower()
            return PIDState.PRE, prefix, None

        return PIDState.NOT, None, None

    @classmethod    
    def get_prefix_of(cls, member: "ProtoClass") -> str:
        return member.prefix

    @classmethod
    def issue_pid(cls, src: Union[str, "ProtoClass", Any]) -> Optional[str]:
        """
        Accepts:
          - str: a PID or bare prefix (e.g., "te" or "te_..."),
          - ProtoClass: an enum member (e.g., ProtoClass.TE),
          - object or class: resolves via from_class().
        Returns a new PID "prefix_uuid4" if a valid prefix can be determined, else None.
        """
        if isinstance(src, str):
            member = cls.from_prefix(src)        # handles pid or bare prefix
        elif isinstance(src, ProtoClass):
            member = src
        else:
            member = cls.from_class(src)         # works for class or instance

        return member.make_pid() if member else None

    @classmethod
    def validate_pid(cls, pid: str) -> str:
        state, _, _ = cls.split_pid(pid)
        if state is PIDState.PRE:
            return self.make_pid(pid)
        if state is PIDState.FULL:
            return pid
        else:
            raise ValueError("value must be either a valid prefix or pid")

    @classmethod
    def ensure_pid_for(cls, obj_or_cls: Any, pid: Optional[str]):
        rp = cls.validate_pid(pid)
        if rp is not None:
            return rp
        member = cls.from_class(obj_or_cls)
        return f"{member.prefix}_{uuid.uuid4()}" if member else None

    @classmethod
    def is_valid_pid(cls, pid: Optional[str]) -> bool:
        state, _, _ = cls.split_pid(pid)
        return state is PIDState.FULL
        
    def make_pid(self, uid: Optional[str] = None) -> str:
        """Instance (enum member) helper for creating PIDs with this prefix."""
        return f"{self.prefix}_{uid or uuid.uuid4()}"

    @classmethod
    def get_prefix(cls, pid: Optional[str]) -> Optional[str]:
        _, prefix, _ = cls.split_pid(pid)
        return prefix

