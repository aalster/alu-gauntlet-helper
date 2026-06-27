# UI Language (Eng/Ukr) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an application-UI language setting (English / Ukrainian) independent of the existing game-content language.

**Architecture:** A new lightweight `ui_lang` module (a translation dict + `t(key)` lookup), mirroring the existing `game_lang` module but **without** live re-translation — the UI language is applied once at startup and changing it requires a restart. A new `app_language` settings field (empty = auto-detect from system locale on first run). All visible view literals are routed through `t()`.

**Tech Stack:** Python 3.9+, PyQt6, Pydantic, pytest.

## Global Constraints

- UI language values: `"en"` | `"uk"`. Settings field `app_language` default `""` (empty = not yet determined → triggers first-run auto-detect).
- Game-content language (`game_language`, `en`/`ru`) and car names are **unchanged**: car names always English; map/track names keep following `game_lang`.
- Changing UI language does **not** apply live — it takes effect on next launch. A static muted hint label sits under the language combo always.
- Auto-detect rule: system locale first 2 chars `uk` or `ru` → `uk`, otherwise `en`.
- Missing-translation fallback: current language → English string → the key itself (never crash, never blank).
- Follow the existing `game_lang` module style: process-global variable, no heavy imports, no circular deps.
- Tests run with `pytest`. New tests live under `tests/`.

---

### Task 1: `ui_lang` module + full translation dictionary

**Files:**
- Create: `alu_gauntlet_helper/ui_lang.py`
- Test: `tests/test_ui_lang.py`

**Interfaces:**
- Produces:
  - `EN = "en"`, `UK = "uk"`
  - `TRANSLATIONS: dict[str, dict[str, str]]` — keyed `{"en": {...}, "uk": {...}}`
  - `set_ui_language(language: str) -> None` — normalizes anything not `"uk"` to `EN`
  - `current_ui_language() -> str`
  - `t(key: str) -> str` — returns current-language string; falls back to EN string; falls back to `key`
  - `system_to_ui_language(locale_name: str) -> str` — maps an OS locale name (e.g. `"uk_UA"`) to `EN`/`UK`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ui_lang.py`:

```python
import pytest

from alu_gauntlet_helper import ui_lang


@pytest.fixture(autouse=True)
def restore_language():
    original = ui_lang.current_ui_language()
    yield
    ui_lang.set_ui_language(original)


def test_default_language_is_en():
    assert ui_lang.current_ui_language() == ui_lang.EN


def test_set_ui_language_uk():
    ui_lang.set_ui_language(ui_lang.UK)
    assert ui_lang.current_ui_language() == ui_lang.UK


def test_unknown_language_normalizes_to_en():
    ui_lang.set_ui_language("zz")
    assert ui_lang.current_ui_language() == ui_lang.EN


def test_t_returns_current_language_string():
    ui_lang.set_ui_language(ui_lang.EN)
    assert ui_lang.t("settings.save") == "Save"
    ui_lang.set_ui_language(ui_lang.UK)
    assert ui_lang.t("settings.save") == "Зберегти"


def test_t_returns_key_when_missing():
    assert ui_lang.t("nonexistent.key") == "nonexistent.key"


def test_translation_dicts_have_identical_keys():
    en_keys = set(ui_lang.TRANSLATIONS["en"])
    uk_keys = set(ui_lang.TRANSLATIONS["uk"])
    assert en_keys == uk_keys, f"key mismatch: {en_keys ^ uk_keys}"


@pytest.mark.parametrize("locale_name,expected", [
    ("uk_UA", "uk"),
    ("ru_RU", "uk"),
    ("en_US", "en"),
    ("de_DE", "en"),
    ("", "en"),
    ("C", "en"),
])
def test_system_to_ui_language(locale_name, expected):
    assert ui_lang.system_to_ui_language(locale_name) == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ui_lang.py -v`
Expected: FAIL with `ModuleNotFoundError` / `AttributeError` (module not created yet).

- [ ] **Step 3: Create the module**

Create `alu_gauntlet_helper/ui_lang.py` with the complete dictionary below:

```python
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
        "settings.game_lang_en": "Eng",
        "settings.game_lang_ru": "Rus",
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
        "capture.discard_session": "Discard session",
        "capture.save_failed": "Save failed",
        "capture.discard_confirm": "Discard all captured races?",
        # car selection
        "car_selection.race_history": "Race History — {name}",
        "car_selection.race_n": "Race {n}",
        "car_selection.select_track_placeholder": "Select track...",
        "car_selection.select_track": "Select a track",
        "car_selection.no_data": "No race data",
        # overlay
        "overlay.progress": "Gauntlet capture {complete}/{total}",
        "overlay.capture": "Capture",
        "overlay.save": "Save",
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
        "settings.game_lang_en": "Англ.",
        "settings.game_lang_ru": "Рос.",
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
        "capture.discard_session": "Скасувати сесію",
        "capture.save_failed": "Не вдалося зберегти",
        "capture.discard_confirm": "Скасувати всі захоплені заїзди?",
        "car_selection.race_history": "Історія заїздів — {name}",
        "car_selection.race_n": "Заїзд {n}",
        "car_selection.select_track_placeholder": "Оберіть трек...",
        "car_selection.select_track": "Оберіть трек",
        "car_selection.no_data": "Немає даних про заїзди",
        "overlay.progress": "Захоплення Gauntlet {complete}/{total}",
        "overlay.capture": "Захопити",
        "overlay.save": "Зберегти",
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ui_lang.py -v`
Expected: PASS (all tests, including the dict-parity test).

- [ ] **Step 5: Commit**

```bash
git add alu_gauntlet_helper/ui_lang.py tests/test_ui_lang.py
git commit -m "feat(i18n): add ui_lang module with en/uk translation dictionary"
```

---

### Task 2: `app_language` settings field + startup auto-detect/apply

**Files:**
- Modify: `alu_gauntlet_helper/services/settings.py` (add field near `game_language`, ~line 15)
- Modify: `main.py` (add wiring near existing `game_lang.set_game_language`, ~lines 40-42)
- Test: `tests/test_settings_model.py` (add one test)

**Interfaces:**
- Consumes: `ui_lang.set_ui_language`, `ui_lang.system_to_ui_language` (Task 1)
- Produces: `Settings.app_language: str` (default `""`)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_settings_model.py`:

```python
def test_app_language_defaults_to_empty():
    s = Settings()
    assert s.app_language == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_settings_model.py::test_app_language_defaults_to_empty -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'app_language'`.

- [ ] **Step 3: Add the field**

In `alu_gauntlet_helper/services/settings.py`, immediately after the existing
`game_language` field (around line 15), add:

```python
    # мова інтерфейсу застосунку; "" = ще не визначено (тригер автодетекту)
    app_language: str = ""  # "" | "en" | "uk"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_settings_model.py -v`
Expected: PASS.

- [ ] **Step 5: Wire auto-detect + apply in main.py**

In `main.py`, locate the existing block (around lines 40-42):

```python
    settings = APP_CONTEXT.settings.get()
    from alu_gauntlet_helper import game_lang
    game_lang.set_game_language(settings.game_language)
```

Replace it with:

```python
    settings = APP_CONTEXT.settings.get()
    from alu_gauntlet_helper import game_lang, ui_lang
    from PyQt6.QtCore import QLocale
    game_lang.set_game_language(settings.game_language)
    # мова UI: при першому запуску визначаємо із системної локалі й зберігаємо
    if not settings.app_language:
        settings.app_language = ui_lang.system_to_ui_language(QLocale.system().name())
        APP_CONTEXT.settings.save(settings)
    ui_lang.set_ui_language(settings.app_language)
```

(`QLocale.system().name()` works before `QApplication` is constructed — it reads
OS locale, not Qt app state.)

- [ ] **Step 6: Verify the app still imports/starts**

Run: `python -c "import main"`
Expected: no error (module imports cleanly).

- [ ] **Step 7: Commit**

```bash
git add alu_gauntlet_helper/services/settings.py main.py tests/test_settings_model.py
git commit -m "feat(i18n): add app_language setting with first-run locale auto-detect"
```

---

### Task 3: Application-language combo + restart hint in Settings tab

**Files:**
- Modify: `alu_gauntlet_helper/views/settings_tab.py`

**Interfaces:**
- Consumes: `ui_lang` (Task 1), `Settings.app_language` (Task 2)
- Produces: a working dropdown that persists `app_language`; static hint label.

This task adds the new control. (Localizing the *other* settings labels happens
in Task 4.) No unit test — verified by launching the app; the dict-parity test
from Task 1 already guards the new keys.

- [ ] **Step 1: Add the import and option list**

At the top of `settings_tab.py`, the module already does
`from alu_gauntlet_helper import game_lang`. Change it to:

```python
from alu_gauntlet_helper import game_lang, ui_lang
```

Below the existing `GAME_LANGUAGE_OPTIONS` list (around line 24), add:

```python
# (підпис, значення) — мова інтерфейсу застосунку
UI_LANGUAGE_OPTIONS = [
    ("Eng", ui_lang.EN),
    ("Ukr", ui_lang.UK),
]
```

- [ ] **Step 2: Build the combo + hint widgets**

In `SettingsTab.__init__`, right before the existing `self.game_language = QComboBox()`
block (around line 43), add:

```python
        self.app_language = QComboBox()
        for label, value in UI_LANGUAGE_OPTIONS:
            self.app_language.addItem(label, value)
        self.app_language.setMaximumWidth(HOTKEY_INPUT_WIDTH)
        self.app_language_hint = QLabel(ui_lang.t("settings.app_language_hint"))
        self.app_language_hint.setStyleSheet("color: #888;")
```

- [ ] **Step 3: Add the rows to the form**

In `__init__`, find the form assembly (around line 87,
`self.form.addRow("Game language", self.game_language)`). Insert the app-language
rows just before it:

```python
        self.form.addRow("Application language", self.app_language)
        self.form.addRow("", self.app_language_hint)
```

(Leave the existing `"Game language"` row as-is for now; Task 4 localizes captions.)

- [ ] **Step 4: Restore the saved value in refresh()**

In `refresh()` (around line 131, after the `show/close/start` lines and near the
existing `lang_idx = self.game_language.findData(...)`), add:

```python
        app_lang_idx = self.app_language.findData(settings.app_language)
        self.app_language.setCurrentIndex(app_lang_idx if app_lang_idx >= 0 else 0)
```

- [ ] **Step 5: Persist on save()**

In `on_save()` (around line 161, near
`settings.game_language = self.game_language.currentData() or game_lang.EN`), add:

```python
        settings.app_language = self.app_language.currentData() or ui_lang.EN
```

Do **not** call `ui_lang.set_ui_language` here — the change applies on next launch.

- [ ] **Step 6: Verify**

Run: `python -c "import alu_gauntlet_helper.views.settings_tab"`
Expected: no import error.

Then run `python main.py`, open SETTINGS: the "Application language" dropdown
shows Eng/Ukr with the muted hint beneath it; selecting Ukr + Save persists
(re-open Settings → still Ukr). Restart the app → UI is Ukrainian (after Task 4).

- [ ] **Step 7: Commit**

```bash
git add alu_gauntlet_helper/views/settings_tab.py
git commit -m "feat(i18n): add application-language selector + restart hint to settings"
```

---

### Task 4: Localize main window, tray, and settings-tab labels

**Files:**
- Modify: `alu_gauntlet_helper/views/main_window.py`
- Modify: `alu_gauntlet_helper/views/settings_tab.py`

**Interfaces:**
- Consumes: `ui_lang.t` (Task 1)

No unit test (pure string routing); verified by import + launch. The Task-1
parity test guards key existence.

- [ ] **Step 1: Localize main_window.py**

Add the import after the existing `from alu_gauntlet_helper.app_context import APP_CONTEXT`:

```python
from alu_gauntlet_helper import ui_lang
```

Replace the literals (exact current → new):

- L23 `self.setWindowTitle("ALU Gauntlet Helper")` → `self.setWindowTitle(ui_lang.t("window.title"))`
- L71 `show_action = QAction("Open", self)` → `show_action = QAction(ui_lang.t("tray.open"), self)`
- L72 `quit_action = QAction("Quit", self)` → `quit_action = QAction(ui_lang.t("tray.quit"), self)`
- L56-61 the six `addTab` calls:

```python
        self.tabs.addTab(self.capture_tab, ui_lang.t("tab.capture"))
        self.tabs.addTab(self.car_selection_tab, ui_lang.t("tab.car_selection"))
        self.tabs.addTab(self.races_tab, ui_lang.t("tab.races"))
        self.tabs.addTab(self.cars_tab, ui_lang.t("tab.cars"))
        self.tabs.addTab(self.tracks_tab, ui_lang.t("tab.tracks"))
        self.tabs.addTab(self.settings_tab, ui_lang.t("tab.settings"))
```

- [ ] **Step 2: Localize settings_tab.py literals**

(`ui_lang` is already imported from Task 3.) Replace:

- L35 `QCheckBox("Show tray icon")` → `QCheckBox(ui_lang.t("settings.show_tray"))`
- L38 `QCheckBox("Close to tray")` → `QCheckBox(ui_lang.t("settings.close_to_tray"))`
- L41 `QCheckBox("Start minimized")` → `QCheckBox(ui_lang.t("settings.start_minimized"))`
- L57 `QCheckBox("Save screenshots of unrecognized / low-confidence captures (data/captures)")` → `QCheckBox(ui_lang.t("settings.save_captures"))`
- L58 `QPushButton("Open folder")` → `QPushButton(ui_lang.t("settings.open_folder"))`
- L80 `QPushButton("Save")` → `QPushButton(ui_lang.t("settings.save"))`
- The form captions — `addRow("Application language", ...)` → `addRow(ui_lang.t("settings.app_language"), ...)`; `addRow("Game language", ...)` → `addRow(ui_lang.t("settings.game_language"), ...)`; `"Capture hotkey"` → `ui_lang.t("settings.capture_hotkey")`; `"Overlay hotkey"` → `ui_lang.t("settings.overlay_hotkey")`; `"Overlay actions"` → `ui_lang.t("settings.overlay_actions")`; `"Overlay opacity"` → `ui_lang.t("settings.overlay_opacity")`; `"Capture monitor"` → `ui_lang.t("settings.capture_monitor")`.
- L174 `self.capture_status.setText("Saved.")` → `self.capture_status.setText(ui_lang.t("settings.saved"))`
- L176 `self.capture_status.setText("Хоткей не зареєструвався — спробуй іншу клавішу")` → `self.capture_status.setText(ui_lang.t("settings.hotkey_failed"))`
- Game-language combo labels (around line 21-24): change `GAME_LANGUAGE_OPTIONS` to use keys at build time inside `__init__` instead of constant labels. Replace the loop at ~L44:

```python
        self.game_language = QComboBox()
        self.game_language.addItem(ui_lang.t("settings.game_lang_en"), game_lang.EN)
        self.game_language.addItem(ui_lang.t("settings.game_lang_ru"), game_lang.RU)
        self.game_language.setMaximumWidth(HOTKEY_INPUT_WIDTH)
```

(Then `GAME_LANGUAGE_OPTIONS` is unused — delete that constant.)

- Monitor button label in `_build_monitor_selector` (~L115)
  `QPushButton(f"Monitor {index + 1}\n{width}×{height}", self)` →

```python
            button = QPushButton(
                ui_lang.t("settings.monitor_btn").format(
                    index=index + 1, width=width, height=height),
                self)
```

- [ ] **Step 3: Verify**

Run: `python -c "import alu_gauntlet_helper.views.main_window"`
Expected: no import error.

Manual: launch with `app_language="uk"` in DB (set via Settings + restart) → tabs,
tray menu, and all settings labels render in Ukrainian; with `"en"` → English.

- [ ] **Step 4: Commit**

```bash
git add alu_gauntlet_helper/views/main_window.py alu_gauntlet_helper/views/settings_tab.py
git commit -m "feat(i18n): localize main window, tray, and settings labels"
```

---

### Task 5: Localize remaining tabs, dialogs, overlay, and components

**Files:**
- Modify: `alu_gauntlet_helper/views/races_tab.py`
- Modify: `alu_gauntlet_helper/views/tracks_tab.py`
- Modify: `alu_gauntlet_helper/views/cars_tab.py`
- Modify: `alu_gauntlet_helper/views/capture_tab.py`
- Modify: `alu_gauntlet_helper/views/car_selection_tab.py`
- Modify: `alu_gauntlet_helper/views/overlay.py`
- Modify: `alu_gauntlet_helper/views/components/edit_dialog.py`
- Modify: `alu_gauntlet_helper/views/components/image_line_edit.py`

**Interfaces:**
- Consumes: `ui_lang.t` (Task 1)

Add `from alu_gauntlet_helper import ui_lang` to each file (alongside existing
imports). No unit test; verified by import + launch.

- [ ] **Step 1: races_tab.py**

- L39 tooltip `"Bad timing"` → `ui_lang.t("races.bad_timing")`
- L62 `"Edit Race" if item.id else "Add Race"` → `ui_lang.t("dialog.edit_race") if item.id else ui_lang.t("dialog.add_race")` (match the actual conditional form in the file)
- L66 `addRow("Track", ...)` → `addRow(ui_lang.t("field.track"), ...)`
- L67 `addRow("Car", ...)` → `addRow(ui_lang.t("field.car"), ...)`
- L68 `addRow("Rank", ...)` → `addRow(ui_lang.t("field.rank"), ...)`
- L69 `addRow("Time", ...)` → `addRow(ui_lang.t("field.time"), ...)`
- L70 `addRow("Note", ...)` → `addRow(ui_lang.t("field.note"), ...)`
- L162 placeholder `"Track"` → `ui_lang.t("field.track")`
- L169 placeholder `"Car"` → `ui_lang.t("field.car")`
- L172 `"Add"` → `ui_lang.t("common.add")`

- [ ] **Step 2: tracks_tab.py**

- L32 `"Edit Map"/"Add Map"` → `ui_lang.t("dialog.edit_map")` / `ui_lang.t("dialog.add_map")`
- L36 `"Name"` → `ui_lang.t("field.name")`
- L37 `"Name (RU)"` → `ui_lang.t("field.name_ru")`
- L38 `"Icon"` → `ui_lang.t("field.icon")`
- L103 `"Edit Track"/"Add Track"` → `ui_lang.t("dialog.edit_track")` / `ui_lang.t("dialog.add_track")`
- L107 `"Map"` → `ui_lang.t("field.map")`
- L109 `"Name"` → `ui_lang.t("field.name")`
- L111 `"Name (RU)"` → `ui_lang.t("field.name_ru")`
- L113 `"Icon"` → `ui_lang.t("field.icon")`
- L202, L279 `"Add"` → `ui_lang.t("common.add")`

- [ ] **Step 3: cars_tab.py**

- L36 `"MAX"` → `ui_lang.t("cars.max")`
- L45 `"Edit Car"/"Add Car"` → `ui_lang.t("dialog.edit_car")` / `ui_lang.t("dialog.add_car")`
- L50 `"Brand"` → `ui_lang.t("field.brand")`
- L51 `"Model"` → `ui_lang.t("field.model")`
- L56 `"Rank"` → `ui_lang.t("field.rank")`
- L57 `"Icon"` → `ui_lang.t("field.icon")`
- L153 class filter buttons: localize only `"All"` → `ui_lang.t("cars.filter_all")`; leave `"D","C","B","A","S"` literal (class letters, not translated)
- L169 `"Default"` → `ui_lang.t("cars.sort_default")`
- L170 `"Max Rank"` → `ui_lang.t("cars.sort_max_rank")`
- L171 tooltip `"Sort order"` → `ui_lang.t("cars.sort_order")`
- L175 `"Add"` → `ui_lang.t("common.add")`

- [ ] **Step 4: capture_tab.py**

- L19 rich-text warning `"Some fields were recognized..."` → `ui_lang.t("capture.low_conf_warning")` (keep any surrounding HTML/markup; replace only the text content)
- L106 `"Load screenshot"` → `ui_lang.t("capture.load_screenshot")`
- L110 `f"Capture Screen ({settings.capture_hotkey.upper()})"` → `ui_lang.t("capture.capture_screen").format(hotkey=settings.capture_hotkey.upper())`
- L114 `f"Toggle Overlay ({settings.overlay_hotkey.upper()})"` → `ui_lang.t("capture.toggle_overlay").format(hotkey=settings.overlay_hotkey.upper())`
- L140 `"Save selected"` → `ui_lang.t("capture.save_selected")`
- L142 `"Discard session"` → `ui_lang.t("capture.discard_session")`
- L232 file-dialog title `"Load screenshot"` → `ui_lang.t("capture.load_screenshot")`
- L233 `"Images (*.png *.jpg *.jpeg *.bmp)"` → `ui_lang.t("common.images_filter")`
- L276 `"Save failed"` → `ui_lang.t("capture.save_failed")`
- L281 `"Discard session"` → `ui_lang.t("capture.discard_session")`
- L282 `"Discard all captured races?"` → `ui_lang.t("capture.discard_confirm")`

- [ ] **Step 5: car_selection_tab.py**

- L19 `f"Race History - {car_name}"` → `ui_lang.t("car_selection.race_history").format(name=car_name)`
- L128 `f"Race {race_number}"` → `ui_lang.t("car_selection.race_n").format(n=race_number)`
- L134 placeholder `"Select track..."` → `ui_lang.t("car_selection.select_track_placeholder")`
- L147, L177, L207 `"Select a track"` → `ui_lang.t("car_selection.select_track")`
- L213 `"No race data"` → `ui_lang.t("car_selection.no_data")`

- [ ] **Step 6: overlay.py**

- L30 `f"Gauntlet capture {complete}/{RACE_COUNT}"` → `ui_lang.t("overlay.progress").format(complete=complete, total=RACE_COUNT)`
- L272 `"Capture"` → `ui_lang.t("overlay.capture")`
- L277 `"Save"` → `ui_lang.t("overlay.save")`

- [ ] **Step 7: components/edit_dialog.py**

- L17 `QPushButton("Ok")` → `QPushButton(ui_lang.t("dialog.ok"))`
- L19 `QPushButton("Cancel")` → `QPushButton(ui_lang.t("dialog.cancel"))`

- [ ] **Step 8: components/image_line_edit.py**

- L23 tooltip `"Clear"` → `ui_lang.t("image.clear")`
- L29 `"Choose file"` → `ui_lang.t("image.choose_file")`
- L33 `"Paste from clipboard"` → `ui_lang.t("image.paste")`
- L66 dialog title `"Choose Image"` → `ui_lang.t("image.choose_image")`
- L66 filter `"Images (*.png *.jpg *.jpeg *.bmp)"` → `ui_lang.t("common.images_filter")`

- [ ] **Step 9: Verify all modules import**

Run:
```bash
python -c "import alu_gauntlet_helper.views.races_tab, alu_gauntlet_helper.views.tracks_tab, alu_gauntlet_helper.views.cars_tab, alu_gauntlet_helper.views.capture_tab, alu_gauntlet_helper.views.car_selection_tab, alu_gauntlet_helper.views.overlay, alu_gauntlet_helper.views.components.edit_dialog, alu_gauntlet_helper.views.components.image_line_edit"
```
Expected: no import error.

Run the full suite: `pytest -q`
Expected: PASS (no regressions; `test_ui_lang.py` parity test still green).

- [ ] **Step 10: Manual verification**

Launch `python main.py` with `app_language="uk"` (set via Settings → restart):
every tab, dialog (Add/Edit Race/Map/Track/Car), the overlay, capture buttons,
and file dialogs render Ukrainian. Map/track names still follow Game language;
car names stay English. Switch to Eng + restart → English throughout.

- [ ] **Step 11: Commit**

```bash
git add alu_gauntlet_helper/views/
git commit -m "feat(i18n): localize remaining tabs, dialogs, overlay, and components"
```

---

## Notes for the implementer

- **Line numbers are from a snapshot** — they may drift as you edit. Match on the
  literal text, not the line number.
- **Strings left intentionally literal:** car class letters `D/C/B/A/S`, keyboard
  combos `Ctrl + Alt` / `Ctrl + Shift`, the `"%"` opacity suffix, object names
  (`"secondary"`, `"segment"`, `"first"`, `"last"`), stylesheets, resource paths.
- **Conditional dialog titles:** preserve the existing `if item.id` (edit) vs else
  (add) structure — only swap the two literals for their `t()` keys.
- **`.format(...)` placeholders** must match the dict exactly: `{hotkey}`, `{name}`,
  `{n}`, `{complete}`, `{total}`, `{index}`, `{width}`, `{height}`.
- **Git:** the repo owner handles commits himself — if running unattended, prepare
  the commits but confirm before pushing.
```
