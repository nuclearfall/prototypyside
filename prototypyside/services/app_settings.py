from PySide6.QtCore import QObject, Signal, Property
from PySide6.QtWidgets import QApplication,QGraphicsScene
from PySide6.QtGui import QFont

from prototypyside.utils.units.unit_str_font import UnitStrFont
from prototypyside.utils.render_context import RenderContext, RenderMode, RenderRoute, TabMode

# @dataclass
# class DPIContext:
#     display_dpi: int = 300
#     print_dpi: int = 300

#     def for_display(self): return self.display_dpi
#     def for_print(self): return self.print_dpi
    
class AppSettings(QObject):
    unit_changed = Signal(str)
    print_unit_and_dpi_changed = Signal(str)
    dpi_changed = Signal(int)
    ctx_changed = Signal(object)

    def __init__(self, display_unit="in", print_unit="pt", display_dpi=300, print_dpi=300):
        super().__init__()
        self._display_unit = display_unit
        self._print_dpi = print_dpi
        self._print_unit = print_unit
        self._display_dpi = display_dpi
        self._dpi = self._display_dpi
        self._unit = "px"
        self.default_font = UnitStrFont(QFont("Arial", 12))

        self._ctx = RenderContext(
            dpi=self._dpi,
            unit=self._unit,
            mode=RenderMode.GUI,
            tab_mode=TabMode.LAYOUT,
            route=RenderRoute.COMPOSITE,

        )
        screen = QApplication.primaryScreen()
        logical = screen.logicalDotsPerInch()
        physical = screen.physicalDotsPerInch()
        dpr = screen.devicePixelRatio()

        # Effective DPI (scaled) if you want to treat 72 as base
        effective = logical * dpr
        self._ldpi = effective

    @Property(object)
    def ctx(self):
        return self._ctx

    @ctx.setter
    def ctx(self, new):
        if self._ctx == new:
            return
        self._ctx = new

    @Property(str)
    def unit(self):
        return self._unit

    @unit.setter
    def unit(self, unit):       
        if self._unit != unit:
            self._unit = unit
            self._ctx.unit = unit
            self.unit_changed.emit(unit)

    @Property(int)
    def dpi(self):
        return self._dpi

    @dpi.setter
    def dpi(self, new_dpi):
        if new_dpi != self._dpi:
            self._dpi = new_dpi
            self._ctx.dpi = new_dpi 
            print(f"[APPSETTINGS] new dpi {new_dpi} emitted")
            self.dpi_changed.emit(new_dpi)

    @Property(float)
    def display_dpi(self):
        return self._display_dpi

    @display_dpi.setter
    def display_dpi(self, new):
        if self._display_dpi == new:
            return
        self._display_dpi = new
    
    @Property(float)
    def ldpi(self) -> float:
        return self._ldpi
               
    @Property(int)
    def print_dpi(self):
        return self._print_dpi

    @print_dpi.setter
    def print_dpi(self, new_dpi):
        if new_dpi != self._print_dpi:
            self._print_dpi = new_dpi

    @Property(str)
    def display_unit(self):
        return self._display_unit

    @display_unit.setter
    def display_unit(self, unit):
        if self._display_unit != unit:
            self._display_unit = unit
            self.unit_changed.emit(unit)

    @Property(str)
    def print_unit(self):
        return self._print_unit

    @display_unit.setter
    def print_unit(self, unit):
        if self._print_unit != unit:
            self._print_unit = unit
            self.unit_changed.emit(unit) 

    @property 
    def ldpi(self):
        return self._ldpi

    @ldpi.setter
    def ldpi(self, value):
        self._ldpi = value if value != self._ldpi else self._ldpi