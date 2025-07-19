# pagination_manager.py

from __future__ import annotations

"""Refactored PaginationManager

This version delegates *all* item‑to‑instance decisions to a
``PaginationPolicy`` obtained from ``PaginationPolicyFactory`` rather than
containing pagination heuristics inline.  The manager is therefore much
shorter and focused on orchestration:

* Build the *datasets* mapping required by the policy.
* Ask the policy for each successive page.
* Cache the resulting page matrix so callers can access pages lazily or via
  eager ``generate()``.

The previous re‑balancing / item‑template mapping logic has been removed – that
complexity now resides inside the concrete policy class (``InterleaveDatasets``
by default).
"""

from typing import Iterable, List, Optional, Tuple, Dict, Any

# ──────────────────────────────────────────────────────────────────────────────
# Forward declarations / light aliases (replace with real imports in app)
# ──────────────────────────────────────────────────────────────────────────────
# LayoutTemplate = Any     # TODO: real class
# LayoutSlot = Any         # TODO: real class
# ComponentInstance = Any  # TODO: real class
# MergeManager = Any       # TODO: real class
# ProtoRegistry = Any      # TODO: real class (factory for ComponentInstance)

from .pagination_policy import PaginationPolicyFactory, Placement, PaginationPolicy  # type: ignore


class PaginationError(RuntimeError):
    """Raised when the layout template cannot be paginated (e.g., no items)."""


class PaginationManager:
    """Paginate a *single‑page* ``LayoutTemplate`` into multiple print pages.

    After refactor, the manager is a *thin cache* around a chosen
    ``PaginationPolicy``.  Page generation is delegated to the policy.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def __init__(
        self,
        layout_template: "LayoutTemplate",
        registry: "ProtoRegistry",
        merge_manager: Optional["MergeManager"] = None,
    ) -> None:
        self.layout_template = layout_template
        self.registry = registry
        self.merge_manager = merge_manager

        # Page list where each page is list[Placement]
        self._pages: List[List[Placement]] = []
        self._generated: bool = False

        # The chosen policy instance
        self._policy: PaginationPolicy | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate(self) -> None:
        """Generate all pages eagerly (blocking)."""
        self._ensure_policy_prepared()
        while not self._generated:
            self._build_next_page()

    def page_count(self) -> int:
        self._ensure_at_least_one_page()
        return len(self._pages)

    __len__ = page_count  # len(pm)

    def get_page(self, index: int):
        self._ensure_pages(index + 1)
        return self._pages[index]

    def iter_pages(self) -> Iterable[List[Placement]]:
        idx = 0
        while True:
            if not self._ensure_pages(idx + 1):
                break
            yield self._pages[idx]
            idx += 1

    # ------------------------------------------------------------------
    # Internal helpers – policy prep & dataset mapping
    # ------------------------------------------------------------------
    def _ensure_policy_prepared(self) -> None:
        if self._policy is not None:
            return  # already prepared

        if not getattr(self.layout_template, "items", None):
            raise PaginationError("LayoutTemplate has no LayoutSlots")

        # Build datasets mapping.  Current assumption: a *single* MergeManager
        # handles all ComponentTemplates that require data rows, keyed by
        # template.pid.  Static templates will simply not appear in the map.
        datasets: Dict[str, MergeManager] = {}
        if self.merge_manager is not None:
            unique_templates = {
                item.template  # type: ignore[attr-defined]
                for row in self.layout_template.items  # type: ignore[attr-defined]
                for item in row
                if item.template is not None  # type: ignore[attr-defined]
            }
            for tmpl in unique_templates:
                # Heuristic: template has data rows if merge_manager.remaining() > 0
                if self.merge_manager.remaining(tmpl) > 0:
                    datasets[tmpl.pid] = self.merge_manager

        # Instantiate policy from factory (Step 2 integration)
        policy_name = getattr(self.layout_template, "pagination_policy", "InterleaveDatasets")
        params = getattr(self.layout_template, "pagination_params", {}) or {}
        self._policy = PaginationPolicyFactory.get(policy_name, **params)
        self._policy.prepare(self.layout_template, datasets)

    # ------------------------------------------------------------------
    # Page building helpers
    # ------------------------------------------------------------------
    def _ensure_pages(self, n: int) -> bool:
        """Build pages until at least *n* exist. Returns False when finished."""
        self._ensure_policy_prepared()
        while len(self._pages) < n and not self._generated:
            self._build_next_page()
        return len(self._pages) >= n

    def _ensure_at_least_one_page(self) -> None:
        self._ensure_pages(1)

    def _build_next_page(self):
        """Ask policy for the next page and cache it."""
        assert self._policy is not None  # prepared already
        placements = self._policy.next_page()
        if placements is None:
            self._generated = True
            return
        self._pages.append(placements)
