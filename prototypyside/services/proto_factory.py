# prototypyside/services/proto_factory.py
from __future__ import annotations

import uuid
import inspect
from functools import lru_cache
from typing import Any, Optional, Type, TYPE_CHECKING

from prototypyside.services.proto_class import ProtoClass

@lru_cache(maxsize=None)
def _import_fqcn(fqcn: str) -> Type[Any]:
    mod, _, cls_name = fqcn.rpartition(".")
    if not mod:
        raise ValueError(f"'{fqcn}' is not a fully-qualified class name")
    module = importlib.import_module(mod)
    kls = getattr(module, cls_name)
    if not inspect.isclass(kls):
        raise TypeError(f"{fqcn} did not resolve to a class")
    return kls

class ProtoFactory:
    """
    Minimal, enum-only factory.
    - No prefix strings.
    - No PID parsing or minting policy beyond uuid4 (unless caller provides pid).
    - Resolution is lazy via ProtoClass.resolve() and cached.
    """

    # ---------- Resolution ----------

    @staticmethod
    @lru_cache(maxsize=None)
    def class_for(proto: ProtoLike) -> Type[Any]:
        if proto is ProtoClass:
            raise TypeError("Expected a ProtoClass *member* (e.g., ProtoClass.CT), a class, or an FQCN string.")

        if isinstance(proto, ProtoClass):
            return proto.resolve()

        if inspect.isclass(proto):
            return proto

        if isinstance(proto, str):
            mod, _, cls_name = proto.rpartition(".")
            if not mod:
                raise ValueError(f"'{proto}' is not a fully-qualified class name")
            module = importlib.import_module(mod)
            kls = getattr(module, cls_name)
            if not inspect.isclass(kls):
                raise TypeError(f"{proto} did not resolve to a class")
            return kls

        raise TypeError(f"Unsupported proto type: {type(proto)!r}")

    @classmethod
    def create(cls, proto: ProtoLike, *, pid: str | None, registry, ctx, **kwargs) -> Any:
        """
        Construct a new object of the given proto.
        - If your models still require prefixed PIDs, pass `pid` explicitly.
        - Any other ctor kwargs (e.g., geometry, name) are forwarded.
        """
        kls = proto.resolve()
        if registry is not None:
            return kls(proto=proto, pid=pid, registry=registry, ctx=ctx, **kwargs)

    # ---------- Serialization methods ---------- #
    @classmethod
    def to_dict(cls, obj: Any) -> dict:
        return obj.to_dict()

    @classmethod
    def from_dict(cls, data: dict, *, registry):
        proto = ProtoClass.from_prefix(data.get("pid"))
        if not proto:
            raise ValueError(f"Failed to load obj: {data.get('pid')} is not a valid ProtoClass")
        kls = proto.resolve()   # must resolve CC -> Component class, PG -> Page class, etc.

        return kls.from_dict(data=data, registry=registry)

    # @classmethod
    # def clone(cls, obj: Any, *, registry) -> Any:
    #     # Map runtime type -> ProtoClass. Use your existing helper if different.

    #     data = cls.to_dict(obj)
    #     return cls.from_dict(data, registry=registry)
