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
    def __init__(self, dpi, unit, mode=RenderMode.GUI, tab_mode=TabMode.COMPONENT, 
                 route=RenderRoute.COMPOSITE):
        self.mode = mode
        self.tab_mode = tab_mode
        self.route = route
        self._dpi = dpi
        self._unit = unit
        
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

    @property
    def is_raster(self):
        return self.route == RenderRoute.RASTER

    @property
    def is_composite(self):
        return self.route == RenderRoute.COMPOSITE

    # @property
    # def ctx(self):
    #     return self._ctx

    # @ctx.setter
    # def ctx(self, new):
    #     if self._ctx == new:
    #         return
    #     self._ctx = new
    
    @property
    def unit(self):
        return self._unit

    @unit.setter
    def unit(self, new):
        if new == self._unit:
            return
        self._unit = new

    @property
    def dpi(self):
        return self._dpi
    
    
    @dpi.setter
    def dpi(self, new):
        if new == self._unit:
            return
        self._unit = new
    
    # --- Serialization ---
    def to_dict(self) -> dict:
        """Return a JSON-serializable dictionary representation."""
        return {
            "mode": self.mode.name,
            "tab_mode": self.tab_mode.name,
            "route": self.route.name,
            "dpi": self.dpi,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RenderContext":
        """Reconstruct a RenderContext from its dict representation."""
        return cls(
            mode=RenderMode[data.get("mode", "GUI")],
            tab_mode=TabMode[data.get("tab_mode", "COMPONENT")],
            route=RenderRoute[data.get("route", "COMPOSITE")],
            dpi=int(data.get("dpi", 300)),
        )