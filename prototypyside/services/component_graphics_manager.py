# component_graphics_manager.py


class ComponentGraphicsManager:
    def __init__(self, scene: QGraphicsScene, registry: MyRegistry):
        self.scene = scene
        self.registry = registry
        self.scene_items_map = {} # Maps template item IDs to QGraphicsItems

    def synchronize_with_registry(self):
        """Pulls the latest state from the registry and updates the scene."""
        template_items = self.registry.get_all_items() 
        template_item_ids = {item.id for item in template_items}

        # 1. Identify and remove items from the scene that are no longer in the active items
        items_to_remove = []
        for item_id, item in list(self.scene_items_map.items()): # Iterate over a copy
            if item_id not in template_item_ids:
                items_to_remove.append(item)
                del self.scene_items_map[item_id] # Remove from our map immediately

        for item in items_to_remove:
            self.scene.removeItem(item)
            # In C++, you'd typically 'delete item;' here if you own it.
            # In Python, it will be GC'd when no more references.

        # 2. Iterate through active registry items to add or update items in the scene
        for item in template_items:
            item_id = item.id
            
            if item_id in self.scene_items_map:
                # Item exists, update its properties
                graphics_item = self.scene_items_map[item_id]
                self._update_graphics_item_properties(graphics_item, item)
            else:
                # Item does not exist, create and add it
                graphics_item = self._create_graphics_item(item)
                if graphics_item:
                    self.scene.addItem(graphics_item)
                    self.scene_items_map[item_id] = graphics_item

        self.scene.update()
        self.print_current_scene_state()


    def _create_graphics_item(self, item):
        """Creates a QGraphicsItem based on the item's type and properties."""
        item = None
        if item.type == 'rectangle':
            item = QGraphicsRectItem(QRectF(item.x, item.y, item.width, item.height))
            item.setPen(Qt.black)
            item.setBrush(item.color) # Use item's color
        elif item.type == 'ellipse':
            item = QGraphicsEllipseItem(QRectF(item.x, item.y, item.width, item.height))
            item.setPen(Qt.black)
            item.setBrush(item.color)
        elif item.type == 'text':
            item = QGraphicsTextItem(item.text)
            item.setPos(QPointF(item.x, item.y))
        
        if item:
            item.setData(0, item.id) # Store item ID on the graphics item
        return item

    def _update_graphics_item_properties(self, graphics_item: QGraphicsItem, item):
        """Updates the properties of an existing QGraphicsItem."""
        if isinstance(graphics_item, QGraphicsRectItem):
            graphics_item.setRect(QRectF(item.x, item.y, item.width, item.height))
            graphics_item.setBrush(item.color)
        elif isinstance(graphics_item, QGraphicsEllipseItem):
            graphics_item.setRect(QRectF(item.x, item.y, item.width, item.height)) # Ellipse uses rect
            graphics_item.setBrush(item.color)
        elif isinstance(graphics_item, QGraphicsTextItem):
            graphics_item.setPlainText(item.text)
            graphics_item.setPos(QPointF(item.x, item.y))

    def print_current_scene_state(self):
        current_ids = [item.data(0) for item in self.scene.items() if item.data(0)]
        print(f"Scene items (by ID): {sorted(current_ids)}")
        print(f"Registry active items: {[e.id for e in self.registry.get_all_items()]}")
        print(f"Registry orphans: {[e.id for e in self.registry.get_all_orphans()]}")
        print("-" * 30)