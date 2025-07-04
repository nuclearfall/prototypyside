# merge_manager.py
from __future__ import annotations

"""MergeManager

Responsibilities
================
1. Parse and cache CSV rows **per ComponentTemplate**.
2. Validate bindings: every `@field` in the template must exist in the CSV;
   extra CSV columns raise only a *warning* (callable hook).
3. Hand out **ComponentInstance** objects on demand via `next_instance()` –
   cloning the template and applying the next row.
4. Provide `remaining()` so PaginationPolicy can test exhaustion.
5. Keep a *per-template cursor* so each dataset is consumed sequentially.

Assumptions
===========
* A ComponentTemplate exposes:
    - `pid` (str)
    - `elements` (list[dict]) where bound fields are expressed as
      `name = "@field"`.
    - `apply_data(row_dict)` -> ComponentInstance
* Static templates either have `csv_rows = []` attribute **or** the caller does
  not ask MergeManager for them (policy omits them from *datasets* mapping).
* A central `warning_handler(str)` can be injected – defaults to `print`.
"""

from typing import Dict, List, Optional, Callable, Any
import csv
from copy import deepcopy

# ---------------------------------------------------------------------------
# Forward stubs to avoid heavy imports – replace in real application context
# ---------------------------------------------------------------------------
ComponentTemplate = Any  # TODO: real class
ComponentInstance = Any  # TODO: real class
ProtoRegistry = Any      # TODO: real registry factory (if needed)


class MergeManager:  # pylint: disable=too-many-instance-attributes
    """One shared instance can serve *all* templates of a project."""

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    def __init__(
        self,
        csv_fp,  # file‑like object or path
        *,
        registry: Optional[ProtoRegistry] = None,
        warning_handler: Callable[[str], None] | None = None,
    ) -> None:
        self._registry = registry
        self._warn = warning_handler or (lambda msg: print(f"⚠️  {msg}"))

        # Global cache keyed by template.pid
        self._rows: Dict[str, List[dict[str, str]]] = {}
        self._cursor: Dict[str, int] = {}
        self._validated: Dict[str, bool] = {}

        # Raw CSV rows available to *every* template unless the template has
        # its own csv_rows attribute (acts as override).
        self._global_rows: List[dict[str, str]] = self._load_csv(csv_fp)

    # ------------------------------------------------------------------
    # CSV parsing
    # ------------------------------------------------------------------
    @staticmethod
    def _load_csv(csv_fp) -> List[dict[str, str]]:
        if isinstance(csv_fp, (str, bytes, bytearray)):
            f = open(csv_fp, "r", newline="", encoding="utf8")  # caller closes? fine for prototype.
        else:
            f = csv_fp  # file‑like
        reader = csv.DictReader(f)
        rows = list(reader)
        return rows

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _get_bound_fields(template: ComponentTemplate) -> set[str]:
        """Extract @bound field names from template elements."""
        return {
            elem["name"][1:]
            for elem in getattr(template, "elements", [])
            if isinstance(elem.get("name"), str) and elem["name"].startswith("@")
        }

    def _validate_template(self, template: ComponentTemplate) -> None:
        pid = template.pid
        if self._validated.get(pid):
            return  # already validated

        csv_headers = set(self._global_rows[0].keys()) if self._global_rows else set()
        required = self._get_bound_fields(template)
        missing = required - csv_headers
        unused = csv_headers - required

        if missing:
            raise ValueError(
                f"CSV is missing required columns for template {pid}: {sorted(missing)}"
            )
        if unused:
            self._warn(
                f"CSV contains unused columns for template {pid}: {sorted(unused)}"
            )
        self._validated[pid] = True

    # ------------------------------------------------------------------
    # Registration / row cache
    # ------------------------------------------------------------------
    def _ensure_registered(self, template: ComponentTemplate) -> None:
        pid = template.pid
        if pid in self._rows:
            return

        # Prefer template‑specific rows if present, else global CSV
        rows = deepcopy(getattr(template, "csv_rows", None)) or deepcopy(self._global_rows)
        self._rows[pid] = rows
        self._cursor[pid] = 0
        self._validate_template(template)

    # ------------------------------------------------------------------
    # Public API expected by PaginationPolicy
    # ------------------------------------------------------------------
    def remaining(self, template: ComponentTemplate) -> int:
        self._ensure_registered(template)
        pid = template.pid
        return len(self._rows[pid]) - self._cursor[pid]

    # Convenience alias for policies
    def total_rows(self, template: ComponentTemplate) -> int:  # noqa: D401
        self._ensure_registered(template)
        return len(self._rows[template.pid])

    def next_row(self, template: ComponentTemplate) -> Optional[dict[str, str]]:
        self._ensure_registered(template)
        pid = template.pid
        idx = self._cursor[pid]
        if idx >= len(self._rows[pid]):
            return None
        row = self._rows[pid][idx]
        self._cursor[pid] += 1
        return row

    # ------------------------------------------------------------------
    # New API: next_instance()
    # ------------------------------------------------------------------
    def next_instance(self, template: ComponentTemplate) -> Optional[ComponentInstance]:
        """Return a *new* ComponentInstance with next data row applied.

        If registry is provided we defer creation to it; otherwise we call
        template.apply_data(row).
        """
        row = self.next_row(template)
        if row is None:
            return None

        if self._registry is not None:
            # Registry is responsible for PID issuance / cloning
            return self._registry.create("ci", template=template, row=row)

        # Fallback: template handles cloning+merge itself
        return template.apply_data(row)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Reset util – helpful for regenerate/undo
    # ------------------------------------------------------------------
    def reset(self, template: ComponentTemplate | None = None) -> None:
        """Reset cursor(s) so pagination can be regenerated."""
        if template is None:
            for pid in self._cursor:
                self._cursor[pid] = 0
        else:
            self._ensure_registered(template)
            self._cursor[template.pid] = 0
