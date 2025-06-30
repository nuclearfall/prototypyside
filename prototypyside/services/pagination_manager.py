"""pagination_manager.py

Core algorithm that converts a **single‑page LayoutTemplate** into an
ordered collection of pages, each page being a list of Component objects
(or ``None`` when a slot stays blank).

Assumptions & terminology
-------------------------
* ``Component`` is the renamed *Component* base‑class.
  * ``StaticComponent`` – has no CSV; may specify ``copies`` (>0 means it
    should appear that many times overall across the document).
  * ``DataMergeComponent`` – one per CSV row.
* The caller provides a **MergeManager** that exposes ``rows``,
  ``remaining``, ``next_row``, and ``reset``.
* The ``LayoutTemplate`` handed in is already in its *final state* —
  auto‑fill has taken place and every ``LayoutSlot`` either has a
  ``content`` reference to a ComponentTemplate or is intentionally left
  empty.  PaginationManager never mutates the template itself; it keeps
  its own per‑slot mapping and reassigns those mappings when templates
  finish (re‑balancing).

Public API
----------
>>> pm = PaginationManager(layout_template, registry, merge_manager)
>>> pm.generate()
>>> len(pm)          # page count
5
>>> for page in pm.iter_pages():
...     render(page)  # where page is list[(LayoutSlot, Component|None)]

The manager is *lazy*; pages are built incrementally the first time they
are requested, but a full upfront ``generate()`` is also provided for
callers that prefer it.
"""

from __future__ import annotations

from math import ceil
from typing import Dict, List, Optional, Tuple, Generator, Iterable, Any

from prototypyside.utils.pagination_helpers import (
    get_component_mode,
    get_required_instances,
    count_slots,
)

# TYPE_CHECKING guard to avoid heavy Qt imports during runtime of pure unit tests
from typing import TYPE_CHECKING
if TYPE_CHECKING:  # pragma: no cover
    from prototypyside.models.layout_template import LayoutTemplate, LayoutSlot
    from prototypyside.models.component_template import ComponentTemplate
    from prototypyside.services.merge_manager import MergeManager
    from prototypyside.services.proto_registry import ProtoRegistry
    from prototypyside.models.component import Component

class PaginationError(RuntimeError):
    """Raised when the layout template cannot be paginated (e.g., no slots)."""


class PaginationManager:
    """Paginate a *single‑page* LayoutTemplate into multiple print pages."""

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        layout_template: "LayoutTemplate",
        registry: "AppRegistry",
        merge_manager: Optional["MergeManager"] = None,
    ) -> None:
        self.layout_template = layout_template
        self.registry = registry
        self.merge_manager = merge_manager

        # page_matrix: list[ page ] where page == list[ (slot, Component|None) ]
        self._page_matrix: List[List[Tuple["LayoutSlot", Optional["Component"]]]] = []

        # Cached mapping of slot index → ComponentTemplate (dynamic, changes on rebalance)
        self._slot_templates: List[Optional["ComponentTemplate"]] = []

        # How many *instances still needed* for each template.
        self._remaining: Dict["ComponentTemplate", int] = {}

        # For static templates we reuse the same Component object (render cache)
        self._static_cache: Dict["ComponentTemplate", "Component"] = {}

        # Guard flag to prevent double generation
        self._generated: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> None:
        """Generate the entire pagination up‑front (eager mode)."""
        while not self._generated:
            self._build_next_page()

    def page_count(self) -> int:
        self._ensure_at_least_one_page()
        return len(self._page_matrix)

    __len__ = page_count  # len(pm)

    def get_page(self, index: int):
        self._ensure_pages(index + 1)
        return self._page_matrix[index]

    def iter_pages(self) -> Iterable[List[Tuple["LayoutSlot", Optional["Component"]]]]:
        page_idx = 0
        while True:
            if not self._ensure_pages(page_idx + 1):
                break
            yield self._page_matrix[page_idx]
            page_idx += 1

    # ------------------------------------------------------------------
    # Internal helpers – initialisation
    # ------------------------------------------------------------------

    def _lazy_init(self) -> None:
        """Populate slot‑template mapping and per‑template counters once."""
        if self._slot_templates:
            return  # already done

        slots = getattr(self.layout_template, "layout_slots", [])
        if not slots:
            raise PaginationError("LayoutTemplate has no LayoutSlots")

        # Fill _slot_templates with each slot's component template (or None)
        self._slot_templates = [getattr(s, "content", None) for s in slots]

        # Compute remaining counts for every template referenced in the layout
        for ct in {t for t in self._slot_templates if t is not None}:
            required = get_required_instances(ct, self.merge_manager)
            self._remaining[ct] = required

        # Algorithms assume at least one template has work
        if all(r == 0 for r in self._remaining.values()):
            raise PaginationError("Nothing to paginate: all components have zero instances required")

    # ------------------------------------------------------------------
    # Internal helpers – pagination loop
    # ------------------------------------------------------------------

    def _ensure_pages(self, n_pages: int) -> bool:
        """Build pages until *at least* ``n_pages`` exist.

        Returns True if page(s) were produced; False if pagination is done.
        """
        self._lazy_init()
        while len(self._page_matrix) < n_pages and not self._generated:
            self._build_next_page()
        return len(self._page_matrix) >= n_pages

    def _build_next_page(self) -> None:
        """Create the next page (if any templates still have remaining rows)."""
        # Quick exit condition: if all templates are exhausted we flag generated
        if all(rem == 0 for rem in self._remaining.values()):
            self._generated = True
            return

        page: List[Tuple["LayoutSlot", Optional["Component"]]] = []
        slots = getattr(self.layout_template, "layout_slots", [])

        # 1. Fill slots for this page
        for idx, slot in enumerate(slots):
            template = self._slot_templates[idx]
            comp: Optional["Component"] = None

            if template is not None and self._remaining.get(template, 0) > 0:
                mode = get_component_mode(template)
                if mode == "merge":
                    row_dict = self.merge_manager.next_row(template) if self.merge_manager else None
                    comp = self._create_component(template, row_dict)
                else:  # static
                    comp = self._static_cache.get(template)
                    if comp is None:
                        comp = self._create_component(template, {})
                        self._static_cache[template] = comp

                # decrement remaining counter
                self._remaining[template] -= 1

            page.append((slot, comp))

        self._page_matrix.append(page)

        # 2. Re‑balance slot assignments for next page
        self._rebalance_slot_templates()

    # ------------------------------------------------------------------
    # Component creation helpers
    # ------------------------------------------------------------------

    def _create_component(self, template: "ComponentTemplate", row: Optional[Dict[str, Any]]):
        """Factory method → Component (Static or DataMerge)."""
        # Determine subclass prefix
        mode = get_component_mode(template)
        prefix = "sc" if mode == "static" else "dc"  # example prefixes
        if row is None:
            row = {}
        # Registry handles PID issuance & construction logic internally
        return self.registry.create(prefix, template=template, row=row)

    # ------------------------------------------------------------------
    # Re‑balancing logic (after each page)
    # ------------------------------------------------------------------

    def _rebalance_slot_templates(self) -> None:
        """Reassign slots whose templates are finished, according to rules."""
        # Identify finished templates that still occupy any slots
        finished_templates = {ct for ct, rem in self._remaining.items() if rem == 0}
        if not finished_templates:
            return  # nothing to rebalance

        # Collect candidate templates to receive more slots
        merge_candidates = {ct for ct, rem in self._remaining.items() if rem > 0 and get_component_mode(ct) == "merge"}
        static_candidates = {ct for ct, rem in self._remaining.items() if rem > 0 and get_component_mode(ct) == "static"}

        # Helper to pick the template with *most* remaining rows
        def pick_best(cands: set["ComponentTemplate"]) -> Optional["ComponentTemplate"]:
            if not cands:
                return None
            return max(cands, key=lambda ct: self._remaining[ct])

        for idx, template in enumerate(self._slot_templates):
            if template in finished_templates:
                # Decide new assignment
                new_template = pick_best(merge_candidates)
                if new_template is None:
                    new_template = pick_best(static_candidates)
                # Could still be None (no data left); slot becomes blank
                self._slot_templates[idx] = new_template

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _ensure_at_least_one_page(self):
        self._ensure_pages(1)

