# prototypyside/views/layers_panel.py

from PySide6.QtWidgets import QListWidget, QListWidgetItem, QAbstractItemView
from PySide6.QtCore import Qt, Signal, QPoint, QModelIndex
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from prototypyside.models.component_element import ComponentElement


class LayersListWidget(QListWidget):
    # Existing signal: still emitted when a single item is (solely) selected
    item_selected_in_list = Signal(object)

    # Existing signal: notify that a Z-order change was requested/completed
    # (item, direction). For full reorders we emit (None, 0).
    item_z_changed_requested = Signal(object, int)

    # NEW: emitted on any selection change (multi-select friendly)
    items_selected_in_list = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Allow drag-reorder inside the list
        self.setDragDropMode(QListWidget.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)

        # Enable multi-selection (Shift for ranges, Ctrl/Cmd for toggles)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # Hook up selection and DnD signals
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.model().rowsMoved.connect(self._on_rows_moved)

        # Optional: nicer UX — select row on single click anywhere on it
        self.setSelectionBehavior(QAbstractItemView.SelectItems)

        self._drag_start_pos: Optional[QPoint] = None

    # ---------- Public API ----------

    def update_list(self, items: List['ComponentElement']) -> None:
        """
        Rebuild the list from the given items (top-most first).
        Preserves selection according to each element's isSelected() state.
        """
        self.blockSignals(True)
        try:
            self.clear()

            # Highest Z first (top of stack at index 0)
            sorted_items = sorted(items, key=lambda e: e.zValue(), reverse=True)

            # Build rows and reflect current selection state from the scene
            for elem in sorted_items:
                row = QListWidgetItem(elem.name or "(unnamed)")
                row.setData(Qt.UserRole, elem)
                self.addItem(row)

                # Keep the name in sync
                # (lambda default arg binds 'row' at definition time)
                elem.nameChanged.connect(lambda name, item=row: item.setText(name))

                if getattr(elem, "isSelected", None) and elem.isSelected():
                    row.setSelected(True)

        finally:
            self.blockSignals(False)
            # Emit selection state now that signals are unblocked
            self._on_selection_changed()

    def sync_from_scene_selection(self, selected_items: List['ComponentElement']) -> None:
        """
        Optional helper: call this when the scene selection changes externally
        to mirror it in the layers list.
        """
        sel_set = set(selected_items)
        self.blockSignals(True)
        try:
            for i in range(self.count()):
                item = self.item(i)
                elem = item.data(Qt.UserRole)
                item.setSelected(elem in sel_set)
        finally:
            self.blockSignals(False)
            self._on_selection_changed()

    # ---------- Internal: selection handling ----------

    def _on_selection_changed(self) -> None:
        """
        Emit both single- and multi-select signals as appropriate.
        """
        selected_elems: List['ComponentElement'] = []
        for i in range(self.count()):
            item = self.item(i)
            if item.isSelected():
                elem = item.data(Qt.UserRole)
                if elem:
                    selected_elems.append(elem)

        # Multi-select friendly signal
        self.items_selected_in_list.emit(selected_elems)

        # Back-compat: if exactly one, emit the original single-item signal
        if len(selected_elems) == 1:
            self.item_selected_in_list.emit(selected_elems[0])

    # ---------- Internal: drag/drop reordering ----------

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat('application/x-qabstractitemmodeldatalist'):
            event.accept()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasFormat('application/x-qabstractitemmodeldatalist'):
            super().dropEvent(event)  # triggers rowsMoved -> _on_rows_moved
        else:
            super().dropEvent(event)

    def _on_rows_moved(
        self,
        parent: QModelIndex,
        start: int,
        end: int,
        destination: QModelIndex,
        row: int,
    ) -> None:
        """
        When the user reorders rows, reassign Z-values so that index 0 is topmost.
        We use a spacing 'step' to preserve room for in-between inserts later.
        """
        # Gather elements in their new visual order (top-most at index 0)
        reordered: List['ComponentElement'] = []
        for i in range(self.count()):
            elem = self.item(i).data(Qt.UserRole)
            if elem:
                reordered.append(elem)

        # Assign distinct Z-values: first item gets highest Z
        step = 100.0
        base = 0.0
        count = len(reordered)
        # Highest Z for index 0; decreasing as we go down
        # Example: count=3 -> z: 300, 200, 100
        for i, elem in enumerate(reordered):
            new_z = base + step * (count - i)
            if elem.zValue() != new_z:
                elem.setZValue(new_z)  # should cause scene/item_changed emissions

        # Notify listeners to refresh views/scenes as needed
        self.item_z_changed_requested.emit(None, 0)
