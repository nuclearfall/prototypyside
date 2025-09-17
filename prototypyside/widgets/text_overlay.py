# text_overlay.py
from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtWidgets import QGraphicsTextItem, QGraphicsScene

if TYPE_CHECKING:
    from prototypyside.views.proto_text_renderer import ProtoTextRenderer

class TextOverlay(QGraphicsTextItem):
    """
    An in-scene editor surface that edits the SAME QTextDocument
    provided by ProtoTextRenderer. It does not own the document; it
    only provides UI for caret/selection/IME.

    Usage:
        overlay = TextOverlay.start(
            scene=scene,
            element=element,
            renderer=element.renderer,
            content_rect=element.content_rect_px()
        )
        overlay.committed.connect(on_commit)
        overlay.canceled.connect(on_cancel)

    Signals:
        committed(element, new_html: str, old_html: str)
        canceled(element)
    """
    committed = Signal(object, str, str)   # (element, new_html, old_html)
    canceled  = Signal(object)             # (element)

    def __init__(
        self,
        element: object,
        renderer: "ProtoTextRenderer",
        *,
        z_bump: float = 1000.0,
        parent: Optional[QGraphicsTextItem] = None
    ):
        super().__init__(parent)

        self._element = element
        self._renderer = renderer
        self._doc = renderer.document            # shared document
        self.setDocument(self._doc)

        # Keep track of original state for undo/cancel
        self._original_html = self._doc.toHtml()

        # Interaction & focus
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFlag(self.ItemIsFocusable, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(getattr(element, "zValue", lambda: 0.0)() + z_bump)

        # Respect view zoom & transforms (InDesign-like)
        # If you prefer fixed-pixel text regardless of zoom, set True:
        self.setFlag(self.ItemIgnoresTransformations, False)

        # Optional: tell the element it's in editing mode (if supported)
        if hasattr(self._element, "set_editing"):
            try:
                self._element.set_editing(True)
            except Exception:
                pass

    # ---------- lifecycle helpers ----------

    @classmethod
    def start(
        cls,
        scene: QGraphicsScene,
        element: object,
        renderer: "ProtoTextRenderer",
        content_rect: QRectF,
        *,
        focus_reason: Qt.FocusReason = Qt.MouseFocusReason
    ) -> "TextOverlay":
        """
        Convenience: create, position/size, add to scene, focus, return overlay.
        """
        overlay = cls(element=element, renderer=renderer)
        overlay.update_geometry(content_rect)

        scene.addItem(overlay)
        overlay.setFocus(focus_reason)
        overlay.ensureCursorVisible()
        return overlay

    def update_geometry(self, content_rect: QRectF) -> None:
        """
        Keep the overlay aligned with the element’s content frame.
        Call this if the element resizes while editing.
        """
        self.setPos(content_rect.topLeft())
        self.setTextWidth(max(0.0, float(content_rect.width())))
        # Height of a QGraphicsTextItem is driven by the document;
        # we don't clamp it here. Clipping is done by your renderer,
        # not by the overlay.

    # ---------- commit / cancel ----------

    def commit(self) -> None:
        """
        Emit a single commit event if the document changed; then close.
        """
        try:
            new_html = self._doc.toHtml()
            old_html = self._original_html
            if new_html != old_html:
                self.committed.emit(self._element, new_html, old_html)
        finally:
            self._teardown()

    def cancel(self) -> None:
        """
        Restore pre-edit HTML and emit canceled; then close.
        """
        try:
            # Revert the shared document to the original HTML
            self._doc.setHtml(self._original_html)
            self.canceled.emit(self._element)
        finally:
            self._teardown()

    def _teardown(self) -> None:
        # Optional: tell the element editing is done
        if hasattr(self._element, "set_editing"):
            try:
                self._element.set_editing(False)
            except Exception:
                pass
        # Remove from scene safely
        if self.scene():
            self.scene().removeItem(self)
        # Drop references to help GC (document is owned by renderer)
        self.setDocument(None)  # type: ignore
        self._doc = None  # type: ignore

    # ---------- events ----------

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        # Click-away commit (InDesign-like)
        self.commit()

    def keyPressEvent(self, e):
        # Cmd/Ctrl + Enter = commit
        if (e.key() in (Qt.Key_Return, Qt.Key_Enter)) and (e.modifiers() & (Qt.ControlModifier | Qt.MetaModifier)):
            self.commit()
            return
        # Esc = cancel/revert
        if e.key() == Qt.Key_Escape:
            self.cancel()
            return
        super().keyPressEvent(e)

    # Optional: prevent accidental dragging while editing
    def mouseMoveEvent(self, e):
        # Don’t propagate as item move; keep default text selection behavior.
        super().mouseMoveEvent(e)
