# pkeysequence.py
import sys
from typing import Optional, Union, Iterable, List
from PySide6.QtGui import QKeySequence, QAction
from PySide6.QtCore import Qt

KeySpec = Union[int, str]
KeySpecOrList = Union[KeySpec, Iterable[KeySpec]]

def _as_list(spec):
    if spec is None:
        return []
    if isinstance(spec, (list, tuple)):
        return list(spec)
    return [spec]

# ----------------- Key Aliasing & Resolution -----------------
class _KeyResolver:
    """Platform-aware aliases for modifiers and common keys."""

    @property
    def Cmd(self) -> int:
        """Cmd on macOS (Meta), Ctrl elsewhere."""
        return Qt.MetaModifier if sys.platform.startswith("darwin") else Qt.ControlModifier

    # If you ever need the actual Windows/Super key on non-mac:
    @property
    def Super(self) -> int:
        """Always the Meta/Super/Windows modifier on every platform."""
        return Qt.MetaModifier

    @property
    def Ctrl(self) -> int:  return Qt.ControlModifier
    @property
    def Meta(self) -> int:  return Qt.MetaModifier
    @property
    def Alt(self) -> int:   return Qt.AltModifier
    @property
    def Shift(self) -> int: return Qt.ShiftModifier

    #Alphanumeric Keys
	A = Qt.Key_A
	B = Qt.Key_B
	C = Qt.Key_C
	D = Qt.Key_D
	E = Qt.Key_E
	F = Qt.Key_F
	G = Qt.Key_G
	H = Qt.Key_H
	I = Qt.Key_I
	J = Qt.Key_J
	K = Qt.Key_K
	L = Qt.Key_L
	M = Qt.Key_M
	N = Qt.Key_N
	O = Qt.Key_O
	P = Qt.Key_P
	Q = Qt.Key_Q
	R = Qt.Key_R
	S = Qt.Key_S
	T = Qt.Key_T
	U = Qt.Key_U
	V = Qt.Key_V
	W = Qt.Key_W
	X = Qt.Key_X
	Y = Qt.Key_Y
	Z = Qt.Key_Z

	N0 = Qt.Key_0
	N1 = Qt.Key_1
	N2 = Qt.Key_2
	N3 = Qt.Key_3
	N4 = Qt.Key_4
	N5 = Qt.Key_5
	N6 = Qt.Key_6
	N7 = Qt.Key_7
	N8 = Qt.Key_8
	N9 = Qt.Key_9

    # Other Non-modifier keys
    Backspace 	= Qt.Key_Backspace
    Delete    	= Qt.Key_Delete
    Return    	= Qt.Key_Return       # Main Enter
    Enter     	= Qt.Key_Enter        # Keypad Enter
    Escape    	= Qt.Key_Escape
    Tab       	= Qt.Key_Tab
    Space    	= Qt.Key_Space
	Exclam 		= Qt.Key_Exclam
	QuoteDbl 	= Qt.Key_QuoteDbl
	NumberSign 	= Qt.Key_NumberSign
	Dollar 		= Qt.Key_Dollar
	Percent 	= Qt.Key_Percent
	Ampersand 	= Qt.Key_Ampersand
	Apostrophe 	= Qt.Key_Apostrophe
	ParenLeft 	= Qt.Key_ParenLeft
	ParenRight 	= Qt.Key_ParenRight
	Asterisk 	= Qt.Key_Asterisk
	Plus 		= Qt.Key_Plus
	Comma 		= Qt.Key_Comma
	Minus 		= Qt.Key_Minus
	Period 		= Qt.Key_Period
	Slash 		= Qt.Key_Slash
	Colon 		= Qt.Key_Colon
	Semicolon 	= Qt.Key_Semicolon
	Less 		= Qt.Key_Less
	Equal 		= Qt.Key_Equal
	Greater 	= Qt.Key_Greater
	Question 	= Qt.Key_Question
	At 			= Qt.Key_At
	BracketLeft = Qt.Key_BracketLeft
	Backslash 	= Qt.Key_Backslash
	BracketRight= Qt.Key_BracketRight
	AsciiCircum = Qt.Key_AsciiCircum
	Underscore 	= Qt.Key_Underscore
	QuoteLeft 	= Qt.Key_QuoteLeft
	BraceLeft 	= Qt.Key_BraceLeft
	Bar 		= Qt.Key_Bar
	BraceRight 	= Qt.Key_BraceRight
	AsciiTilde 	= Qt.Key_AsciiTilde

	# Navigation and Special Keys
	Home 		= Qt.Key_Home
	End 		= Qt.Key_End
	PageUp 		= Qt.Key_PageUp
	PageDown 	= Qt.Key_PageDown
	Left 		= Qt.Key_Left
	Up 			= Qt.Key_Up
	Right 		= Qt.Key_Right
	Down 		= Qt.Key_Down
	Escape 		= Qt.Key_Escape
	Tab 		= Qt.Key_Tab
	Backtab 	= Qt.Key_Backtab

	Insert 		= Qt.Key_Insert
	Delete 		= Qt.Key_Delete

    # Function keys
    F1 = Qt.Key_F1;  F2 = Qt.Key_F2;   F3 = Qt.Key_F3;   F4 = Qt.Key_F4
    F5 = Qt.Key_F5;  F6 = Qt.Key_F6;   F7 = Qt.Key_F7;   F8 = Qt.Key_F8
    F9 = Qt.Key_F9;  F10 = Qt.Key_F10; F11 = Qt.Key_F11; F12 = Qt.Key_F12

Key = _KeyResolver()

class _Alias:
    """Descriptor: returns QKeySequence or List[QKeySequence] on attribute access."""
    def __init__(
        self,
        *,
        mac: Optional[KeySpecOrList] = None,
        windows: Optional[KeySpecOrList] = None,
        linux: Optional[KeySpecOrList] = None,
        other: Optional[KeySpecOrList] = None,
        many: bool = False,
    ) -> None:
        self.mac = _as_list(mac)
        self.windows = _as_list(windows)
        self.linux = _as_list(linux)
        self.other = _as_list(other)
        self.many = many

    def __get__(self, obj, owner):
        plat = _plat()
        chosen: List[KeySpec] = []
        if   plat == "mac":     chosen = self.mac
        elif plat == "windows": chosen = self.windows
        elif plat == "linux":   chosen = self.linux
        if not chosen:
            chosen = self.other
        # Build QKeySequence(s)
        seqs = [QKeySequence(s) for s in chosen]
        if self.many:
            return seqs
        return seqs[0] if seqs else QKeySequence()

# ----------------- PKeySequence (single) -----------------
class PKeySequence(QKeySequence):
    """
    Platform-selecting QKeySequence factory:
        seq = PKeySequence(mac=Key.Cmd|Key.Backspace, other=Key.Ctrl|Key.Delete)
    Returns a QKeySequence instance via __new__.
    """
    RemoveItem = _Alias(
        mac=Key.Meta | Key.Delete,
        windows=Key.Super | Key.Backspace,
        other=Key.Meta | Key.Backspace,
    )
    AddItem = _Alias(
        mac=Key.Meta | Key.Shift | Key.Plus,
        windows=Key.Super | Key.Backspace,
        other=Key.Meta | Key.Backspace,
    )

    def __new__(
        cls,
        mac: Optional[Union[int, str]] = None,
        other: Optional[Union[int, str]] = None,
        windows: Optional[Union[int, str]] = None,
        linux: Optional[Union[int, str]] = None
    ) -> QKeySequence:
        p = sys.platform
        key_spec: Optional[Union[int, str]] = None

        if p.startswith("darwin"):
            key_spec = mac
        elif p.startswith("win"):
            key_spec = windows if windows is not None else None
        elif p.startswith(("linux", "freebsd", "openbsd", "netbsd")):
            key_spec = linux if linux is not None else None

        if key_spec is None:
            key_spec = other

        return QKeySequence(key_spec) if key_spec is not None else QKeySequence()

# ----------------- Helper for multiple shortcuts ----------

def PKeySequences(
    *,
    mac: Optional[Iterable[Union[int, str]]] = None,
    other: Optional[Iterable[Union[int, str]]] = None,
    windows: Optional[Iterable[Union[int, str]]] = None,
    linux: Optional[Iterable[Union[int, str]]] = None,
) -> List[QKeySequence]:
    """
    Resolve a platform-specific LIST of shortcuts.
    Example:
        seqs = PKeySequences(
            mac=[Key.Cmd|Key.Backspace, Key.Cmd|Key.Delete],
            other=[Key.Ctrl|Key.Delete]
        )
        action.setShortcuts(seqs)
    """
    p = sys.platform
    chosen: Optional[Iterable[Union[int, str]]] = None

    if p.startswith("darwin"):
        chosen = mac
    elif p.startswith("win"):
        chosen = windows
    elif p.startswith(("linux", "freebsd", "openbsd", "netbsd")):
        chosen = linux

    if not chosen:
        chosen = other

    return [QKeySequence(spec) for spec in chosen] if chosen else []

# ----------------- Example usage -----------------
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)
    win = QMainWindow()

    def on_delete():
        print("Delete triggered")

    act = QAction("Delete Item", win)
    act.triggered.connect(on_delete)

    # If you want BOTH Meta+Backspace and Meta+Delete:
    act.setShortcuts(PKeySequences(
        mac=[Key.Cmd | Key.Backspace, Key.Cmd | Key.Delete],
        # If you want Ctrl variants elsewhere:
        other=[Key.Ctrl | Key.Delete, Key.Ctrl | Key.Backspace],
        # Or if you prefer actual Super/Windows key elsewhere:
        # other=[Key.Super | Key.Backspace, Key.Super | Key.Delete],
    ))

    win.menuBar().addMenu("&Edit").addAction(act)
    win.show()
    sys.exit(app.exec())
