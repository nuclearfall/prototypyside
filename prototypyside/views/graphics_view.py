# graphics_view.py
# prototypyside/views/designer_graphics_view.py
from PySide6.QtWidgets import QGraphicsView, QPinchGesture, QGestureEvent
from PySide6.QtGui import QWheelEvent, QPainter, QTransform
from PySide6.QtCore import Qt, QPointF, QEvent, QRectF, QSizeF, QObject, QVariantAnimation, QEasingCurve
import sys

IS_MAC = sys.platform == 'darwin'

class DesignerGraphicsView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)

        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)

        # Accept touch and gestures
        self.setAttribute(Qt.WA_AcceptTouchEvents)
        self.grabGesture(Qt.PinchGesture)
        self.viewport().setAttribute(Qt.WA_AcceptTouchEvents)
        self.viewport().grabGesture(Qt.PinchGesture)
        self.viewport().installEventFilter(self)

        self.current_scale = 1.0
        self._last_scale = 1.0
        self.MIN_SCALE = 1.0
        self.MAX_SCALE = 10.0
        self._pinch_start_transform = QTransform()
        self._pinch_last_factor = 1.0
        self._gesture_active = False
        self.PINCH_SENSITIVITY = 2.1
        self._pinch_direction = None  # 'in', 'out', or None

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Gesture:
            return self.gestureEvent(event)
        return super().event(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Gesture:
            return self.gestureEvent(event)
        return super().eventFilter(watched, event)

    def gestureEvent(self, event: QGestureEvent) -> bool:
        print(f"gestureEvent triggered {self._pinch_direction}")
        pinch = event.gesture(Qt.PinchGesture)
        if pinch:
            print(f"gestureEvent triggered {self._pinch_direction}")
            self.handlePinchGesture(pinch)
            return True
        return False

    def handlePinchGesture(self, pinch: QPinchGesture):
        if pinch.state() == Qt.GestureStarted:
            self._gesture_active = True
            self._pinch_direction = None
            self._pinch_last_factor = 1.0

        elif pinch.state() == Qt.GestureUpdated:
            if not self._gesture_active:
                return  # Ignore spurious gestures

            scale_factor = pinch.scaleFactor()
            raw_delta = scale_factor / self._pinch_last_factor

            # Lock direction once
            if self._pinch_direction is None:
                if raw_delta > 1.01:
                    self._pinch_direction = 'in'
                elif raw_delta < 0.99:
                    self._pinch_direction = 'out'
                else:
                    return  # Still undecided, wait for clearer delta

            # Prevent reversal mid-gesture
            if self._pinch_direction == 'in' and raw_delta < 1.0:
                return
            if self._pinch_direction == 'out' and raw_delta > 1.0:
                return

            # Smooth scaling
            sensitivity = self.PINCH_SENSITIVITY
            eased_delta = raw_delta ** sensitivity
            smoothed_delta = 1.0 + (eased_delta - 1.0)

            new_scale = self.current_scale * smoothed_delta
            if self.MIN_SCALE <= new_scale <= self.MAX_SCALE:
                self.scaleView(smoothed_delta)
                self.current_scale = new_scale

            self._pinch_last_factor = scale_factor

        elif pinch.state() in (Qt.GestureFinished, Qt.GestureCanceled):
            self._gesture_active = False
            self._pinch_direction = None
            self._pinch_last_factor = 1.0


    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() == Qt.ControlModifier or IS_MAC:
            degrees = event.angleDelta().y() / 8
            steps = degrees / 15  # 15 degrees = 1 "notch"
            factor = 1.0 + steps * 0.05  # 5% zoom per notch

            # Clamp for safety
            if factor > 0:
                self.scaleView(factor)

            event.accept()
        else:
            super().wheelEvent(event)


    def scaleView(self, factor: float):
        new_scale = self.current_scale * factor

        # Clamp scale between MIN_SCALE and MAX_SCALE
        if new_scale < self.MIN_SCALE or new_scale > self.MAX_SCALE:
            return

        self.current_scale = new_scale
        self.scale(factor, factor)

    def startZoomAnimation(self, start_scale: float, end_scale: float, duration: int = 150):
        if hasattr(self, "_zoom_anim") and self._zoom_anim:
            self._zoom_anim.stop()

        anim = QVariantAnimation(self)
        anim.setStartValue(start_scale)
        anim.setEndValue(end_scale)
        anim.setDuration(duration)
        anim.setEasingCurve(QEasingCurve.InOutQuad)

        def on_value_changed(value):
            scale_factor = value / self.current_scale
            self.scaleView(scale_factor)

        anim.valueChanged.connect(on_value_changed)

        def on_finished():
            self._zoom_anim = None  # clear ref

        anim.finished.connect(on_finished)
        self._zoom_anim = anim
        anim.start()