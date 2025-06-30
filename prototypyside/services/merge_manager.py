# merge_manager.py
from __future__ import annotations
from typing import Dict, List, Any, Optional

class MergeManager:
    """
    Hands-out CSV rows *on demand* for each DataMergeComponent.

    It stores a cursor per component PID so successive calls to
    `next_row()` return rows in sequence without duplication.

    StaticComponent templates are simply ignored: they should
    never be passed to this manager.
    """

    def __init__(self, layout, csvfile) -> None:
        self._layout = layout
        self._rows = self.layout.rows
        self._columns = self.layout._columns
        self._csv_fp = csv_fp
        reader = csv.DictReader(csvfile)
        self.headers = reader.fieldnames  # This is a list of the headers
        for row in reader:
            print(row)
            self._rows: Dict[str, List[dict]] = {}     # pid → full list of rows
            self._cursor: Dict[str, int] = {}          # pid → next row index


    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #
    def _ensure_registered(self, template) -> None:
        """Lazily cache the CSV rows for `template` the first time we see it."""
        pid = template.pid
        if pid not in self._rows:
            rows = getattr(template, "csv_rows", None) or []  # empty → static
            self._rows[pid] = rows
            self._cursor[pid] = 0

    # --------------------------------------------------------------------- #
    # Public API expected by PaginationManager
    # --------------------------------------------------------------------- #
    def rows(self, template) -> List[dict]:
        """Return *all* CSV rows for this template (does not move the cursor)."""
        self._ensure_registered(template)
        return self._rows[template.pid]

    def remaining(self, template) -> int:
        """How many rows are still unconsumed?"""
        self._ensure_registered(template)
        pid = template.pid
        return len(self._rows[pid]) - self._cursor[pid]

    def next_row(self, template) -> Optional[dict]:
        """
        Pop the next CSV row, or `None` if the template is exhausted.
        Cursor is advanced only when a row is returned.
        """
        self._ensure_registered(template)
        pid = template.pid
        idx = self._cursor[pid]
        if idx >= len(self._rows[pid]):
            return None                     # no more data
        row = self._rows[pid][idx]
        self._cursor[pid] += 1
        return row

    def reset(self, template) -> None:
        """Rewind the cursor so pagination can be regenerated from scratch."""
        self._ensure_registered(template)
        self._cursor[template.pid] = 0
