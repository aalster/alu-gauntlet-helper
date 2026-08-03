# Асистент проти суперника — Етап 2: шанс перемоги на оверлеї

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Додати в заголовок оверлея загальний шанс перемоги в матчі «72%» (P(≥3 з 5), без тильди) — єдине, чого бракує оверлею до спеки §7.

**Scope note:** Решту дзеркала оверлей отримав ще в Етапі 1: рекомендоване/фактичне авто, бейдж «78% 7/10», колірні статуси, 👎. Колонки «мій avg» і «час суперника» в оверлей НЕ додаються — рішення користувача (спека §7 оновлена): за деталями гравець іде в таб асистента.

**Architecture:** «72%» додається в чисту функцію `header_text` (оверлей) новим необов'язковим параметром `win_chance`; значення дає наявний `AssistantService.win_chance(session)` через виклик у `CaptureController._refresh_overlay`. Кольорові пороги відсотка виносяться в спільний хелпер `style.win_chance_color` (зараз захардкожені в `assistant_tab`) — заголовок оверлея і низ таба фарбуються однаково. `OverlayWindow` і `build_races_table` не змінюються.

**Tech Stack:** Python 3.10+ анотації (`X | None`), PyQt6 (rich-text QLabel), pytest. Чисті функції оверлея тестуються без Qt-івенлупу (наявний `tests/test_overlay_lines.py`).

## Global Constraints

- **Жодних міграцій БД і нових таблиць/колонок** — усе обчислюється на льоту (спека, розділ «Мета»).
- **Git-коміти НЕ робити** — користувач комітить сам (його явне правило). Завдання закінчуються зеленими тестами, без кроку commit.
- Нових UI-рядків немає («72%» — число без перекладу); якщо все ж додаєш ключ — в ОБИДВІ мови `ui_lang.TRANSLATIONS` («en» і «uk»).
- Коментарі в коді — українською, в стилі наявних файлів.
- Тести запускати як `.venv/Scripts/python -m pytest tests/<file> -v` з кореня репо (у Git Bash `python` з PATH відсутній).
- Спека: `docs/superpowers/specs/2026-08-02-opponent-assistant-design.md`, розділ 7 «Оверлей».

## Кольори й формати (довідка)

- `style.WIN_BRIGHT = "#A6E22E"`, `style.LOSS_BRIGHT = "#EE5A50"`, `style.RANK_DOWN = "#FF9F0A"` — усі відмінні від амбер-підсвітки `overlay.UNCERTAIN_COLOR = "#FFC107"`, тож асерти на кольори однозначні.
- Пороги загального шансу (як у `assistant_tab.refresh`): >75 — `WIN_BRIGHT`, >50 — `RANK_DOWN`, інакше `LOSS_BRIGHT`.
- Формат: «72%» — без тильди, як `win_chance_value` внизу таба асистента.

---

### Task 1: style.win_chance_color — спільні пороги кольору шансу

**Files:**
- Modify: `alu_gauntlet_helper/views/style.py`
- Modify: `alu_gauntlet_helper/views/assistant_tab.py` (метод `SessionView.refresh`, блок `chance`)
- Test: `tests/test_overlay_lines.py`

**Interfaces:**
- Consumes: константи `WIN_BRIGHT`, `RANK_DOWN`, `LOSS_BRIGHT` (уже в `style.py`).
- Produces (на це спирається Task 2): `style.win_chance_color(pct: int) -> str` — колір відсотка загального шансу перемоги.

- [x] **Step 1: Написати тести, що падають**

Додати в кінець `tests/test_overlay_lines.py`:

```python
# --- win_chance_color: спільні пороги таба асистента й оверлея -------------


def test_win_chance_color_thresholds():
    from alu_gauntlet_helper.views.style import RANK_DOWN, win_chance_color
    assert win_chance_color(76) == WIN_BRIGHT
    assert win_chance_color(75) == RANK_DOWN   # рівно 75 — ще помаранчевий
    assert win_chance_color(51) == RANK_DOWN
    assert win_chance_color(50) == LOSS_BRIGHT  # рівно 50 — вже червоний
```

- [x] **Step 2: Переконатися, що тести падають**

Run: `.venv/Scripts/python -m pytest tests/test_overlay_lines.py -v -k win_chance_color`
Expected: FAIL (`ImportError: cannot import name 'win_chance_color'`).

- [x] **Step 3: Реалізація**

У `alu_gauntlet_helper/views/style.py` після рядка `COUNT_WARN = "#D9A05A"`:

```python


def win_chance_color(pct: int) -> str:
    """Колір загального шансу перемоги в матчі (P(≥3 з 5), у відсотках):
    >75 — зелений, >50 — помаранчевий, інакше червоний. Спільні пороги для
    низу таба асистента й заголовка оверлея."""
    return WIN_BRIGHT if pct > 75 else RANK_DOWN if pct > 50 else LOSS_BRIGHT
```

У `alu_gauntlet_helper/views/assistant_tab.py` в `SessionView.refresh` замінити:

```python
        chance = APP_CONTEXT.assistant.win_chance(self.session)
        if chance is not None:
            pct = round(chance * 100)
            color = (style.WIN_BRIGHT if pct > 75
                     else style.RANK_DOWN if pct > 50 else style.LOSS_BRIGHT)
            self.win_chance_value.setText(f"{pct}%")
            self.win_chance_value.setStyleSheet(f"color: {color};")
```

на:

```python
        chance = APP_CONTEXT.assistant.win_chance(self.session)
        if chance is not None:
            pct = round(chance * 100)
            self.win_chance_value.setText(f"{pct}%")
            self.win_chance_value.setStyleSheet(f"color: {style.win_chance_color(pct)};")
```

- [x] **Step 4: Тести зелені**

Run: `.venv/Scripts/python -m pytest tests/test_overlay_lines.py -v`
Expected: PASS.

---

### Task 2: header_text — «72%» у заголовку оверлея

**Files:**
- Modify: `alu_gauntlet_helper/views/overlay.py` (функція `header_text` + імпорт зі `style`)
- Test: `tests/test_overlay_lines.py`

**Interfaces:**
- Consumes: `style.win_chance_color(pct)` (Task 1), `ui_lang.t("window.title")`.
- Produces (на це спирається Task 3): `header_text(races, win_chance: float | None = None) -> str` — при `win_chance=None` рівно як зараз (чистий бренд), інакше rich-text «бренд 72%» з кольором за порогами.

- [x] **Step 1: Написати тести, що падають**

Додати в кінець `tests/test_overlay_lines.py`:

```python
# --- заголовок з шансом перемоги «72%» (спека §7, Етап 2) -------------------


def test_header_with_win_chance_appends_colored_percent():
    from alu_gauntlet_helper.views.style import RANK_DOWN
    h = header_text({}, win_chance=0.72)
    assert BRAND_TITLE in h
    assert "72%" in h
    assert "~" not in h    # без тильди — як внизу таба асистента
    assert RANK_DOWN in h  # 72% — помаранчева зона (>50, ≤75)


def test_header_win_chance_color_zones():
    assert WIN_BRIGHT in header_text({}, 0.80)
    assert LOSS_BRIGHT in header_text({}, 0.30)


def test_header_without_win_chance_stays_plain():
    assert header_text({}) == BRAND_TITLE
    assert header_text({}, None) == BRAND_TITLE
```

- [x] **Step 2: Переконатися, що тести падають**

Run: `.venv/Scripts/python -m pytest tests/test_overlay_lines.py -v -k header`
Expected: FAIL (`TypeError: header_text() got an unexpected keyword argument 'win_chance'`).

- [x] **Step 3: Реалізація**

У `alu_gauntlet_helper/views/overlay.py`:

1. До імпорту з `alu_gauntlet_helper.views.style` додати `win_chance_color` (список імпортів там уже багаторядковий).
2. Замінити функцію `header_text`:

```python
def header_text(races: dict[int, EffectiveRace],
                win_chance: float | None = None) -> str:
    """Заголовок оверлея: бренд + «72%» — шанс виграти матч (P(≥3 з 5)),
    коли в сесії є часи суперника. Без них — статичний бренд, як раніше.
    QLabel з дефолтним AutoText сам розпізнає rich-text за тегом <span>."""
    title = ui_lang.t("window.title")
    if win_chance is None:
        return title
    pct = round(win_chance * 100)
    return (f"{escape(title)} <span style='color:{win_chance_color(pct)};"
            f"font-weight:bold'>{pct}%</span>")
```

- [x] **Step 4: Тести зелені**

Run: `.venv/Scripts/python -m pytest tests/test_overlay_lines.py -v`
Expected: PASS.

---

### Task 3: Передача win_chance в оверлей (CaptureController) + повний регрес

**Files:**
- Modify: `alu_gauntlet_helper/capture/capture_controller.py` (метод `_refresh_overlay`, лише виклик `update_content`)
- Test: повний прогін наявних тестів (юніт-тестів на `CaptureController` немає — він тягне Qt/хоткеї; логіка заголовка покрита Task 2, тут лише глю)

**Interfaces:**
- Consumes: `AssistantService.win_chance(session) -> float | None` (наявний), `header_text(races, win_chance)` (Task 2).
- Produces: заголовок оверлея показує шанс матчу; `build_races_table` і `OverlayWindow` не змінюються.

- [x] **Step 1: Реалізація**

У `alu_gauntlet_helper/capture/capture_controller.py` в `_refresh_overlay` замінити виклик:

```python
        self.overlay.update_content(
            header_text(effective),
            build_races_table(effective, track_names, car_names, beat_stats),
            status, hint, self._in_flight)
```

на:

```python
        self.overlay.update_content(
            header_text(effective, APP_CONTEXT.assistant.win_chance(session)),
            build_races_table(effective, track_names, car_names, beat_stats),
            status, hint, self._in_flight)
```

- [x] **Step 2: Повний прогін тестів**

Run: `.venv/Scripts/python -m pytest tests`
Expected: PASS (OCR-тести можуть скіпатись без Tesseract/фікстур — це нормально).

- [x] **Step 3: Ручна перевірка (користувач)**

Запустити `python main.py`, відсканувати акордеон BEFORE — у заголовку оверлея поруч із брендом має з'явитися кольоровий «NN%»; сесія без даних суперника — бренд без відсотка, як раніше.
