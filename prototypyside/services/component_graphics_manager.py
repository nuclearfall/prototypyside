# component_graphics_manager.py


class ComponentGraphicsManager:
    def __init__(self, scene: QGraphicsScene, registry: MyRegistry):
        self.scene = scene
        self.registry = registry
        self.scene_items_map = {} # Maps template element IDs to QGraphicsItems

    def synchronize_with_registry(self):
        """Pulls the latest state from the registry and updates the scene."""
        template_elements = self.registry.get_all_elements() 
        template_element_ids = {element.id for element in template_elements}

        # 1. Identify and remove items from the scene that are no longer in the active elements
        items_to_remove = []
        for item_id, item in list(self.scene_items_map.items()): # Iterate over a copy
            if item_id not in template_element_ids:
                items_to_remove.append(item)
                del self.scene_items_map[item_id] # Remove from our map immediately

        for item in items_to_remove:
            self.scene.removeItem(item)
            # In C++, you'd typically 'delete item;' here if you own it.
            # In Python, it will be GC'd when no more references.

        # 2. Iterate through active registry elements to add or update items in the scene
        for element in template_elements:
            item_id = element.id
            
            if item_id in self.scene_items_map:
                # Item exists, update its properties
                graphics_item = self.scene_items_map[item_id]
                self._update_graphics_item_properties(graphics_item, element)
            else:
                # Item does not exist, create and add it
                graphics_item = self._create_graphics_item(element)
                if graphics_item:
                    self.scene.addItem(graphics_item)
                    self.scene_items_map[item_id] = graphics_item

        self.scene.update()
        self.print_current_scene_state()


    def _create_graphics_item(self, element):
        """Creates a QGraphicsItem based on the element's type and properties."""
        item = None
        if element.type == 'rectangle':
            item = QGraphicsRectItem(QRectF(element.x, element.y, element.width, element.height))
            item.setPen(Qt.black)
            item.setBrush(element.color) # Use element's color
        elif element.type == 'ellipse':
            item = QGraphicsEllipseItem(QRectF(element.x, element.y, element.width, element.height))
            item.setPen(Qt.black)
            item.setBrush(element.color)
        elif element.type == 'text':
            item = QGraphicsTextItem(element.text)
            item.setPos(QPointF(element.x, element.y))
        
        if item:
            item.setData(0, element.id) # Store element ID on the graphics item
        return item

    def _update_graphics_item_properties(self, graphics_item: QGraphicsItem, element):
        """Updates the properties of an existing QGraphicsItem."""
        if isinstance(graphics_item, QGraphicsRectItem):
            graphics_item.setRect(QRectF(element.x, element.y, element.width, element.height))
            graphics_item.setBrush(element.color)
        elif isinstance(graphics_item, QGraphicsEllipseItem):
            graphics_item.setRect(QRectF(element.x, element.y, element.width, element.height)) # Ellipse uses rect
            graphics_item.setBrush(element.color)
        elif isinstance(graphics_item, QGraphicsTextItem):
            graphics_item.setPlainText(element.text)
            graphics_item.setPos(QPointF(element.x, element.y))

    def print_current_scene_state(self):
        current_ids = [item.data(0) for item in self.scene.items() if item.data(0)]
        print(f"Scene items (by ID): {sorted(current_ids)}")
        print(f"Registry active elements: {[e.id for e in self.registry.get_all_elements()]}")
        print(f"Registry orphans: {[e.id for e in self.registry.get_all_orphans()]}")
        print("-" * 30)