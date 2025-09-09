from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, Iterable, List, Optional, Set, Union, Any
import csv

from prototypyside.utils.valid_path import ValidPath
from prototypyside.services.proto_class import ProtoClass

pc = ProtoClass

def _validate_path(path: Union[str, Path]) -> Path:
    return ValidPath.file(path, must_exist=True)


@dataclass
class CSVData:
    path: Union[str, Path]

    headers: List[str] = field(init=False, default_factory=list)
    at_headers: List[str] = field(init=False, default_factory=list)
    _rows: List[Dict[str, str]] = field(init=False, default_factory=list)
    _idx: int = field(init=False, default=0)
    _dialect: Optional[str] = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.path = _validate_path(self.path)
        self._load_csv()

    # ---------------------------
    # Loading & validation
    # ---------------------------
    def _load_csv(self) -> None:
        with self.path.open("r", newline="", encoding="utf-8-sig") as fh:
            sample = fh.read(4096)
        if not sample.strip():
            raise ValueError("CSV file is empty or whitespace only.")

        try:
            dialect = csv.Sniffer().sniff(sample)
            # csv.Sniffer dialects don't always expose a public name; keep for debugging if present
            self._dialect = getattr(dialect, "_name", None)
        except Exception:
            dialect = csv.excel

        with self.path.open("r", newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh, dialect=dialect)
            if not reader.fieldnames or any(h is None or str(h).strip() == "" for h in reader.fieldnames):
                raise ValueError("CSV has missing or empty header names.")
            self.headers = [str(h) for h in reader.fieldnames]
            self._rows = [{k: (v if v is not None else "") for k, v in row.items()} for row in reader]

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
        if not self.at_headers:
            for _ in self._rows:
                yield {}
            return
        for row in self._rows:
            yield {h: row.get(h, "") for h in self.at_headers}

    def next_row(self) -> Dict[str, str]:
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
        for row in self._rows:
            yield dict(row)

    def next_full_row(self) -> Dict[str, str]:
        if not self.has_next():
            raise StopIteration("No remaining CSV rows.")
        row = dict(self._rows[self._idx])
        self._idx += 1
        return row

    # ---------------------------
    # Template comparison
    # ---------------------------
    def compare_template_bindings(self, template: Any) -> Dict[str, str]:
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
        tokens: Set[str] = set()

        def maybe_collect(obj: Any) -> None:
            name = getattr(obj, "name", None)
            if isinstance(name, str) and name.startswith("@"):
                tokens.add(name)

        iterables: List[Iterable[Any]] = []
        if hasattr(template, "items") and isinstance(getattr(template, "items"), Iterable):
            iterables.append(getattr(template, "items"))
        elif hasattr(template, "elements") and isinstance(getattr(template, "elements"), Iterable):
            iterables.append(getattr(template, "elements"))

        for it in iterables:
            for obj in it:
                maybe_collect(obj)

        maybe_collect(template)
        return tokens


class MergeManager:
    """
    Lookups by PID (preferred) or by str(csv_path).
    Fails silently when sources are missing or exhausted.
    """
    _map: Dict[str, CSVData] = {}

    def add_path(self, path: Union[str, Path], pid: Optional[str] = None) -> None:
        try:
            csv_data = CSVData(path)
        except Exception:
            # Fail silently per policy
            return
        key = pid or str(Path(path))
        self._map[key] = csv_data

    def from_component(self, comp: Any) -> Optional[CSVData]:
        # Prefer PID if present and registered
        pid = getattr(comp, "pid", None)
        if pid and pid in self._map:
            return self._map[pid]

        # Fallback to csv_path → normalize to str(Path)
        csv_path = getattr(comp, "csv_path", None)
        if csv_path:
            key = str(Path(csv_path))
            return self._map.get(key)

        return None

    def load_next_page(self, page: Any) -> None:
        """
        Assumes `page.items` is an iterable of slots.
        Each slot is expected to have `.content` (component/instance)
        and the content is expected to implement `set_csv_content(dict)`.
        Fails silently per policy.
        """

        if not hasattr(page, "items") or not getattr(page, "items"):
            raise ValueError(f"Page has no slots. Page is of type {type(page)} it must be a LayoutTemplate")

        for slot in page.items:
            sc = getattr(slot, "content", None)
            if not pc.isproto(sc, pc.CC):
                continue
            csv_data = self.from_component(sc)
            if not csv_data:
                continue
            if not csv_data.has_next():
                continue
            row = csv_data.next_row()  # only @-cols by design

            if hasattr(sc, "set_csv_content") and callable(sc.set_csv_content):
                sc.set_csv_content(row)

