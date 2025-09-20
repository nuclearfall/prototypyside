# font_toolbar.py
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QWidget,
    QFontComboBox,
    QComboBox,
    QToolButton,
    QHBoxLayout,
    QVBoxLayout
)

# Project font/unit helpers
from prototypyside.config import HMAP, VMAP, HMAP_REV, VMAP_REV
from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_font import UnitStrFont


class FontToolbar(QWidget):
    """
    A compact font toolbar that edits a ComponentElement's UnitStrFont.
    Emits: value(target, 'font', new_usf, old_usf)
    """

    # REQUIRED by caller: (target: ComponentElement, prop_name: str, new_val: UnitStrFont, old_val: UnitStrFont)
    fontChanged = Signal(object, str, object, object)
    hAlignChanged = Signal(object, str, object, object)
    vAlignChanged = Signal(object, str, object, object)

    def __init__(self, parent: Optional[QWidget] = None, *, default_dpi: float = 300.0) -> None:
        super().__init__(parent)
        self._updating = False
        self._default_dpi = float(default_dpi)
        self._target: Optional[object] = None  # ComponentElement-like (has .font: UnitStrFont)

        # --- Widgets ---
        self.family_box = QFontComboBox(self)
        self.family_box.setEditable(False)
        self.family_box.setToolTip("Font family")

        self.size_box = QComboBox(self)
        self.size_box.setEditable(True)
        self.size_box.setInsertPolicy(QComboBox.NoInsert)
        self.size_box.setToolTip("Font size (accepts 12, 12pt, 16px, 4.2mm, etc.)")
        # sensible point sizes
        for n in (4,5,6,7,8,9,10,11,12,13,14,15,16,18,20,22,24,28,32,36,48,60,72,112,144,256):
            self.size_box.addItem(str(n))

        self.bold_btn = QToolButton(self)
        self.bold_btn.setCheckable(True)
        self.bold_btn.setText("B")
        self.bold_btn.setToolTip("Bold")
        bf = QFont(self.bold_btn.font())
        bf.setBold(True)
        self.bold_btn.setFont(bf)

        self.italic_btn = QToolButton(self)
        self.italic_btn.setCheckable(True)
        self.italic_btn.setText("I")
        self.italic_btn.setToolTip("Italic")
        itf = QFont(self.italic_btn.font())
        itf.setItalic(True)
        self.italic_btn.setFont(itf)

        self.underline_btn = QToolButton(self)
        self.underline_btn.setCheckable(True)
        self.underline_btn.setText("U")
        self.underline_btn.setToolTip("Underline")
        uf = QFont(self.underline_btn.font())
        uf.setUnderline(True)
        self.underline_btn.setFont(uf)

       # --- Alignment Buttons ---
        self.h_left_btn = QToolButton(self); self.h_left_btn.setCheckable(True); self.h_left_btn.setIcon(QIcon.fromTheme("format-justify-left")); self.h_left_btn.setToolTip("Align Left")
        self.h_center_btn = QToolButton(self); self.h_center_btn.setCheckable(True); self.h_center_btn.setIcon(QIcon.fromTheme("format-justify-center")); self.h_center_btn.setToolTip("Align Center")
        self.h_right_btn = QToolButton(self); self.h_right_btn.setCheckable(True); self.h_right_btn.setIcon(QIcon.fromTheme("format-justify-right")); self.h_right_btn.setToolTip("Align Right")
        self.h_justified_btn = QToolButton(self); self.h_justified_btn.setCheckable(True); self.h_justified_btn.setIcon(QIcon.fromTheme("format-justify-fill")); self.h_justified_btn.setToolTip("Align Justified")

        self.v_top_btn = QToolButton(self); self.v_top_btn.setCheckable(True); self.v_top_btn.setText("⭱"); self.v_top_btn.setToolTip("Align Top")
        self.v_middle_btn = QToolButton(self); self.v_middle_btn.setCheckable(True); self.v_middle_btn.setText("⇵"); self.v_middle_btn.setToolTip("Align Middle")
        self.v_bottom_btn = QToolButton(self); self.v_bottom_btn.setCheckable(True); self.v_bottom_btn.setText("⭳"); self.v_bottom_btn.setToolTip("Align Bottom")

        # Grouping
        self.h_group = QButtonGroup(self); self.h_group.setExclusive(True)
        self.h_group.addButton(self.h_left_btn); self.h_group.addButton(self.h_center_btn); self.h_group.addButton(self.h_justified_btn), self.h_group.addButton(self.h_right_btn)

        self.v_group = QButtonGroup(self); self.v_group.setExclusive(True)
        self.v_group.addButton(self.v_top_btn); self.v_group.addButton(self.v_middle_btn); self.v_group.addButton(self.v_bottom_btn)


        # --- Top Row: Font controls ---
        font_row = QHBoxLayout()
        font_row.setContentsMargins(0, 0, 0, 0)
        font_row.setSpacing(3)
        font_row.addWidget(self.family_box, stretch=1)
        font_row.addWidget(self.size_box, stretch=0)


        # --- Bottom Row: Alignment controls ---
        align_row = QHBoxLayout()
        align_row.setContentsMargins(0, 0, 0, 0)
        align_row.setSpacing(3)
        align_row.addWidget(self.bold_btn, stretch=0)
        align_row.addWidget(self.italic_btn, stretch=0)
        align_row.addWidget(self.underline_btn, stretch=0)
        align_row.addSpacing(10)   # spacer between H and V groups
        align_row.addWidget(self.h_left_btn, 0)
        align_row.addWidget(self.h_center_btn, 0)
        align_row.addWidget(self.h_justified_btn, 0)
        align_row.addWidget(self.h_right_btn, 0)
        align_row.addSpacing(10)   # spacer between H and V groups
        align_row.addWidget(self.v_top_btn, 0)
        align_row.addWidget(self.v_middle_btn, 0)
        align_row.addWidget(self.v_bottom_btn, 0)
        align_row.addStretch(1)

        # --- Master layout ---
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        lay.addLayout(font_row)
        lay.addLayout(align_row)
        self.setLayout(lay)

        # --- Wire signals ---
        self.family_box.currentFontChanged.connect(self._on_any_change)
        self.size_box.editTextChanged.connect(self._on_any_change)
        self.size_box.activated.connect(self._on_any_change)
        self.bold_btn.toggled.connect(self._on_any_change)
        self.italic_btn.toggled.connect(self._on_any_change)
        self.underline_btn.toggled.connect(self._on_any_change)
        self.h_group.buttonToggled.connect(self._on_halign_change)
        self.v_group.buttonToggled.connect(self._on_valign_change)

       # NEW: coalescing timer
        self._emit_timer = QTimer(self)
        self._emit_timer.setSingleShot(True)
        self._emit_timer.setInterval(60)  # small debounce
        self._emit_timer.timeout.connect(self._flush_font_emit)
        self._pending = None  # (target, "font", new, old)

    # ---------- Public API ----------

    def setTarget(self, target: Optional[object]) -> None:
        """
        Bind the toolbar to a ComponentElement-like object exposing .font: UnitStrFont.
        """
        self._target = target
        self._sync_from_target()

    def target(self) -> Optional[object]:
        return self._target

    def set_font(self, usf: UnitStrFont) -> None:
        """
        Programmatically update controls from a UnitStrFont (without emitting).
        """
        if self._target is None:
            # still update UI from the given font so the toolbar reflects the font
            self._sync_from_usf(usf)
        else:
            self._sync_from_target()

    # ---------- Internals ----------

    def _sync_from_target(self) -> None:
        if not self._target or not hasattr(self._target, "font"):
            return
        usf = getattr(self._target, "font")
        if not isinstance(usf, UnitStrFont):
            try:
                usf = UnitStrFont(usf)
            except Exception:
                return
        self._sync_from_usf(usf)

    def _sync_from_usf(self, usf: UnitStrFont) -> None:
        self._updating = True
        try:
            # Family
            self.family_box.setCurrentFont(QFont(usf.family))

            # Size: show points by default
            pt_size = usf.size.to("pt", dpi=usf.dpi).value
            # Avoid overly long float strings
            disp = f"{pt_size:.2f}".rstrip("0").rstrip(".")
            self.size_box.setEditText(disp)

            # Style buttons
            is_bold = int(usf.weight) >= int(QFont.Weight.Bold)
            self.bold_btn.setChecked(bool(is_bold))
            self.italic_btn.setChecked(bool(usf.italic))
            self.underline_btn.setChecked(bool(usf.underline))
        finally:
            self._updating = False

    def _parse_size_text(self, txt: str, *, dpi: float) -> UnitStr:
        """
        Parse the size entry. If unitless, default to points.
        Accepts '12', '12pt', '16px', '4.2mm', etc.
        """
        s = (txt or "").strip()
        if not s:
            # fallback to 12pt
            return UnitStr(12, unit="pt", dpi=dpi)
        # If it contains any letters, let UnitStr auto-detect
        if any(c.isalpha() for c in s):
            return UnitStr(s, dpi=dpi)
        # pure number -> points by default for fonts
        try:
            val = float(s)
        except Exception:
            val = 12.0
        return UnitStr(val, unit="pt", dpi=dpi)

    def _build_usf_from_ui(self, base: UnitStrFont) -> UnitStrFont:
        """
        Construct a new UnitStrFont from current UI controls, starting from 'base' to preserve fields we don't expose.
        """
        family = self.family_box.currentFont().family()
        size_us = self._parse_size_text(self.size_box.currentText(), dpi=base.dpi if base.dpi else self._default_dpi)
        weight = QFont.Weight.Bold if self.bold_btn.isChecked() else QFont.Weight.Normal
        italic = self.italic_btn.isChecked()
        underline = self.underline_btn.isChecked()
        print(f"New family set to {family}")

        # Use with_overrides to keep other attributes (fallbacks, kerning, etc.)
        return base.with_overrides(
            family=family,
            size=size_us,
            weight=int(weight),
            italic=bool(italic),
            underline=bool(underline),
        )

    @Slot()
    def _on_halign_change(self, btn, checked: bool):
        if not checked or not self._target: return
        old = getattr(self._target, "h_align", Qt.AlignLeft)
        new = {self.h_left_btn:"Left", self.h_center_btn:"Center", self.h_justified_btn: "Justify", self.h_right_btn:"Right"}[btn]
        new_align = HMAP.get(new)
        if new != old:
            self.hAlignChanged.emit(self._target, "h_align", new_align, old)

    @Slot()
    def _on_valign_change(self, btn, checked: bool):
        if not checked or not self._target: return
        old = getattr(self._target, "v_align", Qt.AlignTop)
        new = {self.v_top_btn:"Top", self.v_middle_btn:"Middle", self.v_bottom_btn:"Bottom"}[btn]
        new_align = VMAP.get(new)
        if new != old:
            self.vAlignChanged.emit(self._target, "v_align", new_align, old)


    @Slot()
    def _on_any_change(self) -> None:
        if self._updating or not self._target or not hasattr(self._target, "font"):
            return

        old = getattr(self._target, "font")
        try:
            if not isinstance(old, UnitStrFont):
                old = UnitStrFont(old)  # coerce if needed
        except Exception:
            return

        new = self._build_usf_from_ui(old)
        if new == old:
            return

        # DO NOT set the target here
        # setattr(self._target, "font", new)  # <- remove this

        # Coalesce into one emit
        self._pending = (self._target, "font", new, old)
        self._emit_timer.start()  # restart if already running

    def _flush_font_emit(self):
        if not self._pending:
            return
        tgt, prop, new, old = self._pending
        self._pending = None
        # Now emit exactly once per burst
        self.fontChanged.emit(tgt, "font", new, old)
