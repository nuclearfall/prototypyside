# tests/test_clone_hierarchy.py

import pytest
from prototypyside.services.proto_registry import RootRegistry, ProtoRegistry

def collect_items(root):
    """
    Recursively collect all QGraphicsObject children of `root`.
    """
    items = list(root.childItems())
    for child in list(items):
        items.extend(collect_items(child))
    return items

def test_clone_preserves_hierarchy_without_sharing():
    root = RootRegistry()
    registry = ProtoRegistry(parent=root, root=root)
    
    # 1) Create an original template (with nested slots/components)
    original = registry.create('ct')              # a ComponentTemplate
    # (…you may need to add some nested children here, e.g. slot = original.add_slot(...))
    
    # 2) Clone it
    clone = registry.clone(original)
    
    # 3) Collect all graphics‐scene items
    orig_items = collect_items(original)
    clone_items = collect_items(clone)
    
    # 4) Ensure no original QGraphicsObject made it into the clone tree
    for item in orig_items:
        assert item not in clone_items, (
            f"Found original item {item} in clone hierarchy!"
        )
    
    # 5) Ensure every clone child’s parent is the clone (not the original)
    for child in clone_items:
        assert child.parentItem() is not original, (
            f"{child} still points at old parent!"
        )
        # If you know the direct container (e.g. clone.slots_group), you can also:
        # assert child.parentItem() in collect_items(clone), (
        #     f"{child.parentItem()} isn’t under {clone}"
        # )
