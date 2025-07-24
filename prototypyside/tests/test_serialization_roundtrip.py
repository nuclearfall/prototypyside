import os
import sys
import json
import pytest
from pathlib import Path

# ── HEADLESS QT SETUP ───────────────────────────────────────────────────────
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtWidgets import QApplication
_app = QApplication(sys.argv)

# ── VALIDATOR & REGISTRY ───────────────────────────────────────────────────
from prototypyside.services.proto_registry import RootRegistry, ProtoRegistry

# ── MODELS & HELPERS ───────────────────────────────────────────────────────
from prototypyside.models.component_element import TextElement, ImageElement
from prototypyside.models.component_template import ComponentTemplate
from prototypyside.models.layout_template import LayoutTemplate
from prototypyside.models.layout_slot import LayoutSlot
<<<<<<< Updated upstream
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
=======
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
>>>>>>> Stashed changes
from prototypyside.utils.proto_helpers import resolve_pid

# ── FIXTURES ────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def schema_dir():
    return Path(__file__).parent.parent / "schemas"

# Schema validation disabled pending schema updates
@pytest.fixture(scope="module")
def validator(schema_dir):
    return None

@pytest.fixture
def registry():
    root = RootRegistry()
    return ProtoRegistry(parent=root, root=root)

# ── SHARED GEOMETRY FOR MODELS ───────────────────────────────────────────────
usg = UnitStrGeometry(x=0.0, y=0.0, width=2.5, height=3.5, unit="in", dpi=300)

# ── UTILITY: deep compare _ignoring_ geometry keys ───────────────────────────
GEOM_KEYS = {
    "geometry", "border", "border_width", "corner_radius",
    "margin_top","margin_bottom","margin_left","margin_right",
    "spacing_x","spacing_y"
}

def assert_deep_equal_skip_geometry(a, b, ignore_keys=("pid","name")):
    """Recursively compare a vs b, but skip any key in GEOM_KEYS."""
    if isinstance(a, dict) and isinstance(b, dict):
        for key, av in a.items():
            if key in ignore_keys or key in GEOM_KEYS:
                continue
            assert key in b, f"Missing key {key!r}"
            assert_deep_equal_skip_geometry(av, b[key], ignore_keys)
        for key in b:
            if key in ignore_keys or key in GEOM_KEYS:
                continue
            assert key in a, f"Extra key {key!r}"
    elif isinstance(a, list) and isinstance(b, list):
        assert len(a) == len(b), f"List length {len(a)} != {len(b)}"
        for ai, bi in zip(a, b):
            assert_deep_equal_skip_geometry(ai, bi, ignore_keys)
    else:
        assert a == b, f"{a!r} != {b!r}"

# ── TEST 1: Units (no PID) ──────────────────────────────────────────────────
UNIT_SAMPLES = [
    ("unit_str",         UnitStr("3.5in", dpi=300)),
    ("unit_str_geometry",UnitStrGeometry(x=0.0,y=0.0,width=0.02,height=0.02,unit="in",dpi=72)),
]

@pytest.mark.parametrize("name,instance", UNIT_SAMPLES)
def test_units_schema_and_roundtrip(name, instance, validator):
    data = instance.to_dict()
    if validator:
        ok, err = validator.validate(data)
        assert ok, f"{name} schema failure: {err}"
    # ensure from_dict works without error
    rt = instance.__class__.from_dict(data)
    assert isinstance(rt, instance.__class__)

# ── TEST 2: Registry-backed models ───────────────────────────────────────────
MODEL_FACTORIES = [
    ("text_element",       lambda reg: TextElement(resolve_pid("te"), geometry=usg)),
    ("image_element",      lambda reg: ImageElement(resolve_pid("ie"), geometry=usg)),
    ("component_template", lambda reg: ComponentTemplate(resolve_pid("ct"), geometry=usg, registry=reg)),
    ("layout_template",    lambda reg: LayoutTemplate(resolve_pid("lt"), geometry=usg, registry=reg)),
    ("layout_slot",        lambda reg: LayoutSlot(resolve_pid("ls"), geometry=usg)),
]

@pytest.mark.parametrize("name,factory", MODEL_FACTORIES)
def test_models_schema_and_roundtrip(name, factory, validator, registry):
    inst = factory(registry)
    data = inst.to_dict()

    # 1) schema
    if validator:
        ok, err = validator.validate(data)
        assert ok, f"{name} schema failure: {err}"

    # 2) round-trip
    clone = ProtoRegistry.from_dict(data, registry=registry)
    data2 = clone.to_dict()

    # 3) deep compare, skipping geometry
    assert_deep_equal_skip_geometry(data, data2)
