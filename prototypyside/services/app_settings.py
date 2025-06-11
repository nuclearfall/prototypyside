from PySide6.QtCore import QObject, Signal, Property

class AppSettings(QObject):
    unit_changed = Signal(str)
    on_dpi_changed = Signal(int)

    def __init__(self, unit="px", display_dpi=300, print_dpi=300):
        super().__init__()
        self._unit = unit
        self._display_dpi = display_dpi
        self._print_dpi = print_dpi

    @Property(str)
    def unit(self):
        return self._unit

    @unit.setter
    def unit(self, value):
        if self._unit != value:
            self._unit = value
            self.unit_changed.emit(value)

    # Here we alias dpi to display dpi as it is the primary unit being used.
    @Property(int)
    def dpi(self):
        return self.display_dpi

    @dpi.setter
    def display_dpi(self, value):
        if self._display_dpi != value:
            self._display_dpi = value
            self.display_dpi_changed.emit(value)
               
    @Property(int)
    def display_dpi(self):
        return self._display_dpi

    @display_dpi.setter
    def display_dpi(self, value):
        if self._display_dpi != value:
            self._display_dpi = value
            self.display_dpi_changed.emit(value)

    @Property(int)
    def print_dpi(self):
        return self._print_dpi

    @print_dpi.setter
    def print_dpi(self, value):
        if self._print_dpi != value:
            self._print_dpi = value
            self.print_dpi_changed.emit(value)

    def set_all(self, unit: str, display_dpi: int, print_dpi: int):
        # blockSignals isn't necessary here because we're emitting explicitly
        self.unit = unit
        self.display_dpi = display_dpi
        self.print_dpi = print_dpi
