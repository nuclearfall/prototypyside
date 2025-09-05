# clone_policy.py
from enum import Enum, auto
class ClonePolicy(Enum):
    LIVE_MOUNT = auto()            # no clones, reparent in GUI
    SNAPSHOT_UNREGISTERED = auto() # clones with register=False
    SNAPSHOT_EXPORT_REG = auto()   # clones into provided export registry

def snapshot(self, template, page_index: int,
             policy: ClonePolicy,
             export_registry=None):
    # compute Page (angle, slot angles) as discussed
    if policy is ClonePolicy.LIVE_MOUNT:
        # return (Page, live_root_item) after reparenting under a PageRootItem
    elif policy is ClonePolicy.SNAPSHOT_UNREGISTERED:
        clone_lt = self._registry.clone(template, register=False)
        # build a cloned scene tree rooted at `cloned_root` (no registry usage)
        return page, cloned_root
    elif policy is ClonePolicy.SNAPSHOT_EXPORT_REG:
        assert export_registry is not None
        clone_lt = export_registry.clone(template, register=True)
        # build a cloned scene tree rooted at `cloned_root` using export_registry
        return page, cloned_root, export_registry