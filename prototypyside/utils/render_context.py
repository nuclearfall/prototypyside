from enum import Enum, auto
# Render enumerations
class RenderMode(Enum):
    GUI = auto()
    EXPORT = auto()

class TabMode(Enum):
    COMPONENT = auto()
    LAYOUT = auto()

class RenderRoute(Enum):
    RASTER = auto()
    COMPOSITE = auto()
    VECTOR_PRIORITY = auto()

class RenderContext:
    """Unified rendering context that encapsulates all rendering parameters"""
    def __init__(self, mode=RenderMode.GUI, tab_mode=TabMode.COMPONENT, 
                 route=RenderRoute.COMPOSITE, dpi=300, vector_priority=False):
        self.mode = mode
        self.tab_mode = tab_mode
        self.route = route
        self.dpi = dpi
        self.vector_priority = vector_priority
        
    @property
    def is_gui(self):
        return self.mode == RenderMode.GUI
        
    @property
    def is_export(self):
        return self.mode == RenderMode.EXPORT
        
    @property
    def is_component_tab(self):
        return self.tab_mode == TabMode.COMPONENT
        
    @property
    def is_layout_tab(self):
        return self.tab_mode == TabMode.LAYOUT