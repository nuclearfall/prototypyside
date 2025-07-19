# merge_manager.py

import csv
from pathlib import Path
from typing import List, Optional, Dict, Callable, Any

from prototypyside.models.component_template import ComponentTemplate

class CSVData:
    """
    Holds one CSV’s rows and headers, plus the file_path as a Path.
    """
    def __init__(
        self,
        file_path: str,
        template: ComponentTemplate,
        clear_fn: Optional[Callable[[], None]] = None
    ):
        self.file_path: Path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        self.template = template
        # This is the reference point for access by clones:
        self.tpid = template.tpid
        if self.tpid is None:
            self.tpid = template.pid
        self.headers: List[str]
        self.rows: Optional[List[Dict[str, str]]]
        self._clear_fn    = clear_fn or self._default_clear

        # load & validate immediately
        with self.file_path.open("r", newline="", encoding="utf8") as f:
            reader = csv.DictReader(f)
            self.headers = reader.fieldnames or []
            # if no @-fields, treat as empty
            if not any(h.startswith("@") for h in self.headers):
                self.rows = []
            else:
                self.rows = list(reader)

    def _default_clear(self):
        """Reset all @-bound template items to empty string."""
        for item in getattr(self.template, "items", []):
            if getattr(item, "name", "").startswith("@"):
                item.content = ""

    def validate_headers(self) -> Dict[str, str]:
        """
        Returns a map of @-field → status ("ok", "missing", "warn").
        """
        element_keys = [e.name for e in self.template.items if e.name.startswith("@")]
        header_keys  = [h for h in self.headers if h.startswith("@")]
        result: Dict[str, str] = {}
        for key in set(element_keys) | set(header_keys):
            if key in element_keys and key in header_keys:
                result[key] = "ok"
            elif key in element_keys:
                result[key] = "missing"
            else:
                result[key] = "warn"
        return result


class MergeManager:
    """
    Manages loading CSVData objects and handing out row-dicts on demand.
    """

    def __init__(self, warning_handler: Optional[Callable[[str], None]] = None):
        # map template.pid → CSVData
        self._csv_data: Dict[str, CSVData] = {}
        self._warning  = warning_handler or print


    def load_csv(self, csv_path: str, template: ComponentTemplate) -> CSVData:
        """
        Read the CSV into a CSVData instance, cache it, and return it.
        """
        data = CSVData(csv_path, template)
        # Data is linked to the root Component Template not the clones
        # store so we can look up both rows *and* file_path later
        self._csv_data[data.tpid] = data
        # let caller inspect data.rows and data.headers
        return data

    def validate_headers(self, tpid) -> Dict[str, str]:
        data = self._csv_data.get(tpid)
        return data.validate_headers() if data else {}

    def get_all_rows(self, tpid) -> List[Dict[str, str]]:
        """
        Return a fresh list of dicts for this template’s CSV,
        as loaded into CSVData.rows.
        """
        data = self._csv_data.get(tpid)
        if not data or data.rows is None:
            return []
        return list(data.rows)
