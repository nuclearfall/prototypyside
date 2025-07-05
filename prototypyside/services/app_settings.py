from PySide6.QtCore import QObject, Signal, Property

# @dataclass
# class DPIContext:
#     display_dpi: int = 144
#     print_dpi: int = 300

#     def for_display(self): return self.display_dpi
#     def for_print(self): return self.print_dpi
    
class AppSettings(QObject):
    unit_changed = Signal(str, int)

    def __init__(self, display_unit="px", physical_unit="in", display_dpi=144, print_dpi=300):
        super().__init__()
        self._display_unit = display_unit
        self._display_dpi = display_dpi
        self._print_dpi = print_dpi
        self._physical_unit = physical_unit

    @Property(str)
    def unit(self):
        return self._display_unit

    @unit.setter
    def unit(self, unit):       
        if self._display_unit != unit:
            self._display_unit = unit
            self.unit_changed.emit(unit, self._display_dpi)

    @Property(int)
    def dpi(self):
        return self._display_dpi

    @Property(int)
    def display_dpi(self):
        return self._display_dpi
               
    @Property(str)
    def display_unit(self):
        return self._display_unit

    @display_unit.setter
    def display_unit(self, unit):
        if self._display_unit != unit:
            self._display_unit = unit
            self.unit_changed.emit(unit, self._display_dpi)
