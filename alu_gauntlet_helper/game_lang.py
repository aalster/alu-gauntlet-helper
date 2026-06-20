"""Локалізація КОНТЕНТУ гри (назви карт/треків) між мовами інтерфейсу гри.

Це окремий механізм від (майбутньої) мови застосунку: тут лише вибір, якою
мовою показувати назви, що приходять з гри. Тримаємо мову в процес-глобальній
змінній без важких імпортів, щоб моделі/сервіси могли локалізувати назви без
циклічних залежностей з AppContext.
"""

EN = "en"
RU = "ru"

_language = EN
# слухачі зміни мови: для вкладок, що не перебудовуються при кожному refresh
# (напр. RacesTab з його _dirty-оптимізацією) — зміна мови це не мутація даних
_listeners = []


def add_listener(callback) -> None:
    if callback not in _listeners:
        _listeners.append(callback)


def set_game_language(language: str) -> None:
    global _language
    new_language = RU if language == RU else EN
    if new_language == _language:
        return
    _language = new_language
    for callback in list(_listeners):
        callback()


def current_game_language() -> str:
    return _language


def localize(en: str, ru: str) -> str:
    """Назва для показу: рос. лише коли мова RU і переклад заданий, інакше англ."""
    return ru if (_language == RU and ru) else en
