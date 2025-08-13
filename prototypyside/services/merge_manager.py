# merge_manager.py

import csv
from pathlib import Path
from typing import List, Optional, Dict, Callable, Any, Type, TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from prototypyside.models.component_template import ComponentTemplate
from prototypyside.models.layout_template import LayoutTemplate
from prototypyside.utils.proto_helpers import resolve_pid


class CSVData:
    """
    Holds one CSV’s rows and headers, plus the path as a Path.
    """
    def __init__(self, path: str, template: ComponentTemplate):
        self.path = Path(path)
        self.is_linked = False
        self.template_pid = template.pid # Store pid for lookup
        self.link_template(template)
        self.validate_csv()

    def validate_csv(self):
        # load & validate if template
        with self.path.open("r", newline="", encoding="utf8") as f:
            reader = csv.DictReader(f)
            # Store only @-headers for validation purposes
            self.headers = [h for h in (reader.fieldnames or []) if h.startswith("@")]
            
            # if no @-fields, treat as empty
            if not self.headers:
                self.rows = []
            else:
                # Reload the file to read the rows now that we have headers
                f.seek(0) 
                reader = csv.DictReader(f)
                self.rows = list(reader)

        self.count = len(self.rows)

    def link_template(self, template: ComponentTemplate):
        self.tpid = template.pid
        self.tname = template.name
        self.is_linked = True

    def validate_headers(self, template: ComponentTemplate) -> Dict[str, str]:
        """
        Returns a map of @-field → status ("ok", "missing", "warn").
        """
        # Get element names from the provided template that start with '@'
        element_keys = {e.name for e in template.items if e.name.startswith("@")}
        
        # CSV headers that start with '@'
        header_keys = set(self.headers)

        result: Dict[str, str] = {}
        all_keys = element_keys | header_keys

        for key in all_keys:
            is_in_template = key in element_keys
            is_in_csv = key in header_keys

            if is_in_template and is_in_csv:
                result[key] = "ok"      # Found in both
            elif is_in_template and not is_in_csv:
                result[key] = "missing" # In template, but not in CSV
            else: # not is_in_template and is_in_csv
                result[key] = "warn"    # In CSV, but not in template
        
        return result


class MergeManager(QObject): # Must inherit from QObject to have signals
    """
    Manages loading CSVData objects and handing out row-dicts on demand.
    """
    csv_loaded = Signal()
    csv_unloaded = Signal()
    csv_updated = Signal()
    csv_cleared = Signal() # Added for consistency

    def __init__(self, parent=None):
        super().__init__(parent)
        self._csv_data: Dict[str, CSVData] = {}

    def deregister(self, tpid):
        if tpid in self._csv_data:
            self._csv_data.pop(tpid)
            self.csv_cleared.emit() # Emit the cleared signal

    def load_csv(self, csv_path: str, template: ComponentTemplate):
        if isinstance(template, ComponentTemplate):
            # Connect the template's signal to our handler
            template.item_name_change.connect(self._on_template_item_name_changed)
            
            # Create the CSVData object
            csv_data_obj = CSVData(csv_path, template)
            self._csv_data[template.pid] = csv_data_obj
            
            # Set the path on the template itself
            template.csv_path = csv_path
            
            self.csv_loaded.emit()
            return csv_data_obj # Return the object for immediate use if needed
        return None

    def get_csv_data_for_template(self, template: ComponentTemplate) -> Optional[CSVData]:
        """Retrieves CSVData associated with a given template PID."""
        if not template:
            return None
        return self._csv_data.get(template.pid)

    def _on_template_item_name_changed(self):
        """
        Slot to react to an element name changing on a template.
        This triggers re-validation and notifies the UI.
        """
        # The sender() is the ComponentTemplate whose element name changed.
        sender_template = self.sender()
        if isinstance(sender_template, ComponentTemplate):
            # Re-validate and emit the update signal
            self.validate_and_emit(sender_template)

    def validate_and_emit(self, template: ComponentTemplate):
        """Forces validation for a template's CSV and emits an update signal."""
        data = self.get_csv_data_for_template(template)
        if data:
            data.validate_headers(template) # This recalculates the status
            self.csv_updated.emit() # Notify the ImportPanel 
    
