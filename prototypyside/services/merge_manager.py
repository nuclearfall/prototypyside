from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, Iterable, List, Optional, Set, Tuple, Union, Any
import csv

from prototypyside.utils.valid_path import ValidPath


def _validate_path(path: Union[str, Path]) -> Path:
    """
    Validate a file path using ValidPath
    """
    return ValidPath.file(path, must_exist=True)

@dataclass
class CSVData:
    """
    Loads prevalidated CSV and exposes:
      - headers (all headers)
      - at_headers (only headers starting with '@')
      - generators / cursor-style iteration over @-keyed rows
      - a comparison helper against a template's '@name' items

    Row iteration yields ONLY the '@'-prefixed columns, per your spec:
        {"@foo": "...", "@bar": "..."}
    """
    path: Union[str, Path]

    # Populated on load
    headers: List[str] = field(init=False, default_factory=list)
    at_headers: List[str] = field(init=False, default_factory=list)
    _rows: List[Dict[str, str]] = field(init=False, default_factory=list)

    # Cursor for generator-like usage
    _idx: int = field(init=False, default=0)

    # Optional: remember a sniffed dialect name (debugging/telemetry)
    _dialect: Optional[str] = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.path = _validate_path(self.path)
        if not self.path:
            return None
        self._load_csv()

    # ---------------------------
    # Loading & validation
    # ---------------------------
    def _load_csv(self) -> None:
        """
        - Ensures file is valid CSV (via csv.Sniffer + DictReader)
        - Captures headers and rows
        - Derives `at_headers`
        """
        # Read a small sample for sniffer
        with self.path.open("r", newline="", encoding="utf-8-sig") as fh:
            sample = fh.read(4096)
        if not sample.strip():
            raise ValueError("CSV file is empty or whitespace only.")

        try:
            dialect = csv.Sniffer().sniff(sample)
            self._dialect = getattr(dialect, "_name", None)
        except Exception:
            # If sniff fails, fall back to excel dialect
            dialect = csv.excel

        # True parse
        with self.path.open("r", newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh, dialect=dialect)
            if not reader.fieldnames or any(h is None or str(h).strip() == "" for h in reader.fieldnames):
                raise ValueError("CSV has missing or empty header names.")
            # Collect headers
            self.headers = [str(h) for h in reader.fieldnames]
            # Collect rows now (prevalidated)
            self._rows = [ {k: (v if v is not None else "") for k, v in row.items()} for row in reader ]

        if not self._rows:
            # Valid CSV but no data rows
            self._rows = []

        # Compute @-headers
        self.at_headers = [h for h in self.headers if h.startswith("@")]

    # ---------------------------
    # Properties & basic info
    # ---------------------------
    @property
    def row_count(self) -> int:
        return len(self._rows)

    @property
    def remaining(self) -> int:
        return max(0, self.row_count - self._idx)

    def has_next(self) -> bool:
        return self._idx < self.row_count

    def reset(self) -> None:
        self._idx = 0

    # ---------------------------
    # Row access (ONLY @-columns)
    # ---------------------------
    def iter_rows(self) -> Iterator[Dict[str, str]]:
        """
        Iterator over rows restricted to @-prefixed headers.
        Does NOT mutate the internal cursor.
        """
        if not self.at_headers:
            # Spec: still a valid generator; it will just yield {} for each row
            for _ in self._rows:
                yield {}
            return

        for row in self._rows:
            yield {h: row.get(h, "") for h in self.at_headers}

    def next_row(self) -> Dict[str, str]:
        """
        Cursor-style 'next' over ONLY @-columns.
        Raises StopIteration when exhausted.
        """
        if not self.has_next():
            raise StopIteration("No remaining CSV rows.")
        row = self._rows[self._idx]
        self._idx += 1
        if not self.at_headers:
            return {}
        return {h: row.get(h, "") for h in self.at_headers}

    # ---------------------------
    # Full row access (if needed)
    # ---------------------------
    def iter_full_rows(self) -> Iterator[Dict[str, str]]:
        """Iterator over full CSV rows (all headers)."""
        for row in self._rows:
            yield dict(row)

    def next_full_row(self) -> Dict[str, str]:
        """Cursor-style 'next' over full rows (all headers)."""
        if not self.has_next():
            raise StopIteration("No remaining CSV rows.")
        row = dict(self._rows[self._idx])
        self._idx += 1
        return row

    # ---------------------------
    # Template comparison
    # ---------------------------
    def compare_template_bindings(self, template: Any) -> Dict[str, str]:
        """
        Scans `template` for items having a 'name' that starts with '@'
        and compares with CSV @-headers.

        Returns a dict mapping token -> {'ELEMENT'|'CSV'|'BOTH'}

        Example:
            {
              '@title': 'BOTH',
              '@subtitle': 'ELEMENT',
              '@author': 'CSV'
            }
        """
        element_tokens = self._collect_template_at_names(template)
        csv_tokens = set(self.at_headers)

        all_tokens = element_tokens | csv_tokens
        out: Dict[str, str] = {}

        for tok in sorted(all_tokens):
            in_element = tok in element_tokens
            in_csv = tok in csv_tokens
            out[tok] = "BOTH" if (in_element and in_csv) else ("ELEMENT" if in_element else "CSV")

        return out

    def _collect_template_at_names(self, template: Any) -> Set[str]:
        """
        Attempts to collect '@'-prefixed 'name' values from a template.
        Prefers 'items' but also considers 'elements' to fit your app.
        Does a shallow pass; can be extended to recurse if you nest.
        """
        tokens: Set[str] = set()

        def maybe_collect(obj: Any) -> None:
            # Single object with .name
            name = getattr(obj, "name", None)
            if isinstance(name, str) and name.startswith("@"):
                tokens.add(name)

        # Prefer 'items' (per your spec), then 'elements'
        iterables: List[Iterable[Any]] = []
        if hasattr(template, "items") and isinstance(getattr(template, "items"), Iterable):
            iterables.append(getattr(template, "items"))
        elif hasattr(template, "elements") and isinstance(getattr(template, "elements"), Iterable):
            iterables.append(getattr(template, "elements"))

        for it in iterables:
            for obj in it:
                maybe_collect(obj)

        # Also consider the template itself (some templates have their own 'name')
        maybe_collect(template)

        return tokens

# The merge manager should generally prefer to fail finding data silently.
class MergeManager:
    _map: Dict[str, CSVData] = {}

    def add_path(self, path: Path, pid: str = None):
        csv_data = CsvData(path)
        key = pid or str(path)

        if csv_data:
            self._map[key] = csv_data

    def from_component(self, comp: Component):
        key = comp.pid if comp.pid in self._map else comp.csv_path
        if key:
            return self._map.get(key, None)
        else:
            return None

    def load_next_page(self, page: LayoutTemplate):
        slot_content = [slot.content for slot in page.items]
        for sc in slot_content:
            csv_data = self.from_component(sc)
            if csv_data.has_next():
                sc.set_csv_content(csv_data.next_row())
            

# # merge_manager.py
# from __future__ import annotations

# from dataclasses import dataclass, field
# from pathlib import Path
# from typing import (Dict, Iterator, Iterable, List, Optional, Set, 
#         Tuple, Union, Any, TYPE_CHECKING)
# import csv

# from PySide6.QtCore import QObject, Signal

# from prototypyside.services.proto_class import ProtoClass

# if TYPE_CHECKING:
#     from prototypyside.models.component_template import ComponentTemplate
#     from prototypyside.models.layout_template import LayoutTemplate

# pc = ProtoClass

# # class CSVData:
# #     """
# #     Holds one CSV’s rows and headers, plus the path as a Path.
# #     """
# #     def __init__(self, path: str, template: ComponentTemplate):
# #         is_valid_path = ValidPath(path.)
# #         self.path = Path(path)
# #         self.is_linked = False
# #         self.template_pid = template.pid # Store pid for lookup
# #         self.rows = None

# #         self.link_template(template)
# #         self.validate_csv()

# #     def validate_csv(self):
# #         # load & validate if template
# #         with self.path.open("r", newline="", encoding="utf8") as f:
# #             reader = csv.DictReader(f)
# #             # Store only @-headers for validation purposes
# #             self.headers = [h for h in (reader.fieldnames or []) if h.startswith("@")]
            
# #             # if no @-fields, treat as empty
# #             if not self.headers:
# #                 self.rows = []
# #             else:
# #                 # Reload the file to read the rows now that we have headers
# #                 f.seek(0) 
# #                 reader = csv.DictReader(f)
# #                 self.rows = list(reader)
# #         self.iter_rows = iter(self.rows)
# #         self.count = len(self.rows)

# #     def link_template(self, template: ComponentTemplate):
# #         self.tpid = template.pid
# #         self.tname = template.name
# #         self.is_linked = True

# #     def validate_headers(self, template: ComponentTemplate) -> Dict[str, str]:
# #         """
# #         Returns a map of @-field → status ("ok", "missing", "warn").
# #         """
# #         # Get element names from the provided template that start with '@'
# #         element_keys = {e.name for e in template.items if e.name.startswith("@")}
        
# #         # CSV headers that start with '@'
# #         header_keys = set(self.headers)

# #         result: Dict[str, str] = {}
# #         all_keys = element_keys | header_keys

# #         for key in all_keys:
# #             is_in_template = key in element_keys
# #             is_in_csv = key in header_keys

# #             if is_in_template and is_in_csv:
# #                 result[key] = "ok"      # Found in both
# #             elif is_in_template and not is_in_csv:
# #                 result[key] = "missing" # In template, but not in CSV
# #             else: # not is_in_template and is_in_csv
# #                 result[key] = "warn"    # In CSV, but not in template
        
# #         return result

# #     def next_row():


# class MergeManager(QObject): # Must inherit from QObject to have signals
#     """
#     Manages loading CSVData objects and handing out row-dicts on demand.
#     """
#     csv_loaded = Signal()
#     csv_unloaded = Signal()
#     csv_updated = Signal()
#     csv_cleared = Signal() # Added for consistency

#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self._csv_data: Dict[str, CSVData] = {}

#     def deregister(self, tpid):
#         if tpid in self._csv_data:
#             self._csv_data.pop(tpid)
#             self.csv_cleared.emit() # Emit the cleared signal

#     def load_csv(self, csv_path: Path | str, template: ComponentTemplate):
#         if isinstance(template, ComponentTemplate):
#             # Connect the template's signal to our handler
#             template.item_name_change.connect(self._on_template_item_name_changed)
            
#             # Create the CSVData object
#             csv_data_obj = CSVData(csv_path, template)
#             self._csv_data[template.pid] = csv_data_obj
            
#             # Set the path on the template itself
#             template.csv_path = csv_path
            
#             self.csv_loaded.emit()
#             return csv_data_obj # Return the object for immediate use if needed
#         return None

#     def has_csv(self, tpid):
#         return self.get("tpid", False)

#     def get_csv_data_for_template(self, template: ComponentTemplate) -> Optional[CSVData]:
#         """Retrieves CSVData associated with a given template PID."""
#         if not template:
#             return None
#         return self._csv_data.get(template.pid)

#     def _on_template_item_name_changed(self):
#         """
#         Slot to react to an element name changing on a template.
#         This triggers re-validation and notifies the UI.
#         """
#         # The sender() is the ComponentTemplate whose element name changed.
#         sender_template = self.sender()
#         if isinstance(sender_template, ComponentTemplate):
#             # Re-validate and emit the update signal
#             self.validate_and_emit(sender_template)

#     def validate_and_emit(self, template: ComponentTemplate):
#         """Forces validation for a template's CSV and emits an update signal."""
#         data = self.get_csv_data_for_template(template)
#         if data:
#             data.validate_headers(template) # This recalculates the status
#             self.csv_updated.emit() # Notify the ImportPanel 
    
