from PySide6.QtCore import QObject, Signal, Property

# @dataclass
# class DPIContext:
#     display_dpi: int = 300
#     print_dpi: int = 300

#     def for_display(self): return self.display_dpi
#     def for_print(self): return self.print_dpi
    
class AppSettings(QObject):
    unit_changed = Signal(str)
    print_unit_and_dpi_changed = Signal(str)


    def __init__(self, display_unit="in", print_unit="in", display_dpi=300, print_dpi=300):
        super().__init__()
        self._display_unit = display_unit
        self._display_dpi = display_dpi
        self._print_dpi = print_dpi
        self._print_unit = print_unit

    @Property(str)
    def unit(self):
        return self._display_unit

    @unit.setter
    def unit(self, unit):       
        if self._display_unit != unit:
            self._display_unit = unit
            self.unit_changed.emit(unit)

    @Property(int)
    def dpi(self):
        return self._display_dpi

    @Property(int)
    def display_dpi(self):
        return self._display_dpi

    @display_dpi.setter
    def display_dpi(self, new_dpi):
        if new_dpi != self._display_dpi:
            self._display_dpi = new_dpi
               
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

