from PySide6.QtCore import QObject, Signal, Property
from PySide6.QtWidgets import QApplication,QGraphicsScene



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

    def __init__(self, display_unit="in", print_unit="in", display_dpi=300, print_dpi=600):
        super().__init__()
        self._display_unit = display_unit
        self._print_dpi = print_dpi
        self._print_unit = print_unit
        self._display_dpi = display_dpi
        self._dpi = self._display_dpi
        scene = QGraphicsScene()
        screen = QApplication.primaryScreen()
        # Works from a QGraphicsItem / QGraphicsObject
        view = scene.views()[0] if (scene and scene.views()) else None

        screen = (view.window().windowHandle().screen() if view and view.window() and view.window().windowHandle()
                  else (view.screen() if view else QApplication.primaryScreen()))

        logical = float(screen.logicalDotsPerInchY())           # often 72 on macOS
        dpr = (float(view.devicePixelRatioF()) if view else float(screen.devicePixelRatio()))
        self._ldpi = logical * dpr   

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
        return self._dpi

    @dpi.setter
    def dpi(self, new_dpi):
        if new_dpi != self._dpi:
            self._dpi = new_dpi
            print(f"[APPSETTINGS] new dpi {new_dpi} emitted")
            self.dpi_changed.emit(new_dpi)


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