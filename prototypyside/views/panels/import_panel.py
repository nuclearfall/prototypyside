from pathlib import Path
from typing import Any, Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush

from prototypyside.models.component_template import ComponentTemplate
# If you also want to support LayoutTemplate, you can import it and treat similarly.



class ImportPanel(QWidget):
    """
    Displays CSV import/merge status for the selected component template.
    Reacts to template changes, element edits, and MergeManager events.
    """
    def __init__(self, merge_manager, parent=None):
        super().__init__(parent)
        self.merge_manager = merge_manager
        self._current_template: Optional[Any] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.label = QLabel("CSV Import Sources", self)
        self.csv_list = QListWidget(self)
        self.csv_list.setMaximumHeight(100)

        self.fields_label = QLabel("Field Bindings", self)
        self.fields_list = QListWidget(self)

        layout.addWidget(self.label)
        layout.addWidget(self.csv_list)
        layout.addWidget(self.fields_label)
        layout.addWidget(self.fields_list)
        layout.addStretch(1)

        # Refresh when the manager loads/clears/updates CSV
        # self.merge_manager.csv_loaded.connect(self._on_merge_event)
        # self.merge_manager.csv_updated.connect(self._on_merge_event)
        # FIX: Connect to the now-existing csv_cleared signal
        # self.merge_manager.csv_cleared.connect(self._on_merge_event)

    # --- Public API ----------------------------------------------------------

    def set_template(self, template):
        self._current_template = template
        self.update_for_template(template)

    def update_for_template(self, template):
        if not template or not isinstance(template, ComponentTemplate):
            self.csv_list.clear()
            self.fields_list.clear()
            self.csv_list.addItem("No template selected")
            return

        # No need for unwrap_component_template if we pass the correct object
        real = template 

        self.csv_list.clear()
        self.fields_list.clear()
        
        # Use the new, correct method to get data
        data = self.merge_manager.from_component(template)
        
        if data:
            self.csv_list.addItem(Path(getattr(data, "path", "")).name)
            
            # The validation logic is now centralized in CSVData
            validation = compare_template_bindings(real)
            
            # Sort the items for a consistent display order
            sorted_items = sorted(validation.items())

            for el_name, status in sorted_items:
                self._add_field_row(el_name, status)
        else:
            self.csv_list.addItem("No CSV loaded")
            # Show missing elements from the template even if no CSV is loaded
            # print(template.items)
            if template.items != []:
                at_elements = [el.name for el in template.items if el.name.startswith("@")]
                for el_name in sorted(at_elements):
                    self._add_field_row(el_name, "missing")

    # --- Helpers -------------------------------------------------------------

    def _add_field_row(self, label: str, status: str) -> None:
        # Add icons as requested
        icon_map = {
            "BOTH": "✔️",
            "TEMPLATE": "⚠️",
            "CSV": "❌"
        }
        icon = icon_map.get(status, "")
        
        text = f"{icon} {label}" # Prepend icon to the text
        item = QListWidgetItem(text)

        if status == "ok":
            item.setForeground(QColor(20, 150, 20)) # Green
        elif status == "warn":
            item.setForeground(QColor(200, 120, 0)) # Yellow/Orange
        elif status == "missing":
            item.setForeground(QColor(180, 20, 20)) # Red
            
        self.fields_list.addItem(item)

    def _connect_template_signals(self) -> None:
        """Listen to template/item changes so the panel stays current."""
        t = self._current_template
        if not isinstance(t, ComponentTemplate):
            return

        # If your template emits a change signal, hook it
        if hasattr(t, "template_changed"):
            try:
                t.template_changed.connect(self._on_template_changed)
            except (TypeError, RuntimeError):
                pass

        # Listen to item-level changes (rename, add/remove, etc.)
        for item in getattr(t, "items", []):
            if hasattr(item, "item_changed"):
                try:
                    item.item_changed.connect(self._on_template_changed)
                except (TypeError, RuntimeError):
                    pass

    def _disconnect_template_signals(self) -> None:
        t = self._current_template
        if not t:
            return

        if hasattr(t, "template_changed"):
            try:
                t.template_changed.disconnect(self._on_template_changed)
            except (TypeError, RuntimeError):
                pass

        for item in getattr(t, "items", []):
            if hasattr(item, "item_changed"):
                try:
                    item.item_changed.disconnect(self._on_template_changed)
                except (TypeError, RuntimeError):
                    pass

    # --- Slots ---------------------------------------------------------------

    def _on_merge_event(self, *args) -> None:
        """
        Called when MergeManager reports CSV loaded/updated/cleared.
        Only rebuild if it concerns the current template (cheap anyway).
        """
        if self._current_template:
            self.update_for_template(self._current_template)

    def _on_template_changed(self) -> None:
        """Triggered when elements are added/removed/renamed on the template."""
        if self._current_template:
            # Reconnect to any new items and refresh the list
            # self._disconnect_template_signals()
            self._connect_template_signals()
            self.update_for_template(self._current_template)

    # --- (Optional) existing utilities --------------------------------------

    def update_csv_file_list(self) -> None:
        """If you keep this separate view, use manager’s store to show all sources."""
        self.csv_list.clear()
        seen = set()
        for entry in self.merge_manager.csv_data.values():
            if id(entry) in seen:
                continue
            seen.add(id(entry))
            label = Path(str(entry.path)).name
            if getattr(entry, "is_linked", False):
                label += f"  ⇐  {getattr(entry, 'tname', '')}"
            item = QListWidgetItem(label)
            if (getattr(entry, "is_linked", False)
                and self._current_template
                and getattr(self._current_template, "pid", None) == getattr(entry, "tpid", None)):
                item.setSelected(True)
                item.setBackground(QBrush(QColor(230, 230, 230)))
            self.csv_list.addItem(item)
