"""Pagination‑related utility functions.

These helpers are deliberately *framework‑free*: they accept plain model
objects (LayoutTemplate, ComponentTemplate) and numbers; no Qt classes are
imported here.  They provide all the numerical data that PaginationManager
needs so its core algorithm can remain small and unit‑testable.

Assumptions
-----------
* The existing *Component* class has been renamed **Component**.
* Concrete subclasses are ``StaticComponent`` and ``DataMergeComponent``.
* Every *ComponentTemplate* exposes::

      pid: str
      csv_rows: list[dict]  # [] if no merge data (i.e. static component)
      copies: int | None    # Only meaningful for StaticComponent; default 1.

* ``LayoutTemplate`` provides::

      rows: int
      columns: int
      auto_fill: bool
      items: list[LayoutSlot]

  Every ``LayoutSlot`` exposes::

      content: Optional[ComponentTemplate]  # None ↔ empty item

These attributes already exist (or have been specified) in the uploaded
source files.  If a later refactor changes names, adapt the attribute look‑ups
below accordingly.
"""
from __future__ import annotations

from typing import List, Dict, Literal, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # only for type hints; no runtime dependency
    from layout_template import LayoutTemplate, LayoutSlot  # uploaded file
    from component_template import ComponentTemplate        # uploaded file

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
Mode = Literal["static", "merge"]


def get_component_mode(template: "ComponentTemplate") -> Mode:
    """Return ``"merge"`` when *any* CSV rows are defined, else ``"static"``."""
    rows = getattr(template, "csv_rows", None) or []
    return "merge" if rows else "static"


def get_required_instances(template: "ComponentTemplate") -> int:
    """Total instances that must be produced for *this* template.

    * **Merge** templates → one instance per CSV row.
    * **Static** templates → ``template.copies`` (defaults to 1).
    """
    mode = get_component_mode(template)
    if mode == "merge":
        return len(getattr(template, "csv_rows", []))

    # Static component: honour its copies attribute (default 1)
    return max(1, int(getattr(template, "copies", 1)))


def count_items(layout_template: "LayoutTemplate", template: "ComponentTemplate") -> int:
    """How many items on the *initial* page reference *template*?

    The result depends on *auto‑fill* semantics:
    * If the template appears at least once and ``auto_fill`` is **True**,
      every *empty* item is considered to reference this template as well.
    * Otherwise we simply count explicit matches.
    """
    # 1) explicit matches
    explicit_count = sum(1 for item in layout_template.items if item.content is template)

    if explicit_count == 0:
        return 0  # template not present on the layout at all

    if layout_template.auto_fill:
        total_cells = layout_template.rows * layout_template.columns
        filled_cells = len(layout_template.items)
        empty_cells = total_cells - filled_cells
        return explicit_count + empty_cells

    return explicit_count


def rows_for(template: "ComponentTemplate") -> List[Dict[str, str]]:
    """Return the list of *row dictionaries* driving instance generation.

    For *static* templates, we synthesise ``{}`` placeholders repeated
    ``copies`` times so PaginationManager can treat both modes uniformly.
    """
    mode = get_component_mode(template)
    if mode == "merge":
        return list(getattr(template, "csv_rows", []))  # defensive copy

    copies = get_required_instances(template)
    return [{} for _ in range(copies)]

# ---------------------------------------------------------------------------
# Convenience bulk extractor
# ---------------------------------------------------------------------------

def analyse_template(layout_template: "LayoutTemplate", template: "ComponentTemplate") -> Dict[str, int]:
    """Return a dict with pre‑computed numbers used in page count math."""
    return {
        "mode": get_component_mode(template),  # type: ignore[return-value]
        "required_instances": get_required_instances(template),
        "items_per_page": count_items(layout_template, template),
    }

__all__ = [
    "Mode",
    "get_component_mode",
    "get_required_instances",
    "count_items",
    "rows_for",
    "analyse_template",
]