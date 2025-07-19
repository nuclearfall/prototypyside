# proto_helpers.py
import re
import uuid
from typing import Tuple, Optional, Dict
import importlib

def get_class_from_name(module_path, class_name):
    module = importlib.import_module(module_path)
    return getattr(module, class_name)

# Build a name-to-class mapping.
STRING_TO_CLASS = {
    "ComponentTemplate": ComponentTemplate,
    "Component": ComponentTemplate,  # If "Component" is just an alias
    "Image Element": ImageElement,
    "Text Element": TextElement,
    "Layout Template": LayoutTemplate,
    "Layout Page": LayoutTemplate,  # If this is an alias, otherwise use correct class
    "Layout Slot": LayoutSlot,
    "UnitStr": UnitStr,
    "UnitStrGeometry": UnitStrGeometry,

    # Object-only stuff
    "ProtoRegistry": ProtoRegistry,
    "RootRegistry": RootRegistry,
    "ObjectRegistry": ObjectRegistry,
    "ProtoFactory": ProtoFactory,
    "MailRoom": MailRoom,
    "ComponentScene": ComponentScene,
    "LayoutScene": LayoutScene,
    "LayoutTab": LayoutTab,
    "ComponentTab": ComponentTab,
    "MainWindow": MainWindow,
    # "Palette": Palette,
    # "Panel": Panel,
    # "Toolbar": Toolbar,
}

<<<<<<< Updated upstream

ELEMENT_PREFIXES = {"te", "ie"}
CHILD_PREFIXES = {"te", "ie", "ls", "pg", "cc"}


S

REGISTERED_PREFIXES = set(MODEL_ONLY) | set(OBJECT_ONLY)

=======
def parse_pid(pid_str: str) -> Tuple[Optional[str], Optional[str]]:
    pattern = r"^([a-zA-Z0-9]+)(?:_(.*))?$"
    match = re.match(pattern, pid_str)
    return (match.group(1), match.group(2)) if match else (None, None)
>>>>>>> Stashed changes

def issue_pid(prefix: str) -> str:
    if prefix not in REGISTERED_PREFIXES:
        raise ValueError(f"Invalid prefix '{prefix}'. Valid: {sorted(REGISTERED_PREFIXES)}")
    return f"{prefix}_{uuid.uuid4().hex}"

def parse_pid(pid_str: str) -> Tuple[Optional[str], Optional[str]]:
    # Accepts both prefix and full pid
    match = re.match(r"^([a-zA-Z0-9]+)(?:_([0-9a-fA-F]+))?$", pid_str)
    return (match.group(1), match.group(2)) if match else (None, None)

def is_pid(pid: str) -> bool:
    prefix, uuid_str = parse_pid(pid)
    if prefix not in REGISTERED_PREFIXES or not uuid_str:
        return False
    try:
        uuid.UUID(uuid_str, version=4)
        return True
    except Exception:
        return False

def is_pid_prefix(pid_or_prefix: str) -> bool:
    prefix, uuid_str = parse_pid(pid_or_prefix)
    return prefix in REGISTERED_PREFIXES and uuid_str is None

def get_prefix(pid: str) -> Optional[str]:
    """
    Extracts and returns the prefix from a pid string (e.g., 'te_1234abcd' → 'te').
    Returns None if the format is invalid or prefix is not registered.
    """
    prefix, _ = parse_pid(pid)
    if prefix in REGISTERED_PREFIXES:
        return prefix
    raise TypeError(f"{pid} is invalid. Registered prefixes are {sorted(REGISTERED_PREFIXES)}")


