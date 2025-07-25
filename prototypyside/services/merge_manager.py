# merge_manager.py

import csv
from pathlib import Path
from typing import List, Optional, Dict, Callable, Any, Type, TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from prototypyside.models.component_template import ComponentTemplate
 

class CSVData:
    """
    Holds one CSV’s rows and headers, plus the path as a Path.
    """
    def __init__(
        self,
        path: str, template: ComponentTemplate = None
    ):
        self.path: Path = Path(path)
        self.is_linked = False

        if template: 
            self.link_template(template)
        else:
            self.tpid = None
            self.tname = None
            self.rows: Optional[List[Dict[str, str]]]
        self.validate_csv()
    # self._clear_fn = self._default_clear

    def validate_csv(self):
        # load & validate if templat
        with self.path.open("r", newline="", encoding="utf8") as f:
            reader = csv.DictReader(f)
            self.headers = reader.fieldnames or []
            # if no @-fields, treat as empty
            if not any(h.startswith("@") for h in self.headers):
                self.rows = []
            else:
                self.rows = list(reader)
        self.count = len(self.rows)

    def link_template(self, template):
        template.csv_path = self.path
        self.tpid = template.pid
        self.tname = template.name
        self.is_linked = True

    # def _default_clear(self):
    #     """Reset all @-bound template items to empty string."""
    #     for item in getattr(self.template, "items", []):
    #         if getattr(item, "name", "").startswith("@"):
    #             item.content = ""

    def load(self, template=None):
        if template:
            self.tname = template.name
            self.tpid = template.pid
        self.validate_csv()
        return self.rows

    def validate_headers(self, template=None) -> Dict[str, str]:
        """
        Returns a map of @-field → status ("ok", "missing", "warn").
        """
        if hasattr(template, "csv_path"):
            self.link_template(template)
        rows = self.rows
        if not template or not self.rows:
            return {}

        element_keys = [e.name for e in template.items if e.name.startswith("@")]
        header_keys = list(rows[0].keys()) if rows else []

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
    _csv_data = {}

    def register(self, csv_path, template: ComponentTemplate = None):
        key = template.pid if hasattr(template, "pid") else csv_path
        self._csv_data[key] = CSVData(csv_path, template)

    def load_csv(self, csv_path: Optional[str], template: ComponentTemplate):
        if not hasattr(template, "csv_path"):
            raise TypeError(f"template must be a ComponentTemplate, not {template.__name__}.")
        if not csv_path and not template.csv_path:
            raise ValueError("No CSV path provided")
        csv_path = csv_path or template.csv_path
        data = self.get(template.pid) or self.get(csv_path)
        if not data:
            self.register(csv_path, template)
            data = self.get(template.pid)
        return data

    def validate_headers(self, template):
        if isinstance(template, ComponentTemplate):
            entry = self._csv_data.get(template.pid) or self._csv_data.get(template.csv_path)
            if entry:
                return entry.validate_headers(template)
        return {}

    def deregister(self, tpid):
        self._csv_data.pop(tpid)

    def get(self, key):
        return self._csv_data.get(key)