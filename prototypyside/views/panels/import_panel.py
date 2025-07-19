
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem
from PySide6.QtCore import Qt


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

    def update_for_template(self, template):
        """
        Update field and file views for the new template,
        and connect to its change signals.
        """
        # Disconnect previous listeners
        self._disconnect_signals()

        self._current_template = template
        self.update_csv_file_list(template)
        self.update_fields(template)

        # Listen for refresh notifications from the template
        if hasattr(template, "template_refresh"):
            template.template_refresh.connect(self._on_template_refresh)

    def _disconnect_signals(self):
        """Disconnect signals from the previous template and its elements."""
        if self._current_template is None:
            return

        try:
            if hasattr(self._current_template, "template_refresh"):
                self._current_template.template_refresh.disconnect(self._on_template_refresh)
        except TypeError:
            pass  # signal already disconnected

        self._current_template = None

    def _on_template_refresh(self, _pid:str):
        """Triggered when the template or one of its elements changes."""
        self.update_fields(self._current_template)

    def update_csv_file_list(self, selected_template):
        self.csv_list.clear()
        current_pid = selected_template.pid

        for pid, data in self.merge_manager._csv_data.items():
            # data is now CSVData, so data.file_path is a Path
            file_name = data.file_path.name
            item = QListWidgetItem(f"{file_name} ({pid})")
            if pid == current_pid:
                item.setSelected(True)
                item.setBackground(Qt.lightGray)
            self.csv_list.addItem(item)


    def update_fields(self, template):
        self.fields_list.clear()
        data = self.merge_manager._csv_data.get(template.pid)
        if not data:
            return

        field_status = data.validate_headers()
        for field, status in field_status.items():
            if status == "ok":
                label = f"{field} ✔️"
            elif status == "missing":
                label = f"{field} ✖️"
            elif status == "warn":
                label = f"{field} ⚠️"
            else:
                label = f"{field} ?"
            self.fields_list.addItem(QListWidgetItem(label))
