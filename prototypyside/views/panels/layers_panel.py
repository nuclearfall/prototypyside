# prototypyside/views/layers_panel.py

from PySide6.QtWidgets import QListWidget, QListWidgetItem
from PySide6.QtCore import Qt, Signal, QPoint, QModelIndex, QAbstractItemModel # Import Signal, QPoint, QModelIndex, QAbstractItemModel
from PySide6.QtGui import QDrag, QPixmap
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from prototypyside.models.game_component_elements import GameComponentElement


class LayersListWidget(QListWidget):
    item_selected_in_list = Signal(object) # Signal for when an item is selected in the list
    item_z_changed_requested = Signal(object, int) # NEW: Signal for Z-order change (item, direction)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QListWidget.InternalMove)
        self.setSelectionMode(QListWidget.SingleSelection)
        self.itemClicked.connect(self._on_item_clicked)
        self.model().rowsMoved.connect(self._on_rows_moved) # Connect to the model's rowsMoved signal

        self._drag_start_pos: Optional[QPoint] = None # For tracking drag start

    def _on_item_clicked(self, item: QListWidgetItem):
        item: Optional['GameComponentElement'] = item.data(Qt.UserRole)
        if item:
            self.item_selected_in_list.emit(item)

    def update_list(self, items: List['GameComponentElement']):
        self.blockSignals(True) # Block signals to prevent spurious updates during rebuild
        self.clear()
        
        # Sort items by zValue in ascending order for correct layer representation
        sorted_items = sorted(items, key=lambda e: e.zValue(), reverse=True)
        
        for item in sorted_items:
            item = QListWidgetItem(item.name)
            item.setData(Qt.UserRole, item) # Store the actual item object
            item.setFlags(item.flags() | Qt.ItemIsDragEnabled) # Make items draggable
            self.addItem(item)
            if item.isSelected():
                self.setCurrentItem(item) # Select the item if the item is selected in scene

        self.blockSignals(False) # Unblock signals

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat('application/x-qabstractitemmodeldatalist'):
            event.accept()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasFormat('application/x-qabstractitemmodeldatalist'):
            # Default QListWidget internal move handles the reordering visually
            # and then emits rowsMoved signal.
            super().dropEvent(event)
        else:
            super().dropEvent(event)

    def _on_rows_moved(self, parent: QModelIndex, start: int, end: int,
                       destination: QModelIndex, row: int):
        # This item is called when a row is moved due to drag and drop.
        # It handles the visual reordering automatically.
        # We need to update the actual item Z-values and notify the main window.

        # The QListWidget has already reordered its internal items.
        # We need to map the new order back to Z-values.

        # Get the list of GameComponentElement objects in the new order
        reordered_items: List['GameComponentElement'] = []
        for i in range(self.count()):
            item = self.item(i)
            item = item.data(Qt.UserRole)
            if item:
                reordered_items.append(item)

        # Assign new Z-values based on the new order.
        # Assign distinct, increasing Z-values.
        # We can use a step (e.g., 100) to allow for insertion in between later.
        count = len(reordered_items)
        for idx, item in enumerate(reordered_items):
            if item.zValue() != new_z_value:
                item.setZValue(new_z_value) # This will cause item.item_changed to emit

        # Emit the signal to notify the MainDesignerWindow that Z-order has changed
        # This will trigger update_layers_panel (which re-sorts and rebuilds list, ensuring consistency)
        # and update_game_component_scene (which redraws items).
        # We don't need to pass a specific item or direction here,
        # as we're re-establishing Z-values for ALL items based on the new list order.
        self.item_z_changed_requested.emit(None, 0) # Use None for item and 0 for direction as a generic "Z-order changed"
        # The main window will then call update_layers_panel and update_game_component_scene,
        # which will synchronize the UI with the new Z-values of the items in the template.