from typing import Type, TYPE_CHECKING
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem
from PySide6.QtCore import Qt
from shiboken6 import isValid
from prototypyside.models.component_template import ComponentTemplate

class ImportPanel(QWidget):
    """
    Displays CSV import/merge status for the selected component template.
    Reacts to template changes and element edits (e.g., name changes).
    """
    def __init__(self, merge_manager, parent=None):
        super().__init__(parent)
        self.merge_manager = merge_manager
        self._current_template = None

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

    def refresh_ui_for_template(self, template):
        """
        Rebuilds the import panel UI for the given template.
        Updates the field bindings and CSV file indicators.
        """
        self.update_csv_file_list()
        self.update_fields(template)



    def update_for_template(self, template):
        """
        Update the panel to reflect a new ComponentTemplate.
        If the same template is already active, do nothing.
        """
        if template == self._current_template:
            return  # Already connected to this template

        # Disconnect from previous template if valid
        if self._current_template and isValid(self._current_template):
            try:
                self._current_template.template_changed.disconnect(self._on_template_changed)
            except (RuntimeError, TypeError):
                pass

        self._current_template = template

        if self._current_template and isValid(self._current_template):
            try:
                self._current_template.template_changed.connect(self._on_template_changed)
            except (RuntimeError, TypeError):
                pass

        self.refresh_ui_for_template(template)  # Custom method to update display



    def _disconnect_signals(self):
        """Disconnect signals from the previous template and its elements."""
        if self._current_template is None:
            return

        try:
            if hasattr(self._current_template, "template_changed"):
                self._current_template.template_changed.disconnect(self._on_template_changed)
        except TypeError:
            pass  # signal already disconnected

        for item in getattr(self._current_template, "items", []):
            try:
                if hasattr(item, "item_changed"):
                    item.item_changed.disconnect(self._on_template_changed)
            except TypeError:
                pass

        self._current_template = None

    def _on_template_changed(self):
        """Triggered when elements are added/removed to the template."""
        template = self._current_template
        if isinstance(template, ComponentTemplate):
            # Reconnect to any new items
            data = self.merge_manager.get(template.pid)
            for item in getattr(self._current_template, "items", []):
                if hasattr(item, "item_changed"):
                    item.item_changed.connect(self._on_template_changed)

            self.update_fields(self._current_template)

    def update_csv_file_list(self):
        self.csv_list.clear()
        for key, entry in self.merge_manager.csv_data.items():
            label = str(entry.path)
            if entry.is_linked:
                label += f"  ⇐  {entry.tname}"
            item = QListWidgetItem(label)

            # Highlight if linked to current template
            if (entry.is_linked and
                self._current_template and
                getattr(self._current_template, "pid", None) == entry.tpid):
                item.setSelected(True)
                item.setBackground(Qt.lightGray)

            self.csv_list.addItem(item)



    def update_fields(self, template):
        self.fields_list.clear()
        if not isinstance(template, ComponentTemplate):
            return
        entry = self.merge_manager.get(template.pid) or self.merge_manager.get(template.csv_path)

        if entry and entry.is_linked:
            field_status = entry.validate_headers(template)
            for field, status in field_status.items():
                if status == "ok":
                    label = f"{field} ✔️"
                elif status == "missing":
                    label = f"{field} ✖️"
                elif status == "warn":
                    label = f"{field} ⚠️"
                else:
                    label = f"{field}"
                self.fields_list.addItem(QListWidgetItem(label))
