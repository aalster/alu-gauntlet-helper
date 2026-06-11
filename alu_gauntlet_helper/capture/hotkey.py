import keyboard


class GlobalHotkeyService:
    """Глобальні хоткеї (lib keyboard). Колбеки викликаються у потоці keyboard —
    хто підписується, відповідає за перехід у UI-потік (Qt signal)."""

    def __init__(self):
        self._handles: list[object] = []

    def register(self, combo: str, callback) -> bool:
        try:
            self._handles.append(keyboard.add_hotkey(combo, callback))
            return True
        except Exception as e:
            print(f"Failed to register hotkey '{combo}': {e}")
            return False

    def unregister_all(self):
        for handle in self._handles:
            try:
                keyboard.remove_hotkey(handle)
            except Exception:
                pass
        self._handles = []
