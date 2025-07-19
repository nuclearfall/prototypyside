# widget_helpers.py
from PySide6.QtWidgets import QWidget, QVBoxLayout

def wrap_with_vbox(*widgets, stretch=True, margins=(0, 0, 0, 0)) -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(*margins)
    for w in widgets:
        if isinstance(w, tuple):  # widget with alignment
            layout.addWidget(w[0], alignment=w[1])
        else:
            layout.addWidget(w)
    if stretch:
        layout.addStretch(1)
    return container