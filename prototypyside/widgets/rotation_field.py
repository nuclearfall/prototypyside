from PySide6.QtCore import Qt, Signal, Slot, Property
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QSlider, QDoubleSpinBox, QToolButton, QSizePolicy
)

class RotationField(QWidget):
    """
    Rotation control (0–360°) with slider + numeric entry.
    Emits angleChanged(float) with degrees in [0, 360].
    """
    angleChanged = Signal(float)
    editingFinished = Signal()

    def __init__(self, parent=None, decimals=1, single_step=1.0, page_step=15.0):
        super().__init__(parent)

        self._scale = 10  # slider uses ints; scale 0.1° -> 1 tick
        self._block = False
        self._angle = 0.0

        self.slider = QSlider(Qt.Horizontal, self)
        self.slider.setRange(0, 360 * self._scale)
        self.slider.setSingleStep(int(single_step * self._scale))
        self.slider.setPageStep(int(page_step * self._scale))
        self.slider.setFocusPolicy(Qt.NoFocus)

        self.spin = QDoubleSpinBox(self)
        self.spin.setDecimals(decimals)
        self.spin.setRange(0.0, 360.0)
        self.spin.setSingleStep(single_step)
        self.spin.setSuffix("°")
        self.spin.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.spin.setKeyboardTracking(False)  # only commit on Enter/focus-out

        self.btn_minus90 = QToolButton(self); self.btn_minus90.setText("−90°")
        self.btn_reset   = QToolButton(self); self.btn_reset.setText("0°")
        self.btn_plus90  = QToolButton(self); self.btn_plus90.setText("+90°")

        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(6)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.spin, 0)
        lay.addWidget(self.btn_minus90, 0)
        lay.addWidget(self.btn_reset, 0)
        lay.addWidget(self.btn_plus90, 0)

        self.spin.setMinimumWidth(72)
        self.spin.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # wiring
        self.slider.valueChanged.connect(self._on_slider_changed)
        self.spin.valueChanged.connect(self._on_spin_changed)
        self.spin.editingFinished.connect(self._emit_finished)

        # 🔽 ADD THESE so commits happen beyond the spinbox:
        self.slider.sliderReleased.connect(self._emit_finished)

        self.btn_minus90.clicked.connect(self._on_click_minus90)
        self.btn_plus90.clicked.connect(self._on_click_plus90)
        self.btn_reset.clicked.connect(self._on_click_reset)

        self.setAngle(0.0, emit_signal=False)

    # ---- API
    def angle(self) -> float:
        return self._angle

    @Slot(float)
    def setAngle(self, deg: float, emit_signal: bool = True):
        """Set angle in degrees; clamps to [0, 360]. 360 normalizes to 0 to avoid duplicates."""
        val = self._norm(deg)
        self._angle = val
        self._sync_views(val)
        if emit_signal:
            self.angleChanged.emit(val)

    angleProp = Property(float, fget=angle, fset=setAngle, notify=angleChanged)

    # ---- internals
    def _norm(self, deg: float) -> float:
        """Normalize any float to [0, 360]; treat 360 as 0 for consistency."""
        if deg is None:
            return 0.0
        v = float(deg) % 360.0
        # keep exactly-360 entries as 0 to avoid two representations
        if abs(v - 360.0) < 1e-9 or abs(v) < 1e-9:
            return 0.0
        return v

    def _sync_views(self, val: float):
        self._block = True
        try:
            self.spin.setValue(val)
            self.slider.setValue(int(round(val * self._scale)))
        finally:
            self._block = False

    # new helpers ensure we emit after changing the angle
    def _on_click_minus90(self):
        self.setAngle(self._norm(self._angle - 90))
        self._emit_finished()

    def _on_click_plus90(self):
        self.setAngle(self._norm(self._angle + 90))
        self._emit_finished()

    def _on_click_reset(self):
        self.setAngle(0.0)
        self._emit_finished()

    def _emit_finished(self):
        self.editingFinished.emit()

    @Slot(int)
    def _on_slider_changed(self, v: int):
        if self._block: return
        deg = (v / self._scale)
        self._angle = self._norm(deg)
        self._sync_views(self._angle)
        self.angleChanged.emit(self._angle)

    @Slot(float)
    def _on_spin_changed(self, v: float):
        if self._block: return
        self._angle = self._norm(v)
        self._sync_views(self._angle)
        self.angleChanged.emit(self._angle)

    def _emit_finished(self):
        self.editingFinished.emit()
