from __future__ import annotations

"""Pagination policy abstractions for LayoutApplication.

Step 1 introduced the core interface **PaginationPolicy** and the baseline
implementation **InterleaveDatasets**.  
Step 2 adds a **factory / registry** so that the rest of the application can
request a policy by name (string) and the chosen policy type can be persisted
inside `LayoutTemplate` JSON.

The module therefore now contains:

1. `PaginationPolicy` (ABC)
2. `InterleaveDatasets` – row‑major round‑robin policy
3. `PaginationPolicyFactory` – global registry with `register()`, `get()`,
   `default()` helpers, and automatic registration of built‑ins.

Future policies (ClusterByDataset, StaticFirstRow, …) can be placed in their own
modules or right here – they only need to call
`PaginationPolicyFactory.register("PolicyName", PolicyClass)`.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Forward declarations / light aliases. These should be replaced with real
# imports once the full application package is available inside this context.
# ---------------------------------------------------------------------------
ComponentInstance = Any  # TODO: replace with real class
LayoutTemplate = Any     # TODO: replace with real class
LayoutSlot = Any         # TODO: replace with real class
MergeManager = Any       # TODO: replace with real class

# When placed on a page, a slot may remain empty (None).
Placement = Tuple["LayoutSlot", Optional["ComponentInstance"]]

# =============================================================================
# Abstract base class
# =============================================================================

class PaginationPolicy(ABC):
    """Common interface for all pagination strategies."""

    # ---------------------------------------------------------------------
    # Lifecycle
    # ---------------------------------------------------------------------
    @abstractmethod
    def prepare(self, layout: LayoutTemplate, datasets: Dict[str, MergeManager]) -> None: ...

    @abstractmethod
    def next_page(self) -> Optional[List[Placement]]: ...


# =============================================================================
# Factory / registry
# =============================================================================

class PaginationPolicyFactory:
    """Global registry mapping *policy name* → *policy class*.

    The factory enables three things:
    1.  Loose coupling: PaginationManager & GUI request policies by string.
    2.  Persistence: LayoutTemplate stores the selected policy name & params.
    3.  Extensibility: plugins can register additional strategies at runtime.
    """

    _registry: Dict[str, type[PaginationPolicy]] = {}

    # ---------------------------------------------
    # Registration API
    # ---------------------------------------------
    @classmethod
    def register(cls, name: str, policy_cls: type[PaginationPolicy]) -> None:
        if not issubclass(policy_cls, PaginationPolicy):
            raise TypeError("policy_cls must inherit from PaginationPolicy")
        cls._registry[name] = policy_cls

    # ---------------------------------------------
    # Retrieval helpers
    # ---------------------------------------------
    @classmethod
    def get(cls, name: str, **kwargs) -> PaginationPolicy:
        try:
            policy_cls = cls._registry[name]
        except KeyError as exc:
            raise ValueError(f"Unknown pagination policy '{name}'. Registered: {list(cls._registry)}") from exc
        return policy_cls(**kwargs)

    @classmethod
    def default(cls) -> PaginationPolicy:
        """Return a default policy instance (InterleaveDatasets)."""
        return cls.get("InterleaveDatasets")

# =============================================================================
# Concrete policy 0 – InterleaveDatasets (round‑robin)
# =============================================================================

class InterleaveDatasets(PaginationPolicy):
    """Round‑robin distribution across datasets (existing behaviour)."""

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def __init__(self, stride: int = 1):
        self._stride = max(1, stride)
        self._layout: LayoutTemplate | None = None
        self._datasets: Dict[str, MergeManager] | None = None
        self._page_index: int = 0
        self._slots: List[LayoutSlot] = []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _flatten_slots(self) -> List[LayoutSlot]:
        assert self._layout is not None
        return [slot for row in self._layout.slots for slot in row]

    # ------------------------------------------------------------------
    # PaginationPolicy implementation
    # ------------------------------------------------------------------
    def prepare(self, layout: LayoutTemplate, datasets: Dict[str, MergeManager]) -> None:  # noqa: D401
        self._layout = layout
        self._datasets = datasets
        self._page_index = 0
        self._slots = self._flatten_slots()

    def next_page(self) -> Optional[List[Placement]]:  # noqa: D401
        if self._layout is None or self._datasets is None:
            raise RuntimeError("InterleaveDatasets.prepare() has not been called")

        placements: List[Placement] = []
        any_data_left = False

        offset = (self._page_index * self._stride) % len(self._slots)

        for i in range(len(self._slots)):
            slot = self._slots[(offset + i) % len(self._slots)]
            template = slot.template  # type: ignore[attr-defined]
            mgr: MergeManager | None = self._datasets.get(template.pid)

            if mgr is None:
                instance: Optional[ComponentInstance] = getattr(template, "_static_instance", None)
            else:
                if mgr.remaining(template) > 0:
                    any_data_left = True
                    instance = mgr.next_instance(template)
                else:
                    instance = None
            placements.append((slot, instance))

        if not any_data_left:
            return None

        self._page_index += 1
        return placements

# ---------------------------------------------------------------------------
PaginationPolicyFactory.register("InterleaveDatasets", InterleaveDatasets)

# =============================================================================
# Concrete policy 1 – TileOversizeComponent (poster / folding board)
# =============================================================================

class TileOversizeComponent(PaginationPolicy):
    """Slice a single oversized ComponentTemplate into page‑sized tiles.

    *Assumptions*
    -------------
    * The LayoutTemplate contains **exactly one** `LayoutSlot` that already
      references the *oversized* `ComponentTemplate` (CT).
    * CT's pixel dimensions exceed the page size of the LayoutTemplate.
    * A params‐dict is supplied on factory construction:
        ``{ "bleed": 6, "overlap": 0, "order": "row-major" }``
      – All values are optional; defaults as below.
    * `ComponentTemplate.apply_data()` exists but will typically receive an
      **empty dict** (static poster/board).  If the CT is data‑bound the policy
      simply repeats the first available row for every tile.

    *Bleed* (px) – extra margin added around each tile so that no white hairline
    shows after trimming.  
    *Overlap* (px) – additional shared area between adjacent tiles (for glue).
    """

    DEFAULT_PARAMS = {"bleed": 0, "overlap": 0, "order": "row-major"}

    # ------------------------------------------------------------------
    def __init__(self, **params):
        self.params = {**self.DEFAULT_PARAMS, **params}
        self._tiles: List[Placement] = []  # pre‑computed list of all pages
        self._cursor: int = 0

    # ------------------------------------------------------------------
    # PaginationPolicy interface
    # ------------------------------------------------------------------
    def prepare(self, layout: LayoutTemplate, datasets: Dict[str, MergeManager]):
        # 1. Validate layout
        if len(layout.slots) != 1 or len(layout.slots[0]) != 1:
            raise ValueError("TileOversizeComponent requires exactly one slot in LayoutTemplate")
        slot = layout.slots[0][0]
        template = slot.template  # type: ignore[attr-defined]
        if template is None:
            raise ValueError("Slot does not reference a ComponentTemplate")

        page_w = getattr(layout, "page_width_px", None) or layout.width_px  # type: ignore[attr-defined]
        page_h = getattr(layout, "page_height_px", None) or layout.height_px  # type: ignore[attr-defined]
        comp_w = getattr(template, "width_px", None) or template.width  # type: ignore[attr-defined]
        comp_h = getattr(template, "height_px", None) or template.height  # type: ignore[attr-defined]

        # 2. Determine tiling grid
        from math import ceil
        cols = ceil(comp_w / page_w)
        rows = ceil(comp_h / page_h)

        bleed = float(self.params["bleed"])
        overlap = float(self.params["overlap"])

        # 3. Precompute ComponentInstances for each tile
        merge_mgr = datasets.get(template.pid)  # may be None (static)
        row_data = merge_mgr.next_row(template) if merge_mgr else {}
        if row_data is None:
            row_data = {}

        # The slot is reused on every page; renderer will use instance.viewport
        for r in range(rows):
            for c in range(cols):
                left = max(c * page_w - overlap, 0)
                top = max(r * page_h - overlap, 0)
                right = min(left + page_w + bleed, comp_w)
                bottom = min(top + page_h + bleed, comp_h)
                viewport = {
                    "x": left,
                    "y": top,
                    "w": right - left,
                    "h": bottom - top,
                }
                instance = template.apply_data(row_data)  # type: ignore[attr-defined]
                # Attach viewport meta so renderer can clip
                setattr(instance, "viewport", viewport)

                self._tiles.append((slot, instance))

        # Optional order: column-major or snake could be implemented later
        if self.params["order"] == "column-major":
            self._tiles.sort(key=lambda tpl: (tpl[1].viewport["x"], tpl[1].viewport["y"]))  # type: ignore[attr-defined]

    def next_page(self) -> Optional[List[Placement]]:  # noqa: D401
        if self._cursor >= len(self._tiles):
            return None
        page = [self._tiles[self._cursor]]
        self._cursor += 1
        return page

# ---------------------------------------------------------------------------
PaginationPolicyFactory.register("TileOversizeComponent", TileOversizeComponent)

# =============================================================================
# Concrete policy 2 – ClusterByDataset
# =============================================================================

class ClusterByDataset(PaginationPolicy):
    """Fill complete pages with a single dataset at a time.

    Order is the appearance order of templates in ``layout.slots`` unless a
    specific list is provided via params::

        {"order": ["CT_abcd", "CT_efgh", …]}
    """

    def __init__(self, **params):
        self.order: list[str] | None = params.get("order")
        self._layout: LayoutTemplate | None = None
        self._datasets: Dict[str, MergeManager] | None = None
        self._slots: list[LayoutSlot] = []
        self._current_idx: int = 0  # index in self.order

    # -------------------------- helpers ---------------------------------
    def _flatten_slots(self):
        assert self._layout is not None
        return [slot for row in self._layout.slots for slot in row]

    # ----------------------- PaginationPolicy ---------------------------
    def prepare(self, layout: LayoutTemplate, datasets: Dict[str, MergeManager]):
        self._layout = layout
        self._datasets = datasets
        self._slots = self._flatten_slots()

        # Default order = first appearance of each template
        if self.order is None:
            seen: set[str] = set()
            self.order = []
            for slot in self._slots:
                pid = slot.template.pid  # type: ignore[attr-defined]
                if pid not in seen and pid in datasets:
                    seen.add(pid)
                    self.order.append(pid)

    def next_page(self):
        if self._current_idx >= len(self.order):
            return None

        pid = self.order[self._current_idx]
        mgr = self._datasets[pid]
        # Template object (same for all slots referencing this pid)
        template = next(s.template for s in self._slots if s.template.pid == pid)  # type: ignore[attr-defined]

        # No more rows? advance pointer and recurse
        if mgr.remaining(template) == 0:
            self._current_idx += 1
            return self.next_page()

        placements: List[Placement] = []
        for slot in self._slots:
            if slot.template.pid == pid:  # type: ignore[attr-defined]
                instance = mgr.next_instance(template)
            else:
                instance = None
            placements.append((slot, instance))

        return placements

# ---------------------------------------------------------------------------
PaginationPolicyFactory.register("ClusterByDataset", ClusterByDataset)

# =============================================================================
# Concrete policy 3 – StaticFirstRow
# =============================================================================

class StaticFirstRow(PaginationPolicy):
    """Reserve the first *n* rows for a static template, fill the rest with data.

    Params::  {"static_rows": 1}

    *Static template* is auto‑detected: any ComponentTemplate that **lacks** a
    dataset entry in ``datasets`` is considered static.
    """

    DEFAULT_PARAMS = {"static_rows": 1}

    def __init__(self, **params):
        self.params = {**self.DEFAULT_PARAMS, **params}
        self._layout: LayoutTemplate | None = None
        self._datasets: Dict[str, MergeManager] | None = None
        self._slot_rows: list[list[LayoutSlot]] = []
        self._static_cache: Dict[str, ComponentInstance] = {}

    # ----------------------- PaginationPolicy ---------------------------
    def prepare(self, layout: LayoutTemplate, datasets: Dict[str, MergeManager]):
        self._layout = layout
        self._datasets = datasets
        self._slot_rows = layout.slots  # already 2‑D row structure

        # Cache first static instance per static template
        for row in self._slot_rows:
            for slot in row:
                tmpl = slot.template  # type: ignore[attr-defined]
                if tmpl.pid not in datasets:  # static
                    self._static_cache[tmpl.pid] = getattr(tmpl, "_static_instance", tmpl.apply_data({}))  # type: ignore[attr-defined]

    def next_page(self):
        if self._layout is None:
            return None

        any_data_left = False
        placements: List[Placement] = []
        n_static_rows = int(self.params["static_rows"])

        for row_idx, row in enumerate(self._slot_rows):
            for slot in row:
                tmpl = slot.template  # type: ignore[attr-defined]
                if row_idx < n_static_rows or tmpl.pid not in self._datasets:
                    instance = self._static_cache[tmpl.pid]
                else:
                    mgr = self._datasets[tmpl.pid]
                    if mgr.remaining(tmpl):
                        instance = mgr.next_instance(tmpl)
                        any_data_left = True
                    else:
                        instance = None
                placements.append((slot, instance))

        if not any_data_left and not placements:
            return None
        return placements

# ---------------------------------------------------------------------------
PaginationPolicyFactory.register("StaticFirstRow", StaticFirstRow)

# =============================================================================
# Concrete policy 4 – DuplexInterleave (front/back alignment)
# =============================================================================

class DuplexInterleave(PaginationPolicy):
    """Emit pages in front/back pairs aligned for duplex printing.

    Assumes *two* templates are present in the layout:
        • A *front* template (dataset‑bound)
        • A *back* template (static or dataset‑bound)

    Params:: {"back_pid": "CT_back", "flip": "long" | "short"}
    """

    def __init__(self, **params):
        self.back_pid: str | None = params.get("back_pid")
        self.flip: str = params.get("flip", "long")
        self._layout: LayoutTemplate | None = None
        self._datasets: Dict[str, MergeManager] | None = None
        self._slots: list[LayoutSlot] = []
        self._front_pid: str | None = None
        self._is_front_turn: bool = True

    def prepare(self, layout: LayoutTemplate, datasets: Dict[str, MergeManager]):
        self._layout = layout
        self._datasets = datasets
        self._slots = [slot for row in layout.slots for slot in row]

        # Detect front template = first dataset‑bound slot
        for slot in self._slots:
            if slot.template.pid in datasets:  # type: ignore[attr-defined]
                self._front_pid = slot.template.pid  # type: ignore[attr-defined]
                break
        if self._front_pid is None:
            raise ValueError("DuplexInterleave: could not detect front template")

        if self.back_pid is None:
            # Auto‑detect back = first static template encountered
            for slot in self._slots:
                pid = slot.template.pid  # type: ignore[attr-defined]
                if pid != self._front_pid:
                    self.back_pid = pid
                    break
        if self.back_pid is None:
            raise ValueError("DuplexInterleave: back template not specified/found")

    def _build_page_for_pid(self, pid: str) -> List[Placement]:
        placements: List[Placement] = []
        template = next(s.template for s in self._slots if s.template.pid == pid)  # type: ignore[attr-defined]
        mgr = self._datasets.get(pid)
        for slot in self._slots:
            if slot.template.pid == pid:  # type: ignore[attr-defined]
                if mgr and mgr.remaining(template):
                    instance = mgr.next_instance(template)
                else:
                    instance = getattr(template, "_static_instance", template.apply_data({}))  # type: ignore[attr-defined]
            else:
                instance = None
            placements.append((slot, instance))
        return placements

    def next_page(self):
        if self._layout is None:
            return None
        if self._is_front_turn:
            page = self._build_page_for_pid(self._front_pid)  # type: ignore[arg-type]
        else:
            page = self._build_page_for_pid(self.back_pid)  # type: ignore[arg-type]
        self._is_front_turn = not self._is_front_turn
        # Stop when fronts exhausted and we just output back
        if not self._is_front_turn and not any(inst for _, inst in page):
            return None
        return page

# ---------------------------------------------------------------------------
PaginationPolicyFactory.register("DuplexInterleave", DuplexInterleave)

# =============================================================================
# Concrete policy 5 – StaticCluster (tokens / currency sheets)
# =============================================================================

class StaticCluster(PaginationPolicy):
    """Cluster **static** templates first, then cycle through datasets.

    Use‑case: a designer wants to print a block of tokens (all static) followed
    by clustered decks (dataset‑bound) on subsequent pages.

    Params
    ------
    ``static_first`` (bool, default *True*)
        If ``False`` clusters datasets first, then static templates.

    ``order`` (list[str])
        Explicit PID ordering (static *and* dataset templates).  When supplied
        the policy follows this order exactly and ignores ``static_first``.
    """

    def __init__(self, **params):
        self.static_first: bool = params.get("static_first", True)
        self.explicit_order: list[str] | None = params.get("order")
        # Runtime state
        self._layout: LayoutTemplate | None = None
        self._datasets: Dict[str, MergeManager] | None = None
        self._slots: list[LayoutSlot] = []
        self._order: list[str] = []  # sequence of template pids
        self._remaining_static: Dict[str, int] = {}
        self._static_cache: Dict[str, ComponentInstance] = {}
        self._current_idx: int = 0

    # ----------------------- helpers ---------------------------
    def _flatten_slots(self):
        assert self._layout is not None
        return [slot for row in self._layout.slots for slot in row]

    # -------------------- PaginationPolicy ---------------------
    def prepare(self, layout: LayoutTemplate, datasets: Dict[str, MergeManager]):
        self._layout = layout
        self._datasets = datasets
        self._slots = self._flatten_slots()

        static_pids: list[str] = []
        dataset_pids: list[str] = []

        for slot in self._slots:
            pid = slot.template.pid  # type: ignore[attr-defined]
            if pid in datasets:
                if pid not in dataset_pids:
                    dataset_pids.append(pid)
            else:
                if pid not in static_pids:
                    static_pids.append(pid)
                    # Determine copies to print
                    tmpl = slot.template  # type: ignore[attr-defined]
                    copies = getattr(tmpl, "copies", 1)
                    self._remaining_static[pid] = int(copies)
                    # Cache first instance now
                    self._static_cache[pid] = getattr(tmpl, "_static_instance", tmpl.apply_data({}))  # type: ignore[attr-defined]

        if self.explicit_order:
            self._order = self.explicit_order
        else:
            self._order = (static_pids + dataset_pids) if self.static_first else (dataset_pids + static_pids)

    def _cluster_static_done(self, pid: str) -> bool:
        return self._remaining_static.get(pid, 0) <= 0

    def _cluster_data_done(self, pid: str) -> bool:
        if pid not in self._datasets:
            return True
        tmpl = next(s.template for s in self._slots if s.template.pid == pid)  # type: ignore[attr-defined]
        return self._datasets[pid].remaining(tmpl) == 0

    def _advance_cursor(self):
        # Skip finished clusters
        while self._current_idx < len(self._order):
            pid = self._order[self._current_idx]
            if (pid in self._datasets and not self._cluster_data_done(pid)) or (
                pid not in self._datasets and not self._cluster_static_done(pid)
            ):
                return  # found active cluster
            self._current_idx += 1

    def next_page(self):
        if self._layout is None:
            return None
        self._advance_cursor()
        if self._current_idx >= len(self._order):
            return None  # all clusters finished

        pid = self._order[self._current_idx]
        placements: List[Placement] = []
        tmpl = next(s.template for s in self._slots if s.template.pid == pid)  # type: ignore[attr-defined]

        if pid in self._datasets:  # dataset cluster
            mgr = self._datasets[pid]
            for slot in self._slots:
                if slot.template.pid == pid:  # type: ignore[attr-defined]
                    if mgr.remaining(tmpl):
                        inst = mgr.next_instance(tmpl)
                    else:
                        inst = None
                else:
                    inst = None
                placements.append((slot, inst))
        else:  # static cluster
            for slot in self._slots:
                if slot.template.pid == pid:  # type: ignore[attr-defined]
                    inst = self._static_cache[pid]
                else:
                    inst = None
                placements.append((slot, inst))
            # decrement copies by full page of that static template
            page_slots = sum(1 for s in self._slots if s.template.pid == pid)  # type: ignore[attr-defined]
            self._remaining_static[pid] -= page_slots

        # Check if cluster finished, move cursor
        if (pid in self._datasets and self._cluster_data_done(pid)) or (
            pid not in self._datasets and self._cluster_static_done(pid)
        ):
            self._current_idx += 1

        return placements

# ---------------------------------------------------------------------------
PaginationPolicyFactory.register("StaticCluster", StaticCluster)

# =============================================================================
# LayoutTemplate integration (specification)
# =============================================================================

# NOTE: Actual LayoutTemplate class lives in prototypyside.models.layout_template.
# Here is a **minimal patch sketch** that callers can adopt:
#
# class LayoutTemplate(…):
#     def __init__(…, pagination_policy: str | None = None, pagination_params: dict | None = None):
#         super().__init__(…)
#         self.pagination_policy = pagination_policy or "InterleaveDatasets"
#         self.pagination_params = pagination_params or {}
#
#     # -------------------------------------------------------------
#     # Serialization helpers
#     # -------------------------------------------------------------
#     def to_dict(self) -> dict:
#         data = …  # existing serialisation
#         data["paginationPolicy"] = {
#             "type": self.pagination_policy,
#             "params": self.pagination_params,
#         }
#         return data
#
#     @classmethod
#     def from_dict(cls, data: dict) -> "LayoutTemplate":
#         pol = data.get("paginationPolicy", {})
#         inst = cls(…, pagination_policy=pol.get("type"), pagination_params=pol.get("params", {}))
#         …  # hydrate other fields
#         return inst
#
# PaginationManager would then do:
#     policy = PaginationPolicyFactory.get(layout.pagination_policy, **layout.pagination_params)
#     policy.prepare(layout, datasets)
