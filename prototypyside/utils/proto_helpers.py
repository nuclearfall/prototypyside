# from __future__ import annotations
# from enum import Enum, IntEnum
# from functools import lru_cache
# from pydoc import locate
# from typing import Any, Dict, Optional, Type, Tuple, Iterable
# import inspect
# import uuid


# class PIDState(IntEnum):
#     NOT   = 0   # not a string or unregistered prefix
#     PRE   = 1   # registered prefix, missing/invalid uuid
#     FULL  = 2   # registered prefix + valid uuid
#     CLONE = 3   # explicit clone request (valid prefix required)


# def _is_valid_uuid4_str(s: str) -> bool:
#     try:
#         u = uuid.UUID(s)
#         return u.version == 4
#     except (ValueError, TypeError, AttributeError):
#         return False


# class ProtoClass(Enum):
#     # value = (prefix, fully_qualified_class_name)
#     IE = ("ie", "prototypyside.models.image_element.ImageElement")
#     TE = ("te", "prototypyside.models.text_element.TextElement")
#     VE = ("ve", "prototypyside.models.vector_element.VectorElement")

#     CT = ("ct", "prototypyside.models.component_template.ComponentTemplate")
#     CC = ("cc", "prototypyside.models.component_template.Component")          # adjust if distinct
#     LT = ("lt", "prototypyside.models.layout_template.LayoutTemplate")
#     PG = ("pg", "prototypyside.models.layout_template.Page")                  # adjust if distinct
#     LS = ("ls", "prototypyside.models.layout_slot.LayoutSlot")

#     PR = ("pr", "prototypyside.services.proto_registry.ProtoRegistry")
#     RR = ("rr", "prototypyside.services.proto_registry.RootRegistry")
#     PF = ("pf", "prototypyside.services.proto_factory.ProtoFactory")
#     EM = ("em", "prototypyside.services.export_manager.ExportManager")
#     MM = ("mm", "prototypyside.services.merge_manager.MergeManager")

#     US = ("us", "prototypyside.utils.units.unit_str.ProtoClass.US")
#     UG = ("ug", "prototypyside.utils.units.unit_str_geometry.ProtoClass.UG")

#     # ---------- tuple unpackers ----------
#     @property
#     def prefix(self) -> str:
#         return self.value[0]

#     @property
#     def fqcn(self) -> str:
#         return self.value[1]

#     # ---------- resolution ----------
#     @lru_cache(maxsize=None)
#     def resolve(self) -> Type[Any]:
#         """Import and return the concrete class (cached)."""
#         cls = locate(self.fqcn)
#         if cls is None or not inspect.isclass(cls):
#             raise ImportError(f"Could not import class: {self.fqcn}")
#         return cls

#     # ---------- reverse maps (lazy) ----------
#     @classmethod
#     @lru_cache(maxsize=1)
#     def _by_prefix(cls) -> Dict[str, "ProtoClass"]:
#         return {m.prefix: m for m in cls}

#     @classmethod
#     @lru_cache(maxsize=1)
#     def _by_class(cls) -> Dict[Type[Any], "ProtoClass"]:
#         mapping: Dict[Type[Any], ProtoClass] = {}
#         for m in cls:
#             try:
#                 mapping[m.resolve()] = m
#             except Exception:
#                 # ignore entries that aren't importable in this environment
#                 continue
#         return mapping

#     # ---------- convenience lookups ----------
#     @classmethod
#     def registered_prefixes(cls) -> Iterable[str]:
#         return cls._by_prefix().keys()

#     @classmethod
#     def from_prefix(cls, prefix: str) -> Optional["ProtoClass"]:
#         return cls._by_prefix().get(prefix)

#     @classmethod
#     def from_pid(cls, pid: str) -> Optional["ProtoClass"]:
#         if not isinstance(pid, str) or "_" not in pid:
#             return None
#         pre = pid.split("_", 1)[0]
#         return cls.from_prefix(pre)

#     @classmethod
#     def from_class(cls, obj_or_cls: Any) -> Optional["ProtoClass"]:
#         kls = obj_or_cls if inspect.isclass(obj_or_cls) else type(obj_or_cls)
#         return cls._by_class().get(kls)

#     # ---------- PID helpers (moved from module scope) ----------
#     @classmethod
#     def split_pid(
#         cls,
#         pid_str: Optional[str],
#         *,
#         is_clone: bool = False,
#     ) -> Tuple[PIDState, Optional["ProtoClass"], Optional[str]]:
#         """
#         Classify a PID-like string into (state, enum_member, suffix_uuid).
#           - (NOT, None, None)           : not a string or unregistered prefix
#           - (PRE, member, None)         : registered prefix, uuid missing/invalid
#           - (FULL, member, uuid)        : registered prefix + valid uuid (lowercased later)
#           - (CLONE, member, None)       : cloning requested and prefix is registered
#         """
#         if not isinstance(pid_str, str):
#             return PIDState.NOT, None, None

#         parts = pid_str.split("_", 1)
#         member = cls.from_prefix(parts[0])
#         if member is None:
#             return PIDState.NOT, None, None

#         if is_clone:
#             return PIDState.CLONE, member, None

#         if len(parts) == 2 and _is_valid_uuid4_str(parts[1]):
#             return PIDState.FULL, member, parts[1].lower()
#         return PIDState.PRE, member, None

#     @classmethod
#     def validate_pid(
#         cls,
#         pid: Optional[str],
#         *,
#         is_clone: bool = False,
#     ) -> Optional[str]:
#         """
#         Resolve a PID to a canonical string or a newly minted one (state-based):
#           • NOT   → None
#           • PRE   → mint '<prefix>_<uuid4>'
#           • FULL  → canonicalize to '<prefix>_<uuid4-lower-hyphen>'
#           • CLONE → mint '<prefix>_<uuid4>'
#         """
#         state, member, suffix = cls.split_pid(pid)
#         if state is PIDState.NOT or member is None:
#             return None

#         if state is PIDState.FULL:
#             # Normalize the uuid to the canonical hex-with-hyphens lowercase form.
#             return f"{member.prefix}_{str(uuid.UUID(suffix))}"

#         # PRE or CLONE → mint
#         return f"{member.prefix}_{uuid.uuid4()}"

#     @classmethod
#     def parse_pid(
#         cls,
#         pid: Optional[str],
#     ) -> Tuple[PIDState, Optional["ProtoClass"], Optional[str]]:
#         """
#         Like split_pid, but never treats a clone as a forced CLONE state.
#         Useful when you just want to know if the PID is fully valid.
#         """
#         return cls.split_pid(pid, is_clone=False)

#     @classmethod
#     def ensure_pid_for(
#         cls,
#         obj_or_cls: Any,
#         pid: Optional[str],
#         *,
#         is_clone: bool = False,
#     ) -> Optional[str]:
#         """
#         Ensure/normalize a PID for the given object/class.
#         - If pid already FULL for a known prefix → normalized string.
#         - If pid has only a known prefix → mint with that prefix.
#         - If pid is None → infer prefix from obj_or_cls and mint.
#         - If cloning → mint regardless of whether a full pid exists.
#         """
#         # Try to resolve directly (handles PRE/FULL for known prefixes)
#         rp = cls.validate_pid(pid)
#         if rp is not None:
#             return rp

#         # If we couldn't resolve (e.g., pid was None or unknown), infer prefix from class
#         member = cls.from_class(obj_or_cls)
#         return f"{member.prefix}_{uuid.uuid4()}" if member else None

#     # ---------- tiny helpers you’ll actually use ----------
#     def class_(self) -> Type[Any]:
#         """Alias for resolve()."""
#         return self.resolve()

#     def make_pid(self, uid: Optional[str] = None) -> str:
#         """Make a PID with this enum’s prefix."""
#         return f"{self.prefix}_{uid or uuid.uuid4()}"
