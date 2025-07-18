from PySide6.QtCore import QObject, Signal

class GlobalHub(QObject):
    object_registered = Signal(object, object)
    object_deregistered = Signal(object, object)
    object_orphaned = Signal(object, object)

    def __init__(self):
        super().__init__()
        print("[DEBUG] GlobalProtoHub instantiated")

    def global_get_by_prefix(self, prefix: str):
        from .proto_registry import ProtoRegistry  # lazy import to avoid circular import
        found = []
        for r in ProtoRegistry.all():
            found.extend(r.global_get_by_prefix(prefix))
            print(f"[GlobalHub] global_get_by_prefix: {prefix}")

        return found


# Single shared instance
global_hub = GlobalHub()
