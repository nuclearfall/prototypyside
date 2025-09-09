# component_view.py
# prototypyside/views/designer_component_view.py
from PySide6.QtWidgets import QGraphicsView, QPinchGesture, QGestureEvent
from PySide6.QtGui import QWheelEvent, QPainter, QTransform, QMouseEvent
from PySide6.QtCore import Qt, QPointF, QEvent, QRectF, QSizeF, QMarginsF, QObject, QVariantAnimation, QEasingCurve, QTimer
import sys

IS_MAC = sys.platform == 'darwin'

class ComponentView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)

        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        # self.setMouseTracking(True)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        self.setInteractive(True)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setRubberBandSelectionMode(Qt.IntersectsItemShape)
        self.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)
        # Accept touch and gestures
        self.setAttribute(Qt.WA_AcceptTouchEvents)
        self.grabGesture(Qt.PinchGesture)
        self.viewport().setAttribute(Qt.WA_AcceptTouchEvents)
        self.viewport().grabGesture(Qt.PinchGesture)
        self.viewport().installEventFilter(self)
        
        self.current_scale = 1.0
        self._last_scale = 1.0
        self._pinch_start_transform = QTransform()
        self._pinch_last_factor = 1.0
        self._gesture_active = False
        self.PINCH_SENSITIVITY = 1.3
        self._pinch_direction = None  # 'in', 'out', or None
        self._panning = False
        # Always initialize MIN_SCALE and MAX_SCALE
        # Provide sensible default values, then update if scene/view are valid
        self.MIN_SCALE = 0.001 # A small default value
        self.MAX_SCALE = 100.0  # Your desired max scale

    def _update_min_scale(self):
        scene_rect = self.sceneRect()
        view_size = self.viewport().size()

        if not scene_rect.isEmpty() and not view_size.isEmpty():
            scale_x = view_size.width() / scene_rect.width() * 0.25
            scale_y = view_size.height() / scene_rect.height() * 0.25
            self.MIN_SCALE = min(scale_x, scale_y)
            if self.MAX_SCALE < self.MIN_SCALE:
                self.MAX_SCALE = self.MIN_SCALE * 100 # Or some other logical multiple

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Gesture:
            return self.gestureEvent(event)
        return super().event(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Gesture:
            return self.gestureEvent(event)
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_min_scale()
        self._update_padded_scene_rect()

    def gestureEvent(self, event: QGestureEvent) -> bool:
        pinch = event.gesture(Qt.PinchGesture)
        if pinch:
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
                    return  # Still undecided

            # Prevent reversal mid-gesture
            if (self._pinch_direction == 'in' and raw_delta < 1.0) or \
               (self._pinch_direction == 'out' and raw_delta > 1.0):
                return

            # Apply sensitivity
            sensitivity = self.PINCH_SENSITIVITY
            eased_delta = raw_delta ** sensitivity
            smoothed_delta = 1.0 + (eased_delta - 1.0)

            # Let scaleView handle clamping and applying
            self.scaleView(smoothed_delta)

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
        proposed_scale = self.current_scale * factor
        clamped_scale = max(self.MIN_SCALE, min(proposed_scale, self.MAX_SCALE))

        # Adjust actual factor to only apply the portion that stays within bounds
        actual_factor = clamped_scale / self.current_scale

        self.current_scale = clamped_scale
        self.scale(actual_factor, actual_factor)

        self._update_padded_scene_rect()

    # Right click to pan

    def mousePressEvent(self, event: QMouseEvent):
            if event.button() == Qt.RightButton:
                self._panning = True
                self._pan_start = event.pos()
                self.setCursor(Qt.ClosedHandCursor)
                event.accept()
                return
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._panning:
            delta = self._pan_start - event.pos()
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() + delta.x()
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() + delta.y()
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.RightButton and self._panning:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)
        
    def _update_padded_scene_rect(self):
        """Expand the logical sceneRect to give blank margins for panning."""
        bounds = self.scene().itemsBoundingRect()
        # how much blank space? half the viewport, in scene units:
        w = self.viewport().width()  / self.current_scale
        h = self.viewport().height() / self.current_scale
        padded = bounds.marginsAdded(QMarginsF(w/2, h/2, w/2, h/2))
        super().setSceneRect(padded)