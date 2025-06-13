# proto_helpers.py
import re
import uuid
from typing import Tuple, Optional


# Move this here to avoid circular imports from proto_factory
VALID_ID_PREFIXES = {"te", "ie", "ct", "ci", "lt", "ls"}
ELEMENT_PREFIXES = {"te", "ie"}
OBJ_BASE_NAMES = {
    "ie": "Image Element",
    "te": "Text Element",
    "ct": "Component Template",
    "ci": "Component Instance",
    "lt": "Page Layout Template",
    "ls": "Layout Slot",
    "pr": "Proto Registry"
}

def parse_pid(pid_str: str) -> Tuple[Optional[str], Optional[str]]:
    pattern = r"^([a-zA-Z0-9]+)(?:_(.*))?$"
    match = re.match(pattern, pid_str)
    return (match.group(1), match.group(2)) if match else (None, None)

def issue_pid(prefix: str) -> str:
    if prefix not in VALID_ID_PREFIXES:
        raise ValueError(f"Invalid prefix '{prefix}'. Valid: {VALID_ID_PREFIXES}")
    return f"{prefix}_{uuid.uuid4().hex}"

def is_pid(pid_or_prefix: str) -> bool:
    prefix, uuid_str = parse_pid(pid_or_prefix)
    if prefix not in VALID_ID_PREFIXES or not uuid_str:
        return False
    try:
        uuid.UUID(uuid_str, version=4)
        return True
    except (ValueError, TypeError, AttributeError):
        return False

def is_pid_prefix(pid_or_prefix: str) -> bool:
    prefix, uuid_str = parse_pid(pid_or_prefix)
    if prefix not in VALID_ID_PREFIXES:
        return False
    if uuid_str is None:
        return True
    try:
        uuid.UUID(uuid_str, version=4)
        return False
    except (ValueError, TypeError, AttributeError):
        return True

def get_prefix(pid: str) -> Optional[str]:
    """
    Extracts and returns the prefix from a pid string (e.g., 'te_1234abcd' → 'te').
    Returns None if the format is invalid.
    """
    if not isinstance(pid, str):
        return None

    prefix, _ = parse_pid(pid)
    return prefix

