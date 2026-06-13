from typing import Callable


class Observable:
    """Мінімальне джерело подій: слухачі без аргументів, лінива ініціалізація списку.

    Сервіс наслідує цей міксин і викликає self._notify() після мутації даних —
    UI підписується через add_listener, щоб знати, коли треба перебудуватись."""

    def add_listener(self, listener: Callable[[], None]):
        try:
            self._listeners.append(listener)
        except AttributeError:
            self._listeners = [listener]

    def remove_listener(self, listener: Callable[[], None]):
        listeners = getattr(self, "_listeners", None)
        if listeners and listener in listeners:
            listeners.remove(listener)

    def _notify(self):
        for listener in list(getattr(self, "_listeners", ())):
            listener()
