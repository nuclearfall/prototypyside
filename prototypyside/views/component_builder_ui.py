from PySide6.QtWidgets import QWidget, QVBoxLayout
from prototypyside.views.element_palette import ElementPalette
from prototypyside.views.layers_panel import LayersPanel
from prototypyside.widgets.property_panel import PropertyPanel

from PySide6.QtWidgets import QToolBar

from prototypyside.views.base_editor_ui import BaseEditorUI

class ComponentBuilderUI(BaseEditorUI):
    def __init__(self, component_builder):
        super().__init__(component_builder)
        self.component_builder = component_builder
        self.settings = component_builder.settings
        self.appwin = component_builder.appwin

        self.setup_left_panel()
        self.setup_right_panel()

    def setup_left_panel(self):
        self.component_builder.element_palette = ElementPalette()
        self.component_builder.element_palette.element_type_selected.connect(
            self.component_builder.on_element_type_selected
        )

        self.component_builder.layers_panel = LayersPanel()
        self.component_builder.layers_panel.element_selected_in_list.connect(
            self.component_builder.on_layer_element_selected
        )

        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)
        left_layout.addWidget(self.component_builder.element_palette)
        left_layout.addWidget(self.component_builder.layers_panel)

        self.component_builder.left_dock_layout.addWidget(left_container)

    def populate_toolbar(self):
        # Stub for toolbar population
        # Override this in subclasses to add toolbar widgets or actions
        pass

    def setup_right_panel(self):
        self.component_builder.property_panel = PropertyPanel(settings=self.settings)
        self.component_builder.property_panel.set_mode("component")

        # Safely connect only after instantiation
        if self.component_builder.property_panel:
            self.component_builder.property_panel.property_changed.connect(
                self.component_builder.on_property_changed
            )

        self.component_builder.right_dock_layout.addWidget(self.component_builder.property_panel)