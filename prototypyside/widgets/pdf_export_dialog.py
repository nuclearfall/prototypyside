from PySide6.QtWidgets import QFileDialog, QVBoxLayout, QWidget, QLabel, QPushButton
from PySide6.QtCore import Qt
from .page_size_selector import PageSizeSelector

class PDFExportDialog(QFileDialog):
    def __init__(self, parent=None, default_filename="merged_output.pdf"):
        super().__init__(parent)

        self.setWindowTitle("Export to PDF")
        self.setAcceptMode(QFileDialog.AcceptSave)
        self.setNameFilter("PDF Files (*.pdf)")
        self.selectFile(default_filename)

        # Custom widget to embed
        custom_widget = QWidget()
        custom_layout = QVBoxLayout(custom_widget)
        custom_layout.setAlignment(Qt.AlignTop)

        label = QLabel("Select Page Size:")
        self.selector = PageSizeSelector()
        custom_layout.addWidget(label)
        custom_layout.addWidget(self.selector)

        self.setOption(QFileDialog.DontUseNativeDialog, True)
        layout = self.layout()

        # Inject custom widget into QFileDialog
        layout.addWidget(custom_widget, layout.rowCount(), 0, 1, layout.columnCount())

    def get_page_size(self):
        return self.selector.get_current_page_size()
