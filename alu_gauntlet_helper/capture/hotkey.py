import keyboard


class GlobalHotkeyService:
    """Глобальні хоткеї (lib keyboard). Колбеки викликаються у потоці keyboard —
    хто підписується, відповідає за перехід у UI-потік (Qt signal)."""

    def __init__(self):
        self._handles: list[object] = []
        self._hooks: list[object] = []

    def register(self, combo: str, callback, trigger_on_release: bool = False) -> bool:
        try:
            self._handles.append(keyboard.add_hotkey(combo, callback, trigger_on_release=trigger_on_release))
            return True
        except Exception as e:
            print(f"Failed to register hotkey '{combo}': {e}")
            return False

    def register_hold(self, keys: list[str], on_press, on_release) -> bool:
        """Викликає on_press, коли ВСІ keys затиснуті одночасно, і on_release,
        коли відпущено хоч одну. Надійніше за add_hotkey(trigger_on_release=True)
        для комбінацій лише з модифікаторів."""
        state = {"active": False}

        def handler(_event):
            active = all(keyboard.is_pressed(k) for k in keys)
            if active and not state["active"]:
                state["active"] = True
                on_press()
            elif not active and state["active"]:
                state["active"] = False
                on_release()

        try:
            self._hooks.append(keyboard.hook(handler))
            return True
        except Exception as e:
            print(f"Failed to register hold '{'+'.join(keys)}': {e}")
            return False

    def unregister_all(self):
        for handle in self._handles:
            try:
                keyboard.remove_hotkey(handle)
            except Exception:
                pass
        for hook in self._hooks:
            try:
                keyboard.unhook(hook)
            except Exception:
                pass
        self._handles = []
        self._hooks = []
