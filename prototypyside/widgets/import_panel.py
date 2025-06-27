# import_panel.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem
from PySide6.QtCore import Qt

class ImportPanel(QWidget):
    """
    Displays CSV import/merge status for the selected component template.
    Shows all @columns, checkmarks for bound, X for missing, warning for invalid data.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.label = QLabel("Import/CSV Fields", self)
        self.list_widget = QListWidget(self)
        layout.addWidget(self.label)
        layout.addWidget(self.list_widget)
        layout.addStretch(1)

    def update_fields(self, fields_status):
        """
        Expects a dict of {column_name: status} where status is "ok", "missing", "warn"
        """
        self.list_widget.clear()
        for field, status in fields_status.items():
            item = QListWidgetItem(field)
            if status == "ok":
                item.setText(f"{field} ✔️")
            elif status == "missing":
                item.setText(f"{field} ✖️")
            elif status == "warn":
                item.setText(f"{field} ⚠️")
            self.list_widget.addItem(item)
