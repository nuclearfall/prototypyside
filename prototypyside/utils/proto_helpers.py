# proto_helpers.py
import re
import uuid
from typing import Tuple, Optional, Dict, Type
import importlib

def get_class_from_name(module_path, class_name):
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


REGISTERED: Dict[str, str] = {
    "ie": "ImageElement",
    "te": "TextElement",
    "ve": "VectorElement",
    "ct": "ComponentTemplate",
    "cc": "Component",
    "lt": "LayoutTemplate",
    "pg": "Page",
    "ls": "LayoutSlot",
}

REGISTERED_PREFIXES = set(REGISTERED) 
REGISTERED_OBJECTS = set(REGISTERED.values())
REGISTERED_REVERSE_LOOKUP = {v: k for k, v in REGISTERED.items()}

def prefix_for_class(class_name: str) -> Optional[str]:
    return REGISTERED_REVERSE_LOOKUP.get(class_name)

def get_object_type(self, pid_str: str) -> Optional[Type]:
    """
    Returns the Python class/type associated with a given PID's prefix.
    Returns None if no type is mapped for the prefix.
    """
    prefix = get_prefix(pid_str) # Assume get_prefix handles invalid PID_STR formats by returning None or raising
    return self._PROTO_OBJECT_CLASSES.get(prefix)

def parse_pid(pid_str: str) -> Tuple[Optional[str], Optional[str]]:
    # Accepts both prefix and full pid
    match = re.match(r"^([a-zA-Z0-9]+)(?:_([0-9a-fA-F]+))?$", pid_str)
    return (match.group(1), match.group(2)) if match else (None, None)

def is_pid_prefix(pid_or_prefix: str) -> bool:
    prefix, uuid_str = parse_pid(pid_or_prefix)
    return prefix in REGISTERED_PREFIXES and uuid_str is None

def get_prefix(pid: Optional[str]) -> Optional[str]:
    if not pid:
        return None
    if pid in REGISTERED_PREFIXES:
        return pid
    parts = pid.split('_', 1)
    if parts[0] in REGISTERED_PREFIXES:
        return parts[0]
    return None

def parse_pid(pid: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Splits 'prefix_uuid' into (prefix, uuid).
    If only a prefix or uuid, returns (None, value).
    """
    if not pid:
        return (None, None)
    parts = pid.split('_', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return (None, parts[0])

def is_valid_uuid4_string(uuid_string: str) -> bool:
    try:
        val = uuid.UUID(uuid_string, version=4)
        return str(val) == uuid_string
    except Exception:
        return False

def resolve_pid(pid: Optional[str]) -> Optional[str]:
    """
    Resolves a PID:
      1. If no prefix is found, returns None.
      2. If input is only a valid prefix, returns a new PID with uuid4.
      3. If input is prefix_uuid:
         a. If both parts are valid, returns as-is.
         b. If prefix valid but uuid is invalid, returns new PID.
      4. All other cases, returns None.
    """
    if not pid:
        return None

    # Only a prefix (no underscore)
    if pid in REGISTERED_PREFIXES:
        return f"{pid}_{uuid.uuid4()}"

    # Split on first underscore (to support variable-length prefixes)
    parts = pid.split('_', 1)
    if len(parts) == 2:
        prefix, suffix = parts
        if prefix in REGISTERED_PREFIXES:
            if is_valid_uuid4_string(suffix):
                return pid
            else:
                return f"{prefix}_{uuid.uuid4()}"

    return None
