from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFocusEvent, QKeyEvent
from PyQt6.QtWidgets import QLineEdit

# Клавіші-модифікатори (самі по собі не утворюють комбінацію)
_MODIFIER_KEYS = {
    Qt.Key.Key_Control,
    Qt.Key.Key_Shift,
    Qt.Key.Key_Alt,
    Qt.Key.Key_Meta,
    Qt.Key.Key_AltGr,
}

# Клавіші, які не можна призначати хоткеєм за жодних умов
_FORBIDDEN_KEYS = {
    Qt.Key.Key_Space,
    Qt.Key.Key_Return,
    Qt.Key.Key_Enter,
    Qt.Key.Key_Tab,
    Qt.Key.Key_Backspace,
    Qt.Key.Key_CapsLock,
    Qt.Key.Key_NumLock,
    Qt.Key.Key_ScrollLock,
    Qt.Key.Key_Print,  # Print Screen — перехоплюється системою
}

# Спецклавіші → назви у форматі бібліотеки keyboard
_SPECIAL_KEYS = {
    Qt.Key.Key_Space: "space",
    Qt.Key.Key_Return: "enter",
    Qt.Key.Key_Enter: "enter",
    Qt.Key.Key_Tab: "tab",
    Qt.Key.Key_Backspace: "backspace",
    Qt.Key.Key_Delete: "delete",
    Qt.Key.Key_Insert: "insert",
    Qt.Key.Key_Home: "home",
    Qt.Key.Key_End: "end",
    Qt.Key.Key_PageUp: "page up",
    Qt.Key.Key_PageDown: "page down",
    Qt.Key.Key_Up: "up",
    Qt.Key.Key_Down: "down",
    Qt.Key.Key_Left: "left",
    Qt.Key.Key_Right: "right",
    Qt.Key.Key_Print: "print screen",
    Qt.Key.Key_Pause: "pause",
    Qt.Key.Key_CapsLock: "caps lock",
}


def _modifiers(mods: Qt.KeyboardModifier) -> list[str]:
    result: list[str] = []
    if mods & Qt.KeyboardModifier.ControlModifier:
        result.append("ctrl")
    if mods & Qt.KeyboardModifier.AltModifier:
        result.append("alt")
    if mods & Qt.KeyboardModifier.ShiftModifier:
        result.append("shift")
    if mods & Qt.KeyboardModifier.MetaModifier:
        result.append("windows")
    return result


def _key_name(event: QKeyEvent) -> str | None:
    key = event.key()
    if key in _SPECIAL_KEYS:
        return _SPECIAL_KEYS[key]
    if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F35:
        return f"f{key - Qt.Key.Key_F1 + 1}"
    if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
        return chr(key).lower()
    if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        return chr(key)
    text = event.text()
    if text and text.isprintable() and not text.isspace():
        return text.lower()
    return None


class HotkeyEdit(QLineEdit):
    """Поле для введення глобального хоткея натисканням комбінації клавіш.
    Зберігає значення у форматі бібліотеки keyboard (напр. "ctrl+shift+f8")."""

    def __init__(self, value: str = ""):
        super().__init__()
        self._value = value
        self._captured = False
        self.setReadOnly(True)
        self.setText(value)

    def value(self) -> str:
        return self._value

    def set_value(self, value: str):
        self._value = value
        self.setText(value)

    def focusInEvent(self, event: QFocusEvent):
        super().focusInEvent(event)
        self._captured = False
        self.setText("")
        self.setPlaceholderText("Натисніть комбінацію…")

    def focusOutEvent(self, event: QFocusEvent):
        # Якщо вийшли без захопленої комбінації — відновлюємо попереднє значення
        if not self._captured:
            self.setText(self._value)
        self.setPlaceholderText("")
        super().focusOutEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.isAutoRepeat():
            return

        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.clearFocus()
            return

        mods = _modifiers(event.modifiers())

        if key in _MODIFIER_KEYS:
            # Проміжний показ затиснутих модифікаторів
            self.setText("+".join(mods + ["…"]))
            return

        if key in _FORBIDDEN_KEYS:
            self.setText("Ця клавіша недоступна")
            return

        name = _key_name(event)
        if name is None:
            return

        # Без модифікатора дозволені лише функціональні клавіші (F1–F35)
        is_function = Qt.Key.Key_F1 <= key <= Qt.Key.Key_F35
        if not mods and not is_function:
            self.setText("Потрібен модифікатор (Ctrl/Alt/Shift)")
            return

        combo = "+".join(mods + [name])
        self._value = combo
        self._captured = True
        self.setText(combo)
        self.clearFocus()
