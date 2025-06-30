import pytest

# ------------------------------------------------------------
# Minimal stub models so tests run standalone without PySide.
# ------------------------------------------------------------

class DummyComponent:
    """Trivial placeholder returned by the registry."""
    def __init__(self, pid, template, row):
        self.pid = pid
        self.template = template
        self.row = row

class DummyRegistry:
    """Bare‑bones factory that mimics registry.create()."""
    _counter = 0

    def create(self, prefix, **kwargs):
        DummyRegistry._counter += 1
        pid = f"{prefix}_{DummyRegistry._counter}"
        return DummyComponent(pid, kwargs.get("template"), kwargs.get("row"))

class DummyLayoutSlot:
    def __init__(self, content=None):
        self.content = content

class DummyComponentTemplate:
    def __init__(self, pid, csv_rows=None, copies=None):
        self.pid = pid
        self.csv_rows = csv_rows or []      # list[dict] for DataMerge
        self.copies = copies                # int for StaticComponent

class DummyLayoutTemplate:
    def __init__(self, slots):
        self.layout_slots = slots

# ------------------------------------------------------------
# Bring in the helpers and PaginationManager under test
# ------------------------------------------------------------
from prototypyside.utils.pagination_helpers import get_component_mode, get_required_instances, count_slots
from prototypyside.services.pagination_manager import PaginationManager
from prototypyside.services.merge_manager import MergeManager

# ------------------------------------------------------------
# Test helpers behaviour
# ------------------------------------------------------------

def test_helper_modes_and_counts():
    static_t = DummyComponentTemplate("ct_static", copies=3)
    merge_t = DummyComponentTemplate("ct_merge", csv_rows=[{"id": i} for i in range(5)])

    mm = MergeManager()

    assert get_component_mode(static_t) == "static"
    assert get_component_mode(merge_t) == "merge"

    assert get_required_instances(static_t, mm) == 3
    assert get_required_instances(merge_t, mm) == 5

    # simple 1×2 template
    lt = DummyLayoutTemplate([DummyLayoutSlot(static_t), DummyLayoutSlot(merge_t)])
    assert count_slots(lt, static_t) == 1
    assert count_slots(lt, merge_t) == 1

# ------------------------------------------------------------
# Pagination scenarios
# ------------------------------------------------------------

def build_grid(rows, cols, template):
    """Utility to build a grid of LayoutSlots all referencing the same template."""
    return DummyLayoutTemplate([DummyLayoutSlot(template) for _ in range(rows * cols)])

@pytest.mark.parametrize("copies, expected_pages", [(3, 1), (12, 2)])
def test_static_component_pagination(copies, expected_pages):
    """Single static component replicated across a 3×3 page grid."""
    static_t = DummyComponentTemplate("ct_static", copies=copies)
    lt = build_grid(3, 3, static_t)

    pm = PaginationManager(lt, DummyRegistry(), MergeManager())
    pm.generate()

    assert len(pm) == expected_pages


def test_merge_component_45_rows():
    """45 data rows, 9 slots per page ⇒ 5 pages."""
    rows = [{"id": i} for i in range(45)]
    merge_t = DummyComponentTemplate("ct_merge", csv_rows=rows)
    lt = build_grid(3, 3, merge_t)

    mm = MergeManager()
    pm = PaginationManager(lt, DummyRegistry(), mm)
    pm.generate()

    assert len(pm) == 5
    # All pages but the last should be full
    for page in pm.iter_pages():
        filled = [comp for _slot, comp in page if comp]
        if page is not pm.get_page(len(pm)-1):
            assert len(filled) == 9


def test_mixed_rebalancing_example():
    """4 A (12 rows), 2 B (20 rows), 3 C static ⇒ 6 pages after re‑balancing."""
    a_rows = [{"a": i} for i in range(12)]
    b_rows = [{"b": i} for i in range(20)]

    tA = DummyComponentTemplate("ct_A", csv_rows=a_rows)
    tB = DummyComponentTemplate("ct_B", csv_rows=b_rows)
    tC = DummyComponentTemplate("ct_C", copies=999)  # effectively unlimited static

    slots = [DummyLayoutSlot(tA)] * 4 + [DummyLayoutSlot(tB)] * 2 + [DummyLayoutSlot(tC)] * 3
    lt = DummyLayoutTemplate(slots)

    pm = PaginationManager(lt, DummyRegistry(), MergeManager())
    pm.generate()

    assert len(pm) == 6
    # Ensure that by the end no merge rows remain
    mm = pm.merge_manager
    assert mm.remaining(tA) == 0
    assert mm.remaining(tB) == 0
