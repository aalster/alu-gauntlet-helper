"""Локалізація ІНТЕРФЕЙСУ застосунку (UI-рядки) між English та Українською.

Окремий механізм від game_lang (мова КОНТЕНТУ гри — назви карт/треків).
Назви авто завжди англійською. На відміну від game_lang, тут немає
live-перемикання: мова застосовується на старті, зміна потребує перезапуску.
"""

EN = "en"
UK = "uk"

_language = EN

TRANSLATIONS = {
    "en": {
        # main window / tabs / tray
        "window.title": "ALU Gauntlet Helper",
        "tab.capture": "CAPTURE",
        "tab.car_selection": "CAR SELECTION",
        "tab.races": "RACES",
        "tab.cars": "CARS",
        "tab.tracks": "TRACKS",
        "tab.settings": "SETTINGS",
        "tray.open": "Open",
        "tray.quit": "Quit",
        # common / shared field labels
        "common.add": "Add",
        "common.edit": "Edit",
        "common.images_filter": "Images (*.png *.jpg *.jpeg *.bmp)",
        "field.track": "Track",
        "field.car": "Car",
        "field.rank": "Rank",
        "field.time": "Time",
        "field.note": "Note",
        "field.name": "Name",
        "field.name_ru": "Name (RU)",
        "field.icon": "Icon",
        "field.map": "Map",
        "field.brand": "Brand",
        "field.model": "Model",
        # dialogs (edit/add titles + buttons)
        "dialog.ok": "Ok",
        "dialog.cancel": "Cancel",
        "dialog.edit_race": "Edit Race",
        "dialog.add_race": "Add Race",
        "dialog.edit_map": "Edit Map",
        "dialog.add_map": "Add Map",
        "dialog.edit_track": "Edit Track",
        "dialog.add_track": "Add Track",
        "dialog.edit_car": "Edit Car",
        "dialog.add_car": "Add Car",
        # settings
        "settings.app_language": "Application language",
        "settings.app_language_hint": "Language changes apply after restart",
        "settings.game_language": "Game language",
        "settings.show_tray": "Show tray icon",
        "settings.close_to_tray": "Close to tray",
        "settings.start_minimized": "Start minimized",
        "settings.save_captures": "Save screenshots of unrecognized / low-confidence captures (data/captures)",
        "settings.open_folder": "Open folder",
        "settings.capture_hotkey": "Capture hotkey",
        "settings.overlay_hotkey": "Overlay hotkey",
        "settings.overlay_actions": "Overlay actions",
        "settings.overlay_opacity": "Overlay opacity",
        "settings.capture_monitor": "Capture monitor",
        "settings.monitor_btn": "Monitor {index}\n{width}×{height}",
        "settings.save": "Save",
        "settings.saved": "Saved.",
        "settings.hotkey_failed": "Hotkey could not be registered — try another key",
        # races
        "races.bad_timing": "Bad timing",
        # cars
        "cars.max": "MAX",
        "cars.filter_all": "All",
        "cars.sort_default": "Default",
        "cars.sort_max_rank": "Max Rank",
        "cars.sort_order": "Sort order",
        # capture
        "capture.low_conf_warning": "Some fields were recognized with low confidence — review the marked rows before saving.",
        "capture.load_screenshot": "Load screenshot",
        "capture.capture_screen": "Capture Screen ({hotkey})",
        "capture.toggle_overlay": "Toggle Overlay ({hotkey})",
        "capture.save_selected": "Save selected",
        "capture.edit_race_n": "Edit Race {n}",
        "capture.discard_session": "Discard session",
        "capture.save_failed": "Save failed",
        "capture.discard_confirm": "Discard all captured races?",
        # car selection
        "car_selection.race_history": "Race History — {name}",
        "car_selection.race_n": "Race {n}",
        "car_selection.select_track_placeholder": "Select track...",
        "car_selection.select_track": "Select a track",
        "car_selection.no_data": "No race data",
        "car_selection.rank_n": "Rank {n}",
        "car_selection.class_x": "Class {c}",
        "car_selection.rank_label": "Rank: {n}",
        "car_selection.races_count": "{n} races",
        # overlay
        "overlay.no_data": "no data",
        "overlay.capture": "Capture",
        "overlay.save": "Save",
        "overlay.drag_tooltip": "Drag to move the overlay",
        "overlay.hide_tooltip": "Hide overlay",
        "overlay.capture_tooltip": "Capture the screen",
        "overlay.save_tooltip": "Save marked races",
        "overlay.hint": "{capture} capture · {hide} hide · {combo} actions",
        # capture statuses (overlay + capture tab)
        "status.screenshot_failed": "Screenshot failed",
        "status.load_failed": "Failed to load screenshot",
        "status.not_recognized": "Screen not recognized",
        "status.recognizing": "Recognizing",
        "status.recognizing_n": "Recognizing ({n})",
        "status.done": "Done — review in the app",
        # image line edit
        "image.clear": "Clear",
        "image.choose_file": "Choose file",
        "image.paste": "Paste from clipboard",
        "image.choose_image": "Choose Image",
    },
    "uk": {
        "window.title": "ALU Gauntlet Helper",
        "tab.capture": "ЗАХОПЛЕННЯ",
        "tab.car_selection": "ВИБІР АВТО",
        "tab.races": "ЗАЇЗДИ",
        "tab.cars": "АВТО",
        "tab.tracks": "ТРЕКИ",
        "tab.settings": "НАЛАШТУВАННЯ",
        "tray.open": "Відкрити",
        "tray.quit": "Вийти",
        "common.add": "Додати",
        "common.edit": "Редагувати",
        "common.images_filter": "Зображення (*.png *.jpg *.jpeg *.bmp)",
        "field.track": "Трек",
        "field.car": "Авто",
        "field.rank": "Ранг",
        "field.time": "Час",
        "field.note": "Нотатка",
        "field.name": "Назва",
        "field.name_ru": "Назва (RU)",
        "field.icon": "Іконка",
        "field.map": "Карта",
        "field.brand": "Бренд",
        "field.model": "Модель",
        "dialog.ok": "Гаразд",
        "dialog.cancel": "Скасувати",
        "dialog.edit_race": "Редагувати заїзд",
        "dialog.add_race": "Додати заїзд",
        "dialog.edit_map": "Редагувати карту",
        "dialog.add_map": "Додати карту",
        "dialog.edit_track": "Редагувати трек",
        "dialog.add_track": "Додати трек",
        "dialog.edit_car": "Редагувати авто",
        "dialog.add_car": "Додати авто",
        "settings.app_language": "Мова застосунку",
        "settings.app_language_hint": "Зміни мови застосуються після перезапуску",
        "settings.game_language": "Мова гри",
        "settings.show_tray": "Показувати іконку в треї",
        "settings.close_to_tray": "Згортати в трей при закритті",
        "settings.start_minimized": "Запускати згорнутим",
        "settings.save_captures": "Зберігати скріншоти нерозпізнаних / невпевнених захоплень (data/captures)",
        "settings.open_folder": "Відкрити теку",
        "settings.capture_hotkey": "Хоткей захоплення",
        "settings.overlay_hotkey": "Хоткей оверлея",
        "settings.overlay_actions": "Керування оверлеєм",
        "settings.overlay_opacity": "Непрозорість оверлея",
        "settings.capture_monitor": "Монітор захоплення",
        "settings.monitor_btn": "Монітор {index}\n{width}×{height}",
        "settings.save": "Зберегти",
        "settings.saved": "Збережено.",
        "settings.hotkey_failed": "Хоткей не зареєструвався — спробуй іншу клавішу",
        "races.bad_timing": "Некоректний час",
        "cars.max": "МАКС",
        "cars.filter_all": "Усі",
        "cars.sort_default": "За замовч.",
        "cars.sort_max_rank": "Макс. ранг",
        "cars.sort_order": "Порядок сортування",
        "capture.low_conf_warning": "Деякі поля розпізнані з низькою впевненістю — перевірте позначені рядки перед збереженням.",
        "capture.load_screenshot": "Завантажити скріншот",
        "capture.capture_screen": "Захопити екран ({hotkey})",
        "capture.toggle_overlay": "Перемкнути оверлей ({hotkey})",
        "capture.save_selected": "Зберегти вибране",
        "capture.edit_race_n": "Редагувати заїзд {n}",
        "capture.discard_session": "Скасувати сесію",
        "capture.save_failed": "Не вдалося зберегти",
        "capture.discard_confirm": "Скасувати всі захоплені заїзди?",
        "car_selection.race_history": "Історія заїздів — {name}",
        "car_selection.race_n": "Заїзд {n}",
        "car_selection.select_track_placeholder": "Оберіть трек...",
        "car_selection.select_track": "Оберіть трек",
        "car_selection.no_data": "Немає даних про заїзди",
        "car_selection.rank_n": "Ранг {n}",
        "car_selection.class_x": "Клас {c}",
        "car_selection.rank_label": "Ранг: {n}",
        "car_selection.races_count": "{n} заїздів",
        "overlay.no_data": "немає даних",
        "overlay.capture": "Захопити",
        "overlay.save": "Зберегти",
        "overlay.drag_tooltip": "Перетягніть, щоб перемістити оверлей",
        "overlay.hide_tooltip": "Сховати оверлей",
        "overlay.capture_tooltip": "Зробити захоплення екрана",
        "overlay.save_tooltip": "Зберегти відмічені гонки",
        "overlay.hint": "{capture} захоплення · {hide} сховати · {combo} дії",
        "status.screenshot_failed": "Не вдалося зробити скріншот",
        "status.load_failed": "Не вдалося завантажити скріншот",
        "status.not_recognized": "Екран не розпізнано",
        "status.recognizing": "Розпізнавання",
        "status.recognizing_n": "Розпізнавання ({n})",
        "status.done": "Готово — перегляньте в застосунку",
        "image.clear": "Очистити",
        "image.choose_file": "Обрати файл",
        "image.paste": "Вставити з буфера",
        "image.choose_image": "Обрати зображення",
    },
}


def set_ui_language(language: str) -> None:
    global _language
    _language = UK if language == UK else EN


def current_ui_language() -> str:
    return _language


def t(key: str) -> str:
    """Рядок поточної мови; фолбек: поточна → en → сам ключ."""
    current = TRANSLATIONS.get(_language, {})
    if key in current:
        return current[key]
    return TRANSLATIONS["en"].get(key, key)


def system_to_ui_language(locale_name: str) -> str:
    """OS-локаль (напр. 'uk_UA') → мова UI. uk/ru → uk, інакше en."""
    code = (locale_name or "").lower()[:2]
    return UK if code in ("uk", "ru") else EN
