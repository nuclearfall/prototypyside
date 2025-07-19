import os
import sys
import pytest
from pathlib import Path

# Headless Qt for QGraphicsObjects
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtWidgets import QApplication
_app = QApplication(sys.argv)

from prototypyside.services.proto_registry import RootRegistry, ProtoRegistry
from prototypyside.models.component_template import ComponentTemplate
from prototypyside.models.layout_template import LayoutTemplate
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.proto_helpers import issue_pid

# Shared geometry for tests
usg = UnitStrGeometry(x=0, y=0, width=4, height=2, unit="in", dpi=300)

# Keys to skip in deep comparison (geometry & linking fields)
GEOM_KEYS = {
    'geometry', 'border_width', 'corner_radius',
    'margin_top', 'margin_bottom', 'margin_left', 'margin_right',
    'spacing_x', 'spacing_y'
}

# Ignore pid, name, and tpid fields in deep comparison
IGNORE_KEYS = ('pid', 'name', 'tpid')


def assert_deep_equal_skip_geometry(a, b, ignore_keys=IGNORE_KEYS):
    """Recursively compare dicts/lists, skipping geometry & linking keys."""
    if isinstance(a, dict) and isinstance(b, dict):
        for key, av in a.items():
            if key in ignore_keys or key in GEOM_KEYS:
                continue
            assert key in b, f"Missing key {key!r} in clone"
            assert_deep_equal_skip_geometry(av, b[key], ignore_keys)
        for key in b:
            if key in ignore_keys or key in GEOM_KEYS:
                continue
            assert key in a, f"Extra key {key!r} in clone"
    elif isinstance(a, list) and isinstance(b, list):
        assert len(a) == len(b), f"List length {len(a)} != {len(b)}"
        for ai, bi in zip(a, b):
            assert_deep_equal_skip_geometry(ai, bi, ignore_keys)
    else:
        assert a == b, f"{a!r} != {b!r}"


@pytest.fixture

def registry():
    root = RootRegistry()
    return ProtoRegistry(parent=root, root=root)


def test_component_template_clone(registry):
    orig = ComponentTemplate(issue_pid("ct"), geometry=usg, registry=registry)
    child = registry.create("te", geometry=usg)
    orig.items.append(child)

    clone = registry.clone(orig)

    # New PID prefix and distinct PID
    assert clone.pid.startswith("cc_"), "Clone PID prefix incorrect"
    assert clone.pid != orig.pid, "Clone PID should differ from original"

    # Registry bookkeeping
    assert registry.get(clone.pid) is clone

    # Deep compare excluding geometry & linking fields
    d1, d2 = orig.to_dict(), clone.to_dict()
    assert_deep_equal_skip_geometry(d1, d2)

    # Ensure child was cloned, not shared
    assert clone.items[0] is not orig.items[0]
    assert clone.items[0].pid.startswith("te_"), "Child PID prefix incorrect"


def test_layout_template_clone(registry):
    orig = LayoutTemplate(issue_pid("lt"), geometry=usg, registry=registry)
    slot = registry.create("ls", geometry=usg)
    orig.items = [[slot]]

    clone = registry.clone(orig)

    # New PID prefix
    assert clone.pid.startswith("pg_"), "Clone PID prefix incorrect"
    assert clone.pid != orig.pid, "Clone PID should differ from original"

    # Grid structure preserved
    assert isinstance(clone.items, list)
    assert isinstance(clone.items[0], list)
    assert clone.items[0][0].pid.startswith("ls_"), "Slot PID prefix incorrect"

    # Deep compare excluding geometry & linking fields
    d1, d2 = orig.to_dict(), clone.to_dict()
    assert_deep_equal_skip_geometry(d1, d2)
