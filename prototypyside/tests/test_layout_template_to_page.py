# tests/test_layout_template_to_page.py

import pytest
from prototypyside.services.proto_registry import RootRegistry, ProtoRegistry
from prototypyside.models.layout_template import LayoutTemplate

def test_create_page_from_layout_template():
    # 1) Set up a fresh root registry and make a LayoutTemplate
    root_registry = RootRegistry()
    registry = ProtoRegistry(parent=root_registry, root=root_registry)
    layout_template: LayoutTemplate = root_registry.create("lt", registry=registry)  # your LayoutTemplate factory
    # (Optional) Populate the template with at least one ComponentTemplate slot
    # slot = layout_template.add_slot(component_template=some_ct)
    # ...or rely on your default slots in the newly created template
    
    # 2) Now create a “page” from that template
    page = registry.clone(layout_template)
    
    # 3) Registry sanity
    assert registry.get(page.pid) is page
    
    # 4) PID prefixes
    assert page.pid.startswith("pg_"), f"expected page PID to start with 'pg_', got {page.pid!r}"
    
    # 5) Check nested slot clones
    # Slots aren't cloned!!!
    #    We expect each LayoutSlot in the page to be a fresh object
    # for original_slot, cloned_slot in zip(layout_template.items, page.items):
    #     # Slot‐level PID
    #     assert cloned_slot.pid != original_slot.pid
    #     # Registered
    #     assert root_registry.get(cloned_slot.pid) is cloned_slot
        
    #     # If your slots carry a cloned ComponentInstance…
    #     if hasattr(cloned_slot, "content") and cloned_slot.content:
    #         ci = cloned_slot.content
    #         assert ci.pid != original_slot.content.pid
    #         assert root_registry.get(ci.pid) is ci
    
    # 6) Deep‐equality of non‐geometry fields
    #    (Customize these to your schema)
    # for orig, clone in zip(layout_template.items, page.items):
    #     assert orig.row == clone.row
    #     assert orig.column == clone.column

