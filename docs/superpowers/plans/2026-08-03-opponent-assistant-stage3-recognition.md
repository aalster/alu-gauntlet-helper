# Асистент проти суперника — Етап 3 (частина «розпізнавання»): скаут-екрани 2/3

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Розпізнавати два екрани вибору суперника (спека §3): «екран 2» — пропозиція суперника (5 однакових панелей: іконка карти + назва треку, без часів) і «екран 3» — реванш-лог (іконка карти + час суперника, без назв треків); іконка карти → `RaceCapture.map` через матчинг шаблонів OpenCV.

**Architecture:** Новий модуль `map_icon_matcher.py` (мультимасштабний `cv2.matchTemplate` по еталонах іконок карт) + новий екстрактор `opponent_scout.py` з дешевим піксельним гейтом «5 рівних колонок» (перевикористовує `band_segments`). Обидва варіанти екрана обробляє ОДИН екстрактор: варіант визначається наявністю чорної плашки часу внизу панелі (`dark_fraction`, 0 OCR). Номер гонки — позиційний (панелі завжди RACE 1..5 зліва направо); якір екрана — бейдж «RACE 1»/«ГОНКА 1» першої панелі (заодно дає мову). Інтеграція: екстрактор стає в конвеєр ПЕРЕД акордеоном; `SessionManager` тригерить автопідбір і на скани з полем `map`.

**Tech Stack:** Python 3.10+, OpenCV (`matchTemplate` TM_CCOEFF_NORMED), наявні `ocr.read_time`/`read_name`, `TrackResolver`, pytest.

## Global Constraints

- **Жодних міграцій БД** — нових таблиць/колонок немає; еталони іконок — наявні `resources/icons/maps/*.png` (180×180 RGBA, білий гліф з альфою).
- **Git-коміти НЕ робити** — користувач комітить сам. Завдання закінчуються зеленими тестами.
- Коментарі в коді — українською, в стилі наявних файлів.
- Тести: `.venv/Scripts/python -m pytest tests/<file> -v` з кореня репо. OCR-тести без Tesseract скіпаються; тести матчера іконок — чистий OpenCV, без скіпів.
- Спека: `docs/superpowers/specs/2026-08-02-opponent-assistant-design.md` §3; частина «логіка» етапу 3 вже реалізована (план `2026-08-03-opponent-assistant-stage3.md`): `RaceCapture.map` існує і мержиться, `resolve_tracks`/звуження працюють від `EffectiveRace.map_id`.
- Дані суперника (`opponent_car`) з цих екранів НЕ читаємо — спека §3 для них передбачає лише карту/трек/час (авто суперника на екрані є, але воно ніде не використовується — YAGNI).

## Фікстури (вже в репо) і виміряні факти

`tests/fixtures/opponent_tracks.png` (екран 2, EN, нік «Pro™ Shaurya»),
`tests/fixtures/opponent_times_1.png` (екран 3, «carbonara81»),
`tests/fixtures/opponent_times_2.png` (екран 3, «SEOUL DRIVER»); усі 2559×1599.

Виміряно програмно (band_segments + перевірений прототип матчингу, 15/15 панелей вгадано):

- Сегменти панелей (частки ширини): ліві краї ≈ 0.084/0.258/0.431/0.606/0.782,
  ширина 0.132–0.141 (акордеонні згорнуті колонки — 0.08–0.10, розгорнута ≥0.32:
  діапазони не перетинаються; верхня межа `_COLUMN_W_RANGE` 0.13 < 0.132, тож
  запасний OCR-пошук акордеона на скаут-екранах не вмикається).
- Вертикаль: панелі ≈ y 0.253..0.722; бейдж RACE N ≈ 0.253..0.283; іконка карти
  ≈ 0.29..0.42; назва треку (екран 2) ≈ 0.40..0.45; чорна плашка часу (екран 3)
  ≈ 0.66..0.70. На екрані 2 в зоні плашки часу — назва авто на світлому
  градієнті БЕЗ плашки (розрізняється `dark_fraction`).

Очікувані значення панелей (перевірені прототипом і звірені очима/сідом):

| Фікстура | R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|---|
| opponent_tracks: карта | Greenland | San Francisco | The Caribbean | Osaka | Scotland |
| opponent_tracks: трек | Out of the Center | Railroad Bustle | Hell Vale | Namba Park | Rocky Valley |
| opponent_times_1: карта | The Caribbean | Osaka | Himalayas | Rome | Auckland |
| opponent_times_1: час, мс | 27100 | 24983 | 22166 | 21966 | 30499 |
| opponent_times_2: карта | New York | Himalayas | San Francisco | Greenland | Singapore |
| opponent_times_2: час, мс | 25203 | 21285 | 22552 | 44489 | 24036 |

Скори прототипу: правильна карта 0.87–0.90 (зрідка 0.58–0.66 — Caribbean r1
times_1, Greenland r4 times_2, обидва правильні), друга-найкраща ≤ 0.59.

## Довідка по наявному коду

- `screen_recognition/screens/expanded_panel.py` — `band_segments(img) -> list[(l, r)]`.
- `screen_recognition/screens/base.py` — `ScreenExtractor`, `read_race_header(img, region) -> (number|None, "en"/"ru"/None)`, `HEADER_DY_OFFSETS`, `dark_fraction(roi, threshold=70)`, `encode_png`.
- `screen_recognition/ocr.py` — `read_time(img) -> int|None`, `read_name(img, channel="gray", lang="eng") -> str`.
- `screen_recognition/matching.py` — `TrackResolver.resolve(text) -> FieldGuess|None` (текст без назви карти йде через глобальний fallback-матчер: у словнику є синонім «сама назва треку», EN і RU).
- `screen_recognition/regions.py` — `RelRect(x, y, w, h)` з `.sub()`, `.crop()`.
- `models.py` — `RaceCapture` (уже має `map: FieldGuess | None`), `FieldGuess(value, score, candidates)`.
- `services/session_manager.py` — `SessionManager.apply`: `has_opponent_data = any(c.opponent_time or c.opponent_car ...)` → тригер auto_pick.
- `capture/capture_controller.py` — `_build_engine()` збирає екстрактори; порядок за ціною відмови.
- `services/maps.py` — `MapsService.autocomplete("") -> list[Map]` (усі карти; `Map.id`, `Map.icon` — шлях до PNG у data/, скопійованого з `resources/icons/maps` при сіді).
- `tests/recognition_vocab.py` — `build_resolvers()` → TrackResolver на повному сіді; `track_views()` (id = індекс у сід-списку).
- `tests/test_screen_gates.py` — списки фікстур за типом екрана + патерн `no_ocr`.

---

### Task 1: MapIconMatcher — матчинг іконок карт

**Files:**
- Create: `alu_gauntlet_helper/screen_recognition/map_icon_matcher.py`
- Test: `tests/test_map_icon_matcher.py`

**Interfaces:**
- Consumes: `FieldGuess`; еталони — обʼєкти з полями `id: int` і `icon: str` (шлях до PNG 180×180 RGBA).
- Produces (на це спираються Task 2, 4): `MapIconMatcher(maps: Iterable) `; `match(roi_bgr: np.ndarray) -> FieldGuess | None` — карта за іконкою на кропі панелі; score = максимум TM_CCOEFF_NORMED (0..1), `candidates` — топ-3; None, якщо найкращий скор < `MIN_SCORE = 0.5` або кроп замалий.

- [x] **Step 1: Написати тести, що падають**

Створити `tests/test_map_icon_matcher.py`:

```python
"""Матчинг іконок карт (екрани скаутингу суперника). Чистий OpenCV, без OCR.

Очікувані карти панелей звірені очима з resources/icons/maps і зафіксовані
прототипом (див. план 2026-08-03-opponent-assistant-stage3-recognition.md)."""
from pathlib import Path
from types import SimpleNamespace

import cv2
import pytest

from alu_gauntlet_helper.screen_recognition.map_icon_matcher import MapIconMatcher
from alu_gauntlet_helper.screen_recognition.screens.expanded_panel import band_segments

FIXTURES = Path(__file__).parent / "fixtures"
ICONS = Path(__file__).parent.parent / "resources" / "icons" / "maps"

# Абсолютна зона іконки карти в панелі (частки кадру) — як у прототипі.
ICON_Y = (0.29, 0.42)

MAP_IDS = {p.stem: i for i, p in enumerate(sorted(ICONS.glob("*.png")))}


def matcher():
    return MapIconMatcher(SimpleNamespace(id=i, icon=str(ICONS / f"{name}.png"))
                          for name, i in MAP_IDS.items())


def panel_icon(img, index):
    h, w = img.shape[:2]
    left, right = band_segments(img)[index]
    return img[int(ICON_Y[0] * h):int(ICON_Y[1] * h), int(left * w):int(right * w)]


EXPECTED = {
    "opponent_tracks": ["Greenland", "San Francisco", "The Caribbean", "Osaka", "Scotland"],
    "opponent_times_1": ["The Caribbean", "Osaka", "Himalayas", "Rome", "Auckland"],
    "opponent_times_2": ["New York", "Himalayas", "San Francisco", "Greenland", "Singapore"],
}


@pytest.mark.parametrize("fixture", sorted(EXPECTED))
def test_matches_all_panels(fixture):
    path = FIXTURES / f"{fixture}.png"
    if not path.exists():
        pytest.skip("немає фікстури")
    img = cv2.imread(str(path))
    m = matcher()
    for i, expected in enumerate(EXPECTED[fixture]):
        guess = m.match(panel_icon(img, i))
        assert guess is not None, f"панель {i + 1}: іконку не розпізнано"
        assert guess.value == MAP_IDS[expected], f"панель {i + 1}"
        assert guess.score >= 0.5
        assert len(guess.candidates) <= 3


def test_no_match_on_blank_roi():
    import numpy as np
    m = matcher()
    assert m.match(np.zeros((160, 340, 3), dtype=np.uint8)) is None


def test_tiny_roi_returns_none():
    import numpy as np
    m = matcher()
    assert m.match(np.zeros((10, 10, 3), dtype=np.uint8)) is None
```

- [x] **Step 2: Переконатися, що тести падають**

Run: `.venv/Scripts/python -m pytest tests/test_map_icon_matcher.py -v`
Expected: FAIL (ModuleNotFoundError).

- [x] **Step 3: Реалізація**

Створити `alu_gauntlet_helper/screen_recognition/map_icon_matcher.py`:

```python
"""Матчинг іконки карти на панелі скаут-екрана з еталонами resources/icons/maps.

Еталони — 180×180 RGBA: білий гліф бейджа з альфою. На панелі іконка — той
самий білий гліф на фіолетовому градієнті, розмір ≈ 55–85% висоти зони, позиція
трохи плаває, тому шаблон проганяється в кількох масштабах, а зсув знаходить
сам matchTemplate. Форми бейджів різні (гексагон/квадрат/пентагон/щит/коло) —
TM_CCOEFF_NORMED дає правильній карті 0.87–0.90 проти ≤0.59 у другої
(зрідка 0.58–0.66 у правильної — тому поріг 0.5, а не 0.8)."""
from typing import Iterable

import cv2
import numpy as np

from alu_gauntlet_helper.models import FieldGuess

MIN_SCORE = 0.5      # нижче — вважаємо, що іконки в кропі немає
SCALES = (0.55, 0.65, 0.75, 0.85)  # висота шаблону в частках висоти кропу
MIN_TEMPLATE_PX = 20  # дрібніший ресайз втрачає гліф — масштаб пропускається
CANDIDATE_LIMIT = 3


class MapIconMatcher:
    """Зіставляє кроп зони іконки з еталонами всіх карт; будується один раз
    на захоплення (як словники матчерів у _build_engine)."""

    def __init__(self, maps: Iterable):
        # map_id -> grayscale-композит гліфа на чорному (альфа = маска яскравості)
        self._templates: dict[int, np.ndarray] = {}
        for m in maps:
            icon = getattr(m, "icon", "")
            if not icon:
                continue
            img = cv2.imread(icon, cv2.IMREAD_UNCHANGED)
            if img is None or img.ndim != 3 or img.shape[2] != 4:
                continue
            alpha = img[..., 3].astype(np.float32) / 255.0
            gray = cv2.cvtColor(img[..., :3], cv2.COLOR_BGR2GRAY).astype(np.float32)
            self._templates[m.id] = (gray * alpha).astype(np.uint8)

    def match(self, roi_bgr: np.ndarray) -> FieldGuess | None:
        if not self._templates or roi_bgr.size == 0:
            return None
        roi = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
        rh, rw = roi.shape
        scores: dict[int, float] = {}
        for map_id, template in self._templates.items():
            best = 0.0
            for scale in SCALES:
                side = int(rh * scale)
                if side < MIN_TEMPLATE_PX or side > min(rh, rw):
                    continue
                resized = cv2.resize(template, (side, side), interpolation=cv2.INTER_AREA)
                result = cv2.matchTemplate(roi, resized, cv2.TM_CCOEFF_NORMED)
                best = max(best, float(result.max()))
            scores[map_id] = best
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:CANDIDATE_LIMIT]
        if not ranked or ranked[0][1] < MIN_SCORE:
            return None
        return FieldGuess(value=ranked[0][0], score=ranked[0][1], candidates=ranked)
```

- [x] **Step 4: Тести зелені**

Run: `.venv/Scripts/python -m pytest tests/test_map_icon_matcher.py -v`
Expected: PASS (усі 15 панелей). Якщо котрась панель не збігається — звір кроп
із еталоном очима (збережи `panel_icon(...)` у scratchpad через cv2.imwrite із
WINDOWS-шляхом), перш ніж міняти константи.

---

### Task 2: Регіони + OpponentScoutExtractor

**Files:**
- Modify: `alu_gauntlet_helper/screen_recognition/regions.py`
- Create: `alu_gauntlet_helper/screen_recognition/screens/opponent_scout.py`
- Test: `tests/test_opponent_scout.py`

**Interfaces:**
- Consumes: `band_segments`, `read_race_header`, `HEADER_DY_OFFSETS`, `dark_fraction`, `encode_png`, `ocr.read_time`/`read_name`, `TrackResolver`, `MapIconMatcher` (Task 1).
- Produces (на це спираються Task 3–4):
  - `regions.py`: `SCOUT_PANEL_TOP = 0.245`, `SCOUT_PANEL_BOTTOM = 0.73`, `SCOUT_W_RANGE = (0.115, 0.16)`, `SCOUT_HEADER`, `SCOUT_MAP_ICON`, `SCOUT_TRACK_NAME`, `SCOUT_TIME` (RelRect-и відносно панелі);
  - `opponent_scout.py`: `detect_scout_panels(img) -> list[RelRect] | None` (піксельний гейт, 0 OCR) і `OpponentScoutExtractor(track_resolver, map_matcher)` з `name = "opponent_scout"`; повертає 5 `RaceCapture` з позиційними `race_number`, полями `map` (+ `track` на екрані 2, + `opponent_time` на екрані 3), `game_language`.

- [x] **Step 1: Написати тести, що падають**

Створити `tests/test_opponent_scout.py`:

```python
"""Екстрактор скаут-екранів суперника (спека §3, «екран 2» і «екран 3»).

Очікувані значення — з таблиці плану 2026-08-03-...-stage3-recognition.md
(звірені очима зі скріншотами й сідом треків)."""
from pathlib import Path
from types import SimpleNamespace

import cv2
import pytest

from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.map_icon_matcher import MapIconMatcher
from alu_gauntlet_helper.screen_recognition.screens.opponent_scout import (
    OpponentScoutExtractor, detect_scout_panels,
)
from tests.recognition_vocab import build_resolvers

FIXTURES = Path(__file__).parent / "fixtures"
ICONS = Path(__file__).parent.parent / "resources" / "icons" / "maps"

MAP_IDS = {p.stem: 100 + i for i, p in enumerate(sorted(ICONS.glob("*.png")))}

TRACK_RESOLVER, _, TRACK_VIEWS, _ = build_resolvers()


def tid(map_name, name):
    return next(v.id for v in TRACK_VIEWS if v.map_name == map_name and v.name == name)


def extractor():
    m = MapIconMatcher(SimpleNamespace(id=i, icon=str(ICONS / f"{name}.png"))
                       for name, i in MAP_IDS.items())
    return OpponentScoutExtractor(TRACK_RESOLVER, m)


def load(name):
    path = FIXTURES / f"{name}.png"
    if not path.exists():
        pytest.skip("немає фікстури")
    return cv2.imread(str(path))


def need_tesseract():
    if not ocr.is_available():
        pytest.skip("немає tesseract")


def test_detect_scout_panels_on_fixtures():
    for name in ("opponent_tracks", "opponent_times_1", "opponent_times_2"):
        panels = detect_scout_panels(load(name))
        assert panels is not None and len(panels) == 5, name


def test_detect_rejects_accordion():
    assert detect_scout_panels(load("accordion_before_1")) is None
    assert detect_scout_panels(load("race_result_4_lost")) is None


def test_tracks_variant():
    """Екран 2: трек + карта на кожній панелі, часів немає."""
    need_tesseract()
    captures = extractor().extract(load("opponent_tracks"))
    assert [c.race_number for c in captures] == [1, 2, 3, 4, 5]
    expected = [("Greenland", "Out of the Center"),
                ("San Francisco", "Railroad Bustle"),
                ("The Caribbean", "Hell Vale"),
                ("Osaka", "Namba Park"),
                ("Scotland", "Rocky Valley")]
    for c, (map_name, track_name) in zip(captures, expected):
        assert c.track is not None and c.track.value == tid(map_name, track_name)
        assert c.map is not None and c.map.value == MAP_IDS[map_name]
        assert c.opponent_time is None
        assert c.car is None and c.time is None and c.rank is None
        assert c.game_language == "en"
        assert c.source_screen == "opponent_scout"
        assert c.panel_image


def test_times_variant_1():
    """Екран 3: карта + час суперника, назв треків немає."""
    need_tesseract()
    captures = extractor().extract(load("opponent_times_1"))
    assert [c.race_number for c in captures] == [1, 2, 3, 4, 5]
    expected = [("The Caribbean", 27100), ("Osaka", 24983), ("Himalayas", 22166),
                ("Rome", 21966), ("Auckland", 30499)]
    for c, (map_name, time_ms) in zip(captures, expected):
        assert c.map is not None and c.map.value == MAP_IDS[map_name]
        assert c.opponent_time == time_ms
        assert c.track is None
        assert c.car is None and c.time is None and c.rank is None


def test_times_variant_2():
    need_tesseract()
    captures = extractor().extract(load("opponent_times_2"))
    expected = [("New York", 25203), ("Himalayas", 21285), ("San Francisco", 22552),
                ("Greenland", 44489), ("Singapore", 24036)]
    for c, (map_name, time_ms) in zip(captures, expected):
        assert c.map is not None and c.map.value == MAP_IDS[map_name]
        assert c.opponent_time == time_ms


def test_alien_screen_returns_empty():
    need_tesseract()
    assert extractor().extract(load("accordion_before_1")) == []
    assert extractor().extract(load("before_race_1")) == []
```

- [x] **Step 2: Переконатися, що тести падають**

Run: `.venv/Scripts/python -m pytest tests/test_opponent_scout.py -v`
Expected: FAIL (ModuleNotFoundError).

- [x] **Step 3: Регіони**

У `regions.py` після блоку `BEFORE_RACE_*` додати:

```python
# --- Скаут-екрани суперника (спека §3: «екран 2» і «екран 3») -----------------
# Пропозиція суперника і реванш-лог: 5 ОДНАКОВИХ панелей RACE 1..5 у ряд.
#   Екран 2 (пропозиція): іконка карти + НАЗВА ТРЕКУ текстом; часів немає.
#   Екран 3 (реванш-лог): іконка карти + чорна плашка з часом суперника внизу;
#                          назв треків немає.
# Виміряно за tests/fixtures/opponent_tracks.png, opponent_times_{1,2}.png
# (2559×1599): ліві краї сегментів 0.084/0.258/0.431/0.606/0.782, ширина
# 0.132–0.141; панелі по вертикалі 0.253..0.722. X-межі панелей беруться з
# band_segments динамічно, вертикаль — константи із запасом.
SCOUT_PANEL_TOP = 0.245
SCOUT_PANEL_BOTTOM = 0.73
# Ширини сегментів скаут-панелей: вужчі за розгорнуту панель акордеона (≥0.32)
# і ширші за його згорнуті колонки (0.08–0.10; верхня межа їх діапазону 0.13).
SCOUT_W_RANGE = (0.115, 0.16)

# Вкладені регіони відносно панелі (частки панелі).
SCOUT_HEADER = RelRect(0.05, 0.0, 0.90, 0.075)     # бейдж "RACE N" / "ГОНКА N"
SCOUT_MAP_ICON = RelRect(0.0, 0.08, 1.0, 0.29)     # білий бейдж-іконка карти
SCOUT_TRACK_NAME = RelRect(0.03, 0.30, 0.94, 0.15)  # назва треку (лише екран 2)
SCOUT_TIME = RelRect(0.10, 0.84, 0.80, 0.11)       # чорна плашка часу (екран 3)
# Частка темних пікселів у зоні SCOUT_TIME, з якої вважаємо, що плашка є:
# на екрані 3 плашка чорна (частка ~0.5+), на екрані 2 там назва авто на
# світлому градієнті (частка ~0).
SCOUT_TIME_PLATE_MIN_DARK = 0.25
```

- [x] **Step 4: Екстрактор**

Створити `alu_gauntlet_helper/screen_recognition/screens/opponent_scout.py`:

```python
"""Скаут-екрани суперника: пропозиція (екран 2) і реванш-лог (екран 3).

Обидва — 5 ОДНАКОВИХ панелей RACE 1..5 у ряд, без розгорнутої. Гейт (0 OCR):
band_segments дає рівно 5 сегментів однакової ширини SCOUT_W_RANGE — акордеон
(4 вузькі + 1 широка) і решта екранів цей патерн не мають. Якір екрана — бейдж
першої панелі ("RACE 1"/"ГОНКА 1"), він же дає мову інтерфейсу гри.

Номер гонки позиційний (i+1): панелі завжди йдуть 1..5 зліва направо.
Варіант екрана — за чорною плашкою часу внизу панелі (dark_fraction):
є плашка → реванш-лог (карта + час суперника), немає → пропозиція
(карта + назва треку). Іконка карти матчиться шаблонами (MapIconMatcher)
в обох варіантах — при невизначеному треку вона живить звуження за часом
(спека §6) через RaceCapture.map."""
import numpy as np

from alu_gauntlet_helper.models import RaceCapture
from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.map_icon_matcher import MapIconMatcher
from alu_gauntlet_helper.screen_recognition.matching import TrackResolver
from alu_gauntlet_helper.screen_recognition.regions import (
    RelRect, SCOUT_HEADER, SCOUT_MAP_ICON, SCOUT_PANEL_BOTTOM, SCOUT_PANEL_TOP,
    SCOUT_TIME, SCOUT_TIME_PLATE_MIN_DARK, SCOUT_TRACK_NAME, SCOUT_W_RANGE,
)
from alu_gauntlet_helper.screen_recognition.screens.base import (
    HEADER_DY_OFFSETS, ScreenExtractor, dark_fraction, encode_png, read_race_header,
)
from alu_gauntlet_helper.screen_recognition.screens.expanded_panel import band_segments

_PANEL_COUNT = 5

# Канали препроцесу назви треку — як в акордеоні (текст білий на градієнті).
TRACK_CHANNELS = ("gray", "min", "max")


def detect_scout_panels(img: np.ndarray) -> list[RelRect] | None:
    """Панелі скаут-екрана або None. Піксельний гейт, 0 OCR: рівно 5 сегментів,
    усі в SCOUT_W_RANGE (акордеонові колонки вужчі, розгорнута панель ширша)."""
    segments = band_segments(img)
    if len(segments) != _PANEL_COUNT:
        return None
    widths = [right - left for left, right in segments]
    if not all(SCOUT_W_RANGE[0] <= w <= SCOUT_W_RANGE[1] for w in widths):
        return None
    return [RelRect(left, SCOUT_PANEL_TOP, right - left,
                    SCOUT_PANEL_BOTTOM - SCOUT_PANEL_TOP)
            for left, right in segments]


class OpponentScoutExtractor(ScreenExtractor):
    """Пропозиція суперника / реванш-лог: 5 панелей → 5 RaceCapture
    (map завжди; track — екран 2; opponent_time — екран 3)."""

    name = "opponent_scout"

    def __init__(self, track_resolver: TrackResolver, map_matcher: MapIconMatcher):
        self.track_resolver = track_resolver
        self.map_matcher = map_matcher

    def _anchor_language(self, img: np.ndarray, first_panel: RelRect) -> str | None:
        """Якір екрана: бейдж першої панелі має читатись як номер 1.
        Повертає мову ("en"/"ru") або None, якщо якоря немає (чужий екран)."""
        for dy in HEADER_DY_OFFSETS:
            number, language = read_race_header(
                img, first_panel.shifted(0.0, dy).sub(SCOUT_HEADER))
            if number == 1:
                return language
        return None

    def _resolve_track(self, crop: np.ndarray, language: str | None):
        """Назва треку без назви карти: TrackResolver іде через fallback-матчер,
        у словнику якого є синонім «сама назва треку» (EN і RU)."""
        lang = "rus" if language == "ru" else "eng"
        best = None
        for channel in TRACK_CHANNELS:
            guess = self.track_resolver.resolve(
                ocr.read_name(crop, channel=channel, lang=lang))
            if guess is not None and (best is None or guess.score > best.score):
                best = guess
        return best

    def extract(self, img: np.ndarray) -> list[RaceCapture]:
        panels = detect_scout_panels(img)
        if panels is None:
            return []
        language = self._anchor_language(img, panels[0])
        if language is None:
            return []
        captures = []
        for i, panel in enumerate(panels):
            map_guess = self.map_matcher.match(panel.sub(SCOUT_MAP_ICON).crop(img))
            time_roi = panel.sub(SCOUT_TIME).crop(img)
            opponent_time = None
            track = None
            if dark_fraction(time_roi) >= SCOUT_TIME_PLATE_MIN_DARK:
                # реванш-лог: чорна плашка → час суперника, назв треків немає
                opponent_time = ocr.read_time(time_roi)
            else:
                # пропозиція: назва треку текстом під іконкою карти
                track = self._resolve_track(panel.sub(SCOUT_TRACK_NAME).crop(img), language)
            if map_guess is None and track is None and opponent_time is None:
                continue  # порожня/нечитабельна панель — не засмічуємо сесію
            captures.append(RaceCapture(
                race_number=i + 1,
                track=track,
                map=map_guess,
                opponent_time=opponent_time,
                source_screen=self.name,
                panel_image=encode_png(panel.crop(img)),
                game_language=language,
            ))
        return captures
```

- [x] **Step 5: Тести зелені (з калібруванням за потреби)**

Run: `.venv/Scripts/python -m pytest tests/test_opponent_scout.py tests/test_map_icon_matcher.py -v`
Expected: PASS.

Якщо OCR не читає час/трек — калібрувати регіони так само, як в етапі 1:
зберегти кропи `panel.sub(SCOUT_TIME).crop(img)` / `SCOUT_TRACK_NAME` у
scratchpad (cv2.imwrite ВИМАГАЄ Windows-шлях `C:\...`, /c/... мовчки не пише)
і подивитись очима; час найчутливіший — за уроком `ACCORDION_OPPONENT_TIME`
кроп треба звужувати впритул до чорної плашки, без зайвого фону навколо.
Тимчасові скрипти в репо не лишати.

---

### Task 3: Піксельні гейти — скаут-фікстури в test_screen_gates

**Files:**
- Modify: `tests/test_screen_gates.py`

**Interfaces:**
- Consumes: `detect_scout_panels` (Task 2), `OpponentScoutExtractor`, наявні списки фікстур і фікстура `no_ocr`.
- Produces: гарантія «0 OCR на чужих екранах» в обидва боки: скаут-екстрактор мовчить на всіх чужих фікстурах без OCR; наявні екстрактори мовчать на скаут-фікстурах без OCR.

- [x] **Step 1: Написати тести (частина впаде до реалізації — Task 2 вже зроблено, тож усе має пройти одразу; якщо щось падає — це знахідка про гейти)**

У `tests/test_screen_gates.py`:

1. Додати до імпортів:

```python
from alu_gauntlet_helper.screen_recognition.screens.opponent_scout import (
    OpponentScoutExtractor, detect_scout_panels,
)
```

2. Після списку `ACCORDION` додати:

```python
SCOUT = ["opponent_tracks.png", "opponent_times_1.png", "opponent_times_2.png"]
```

3. Дописати тести в кінець файлу (стиль наявних гейт-тестів; подивись, як
   влаштовані сусідні `test_*_gate_*` і фікстура `no_ocr`, і зроби так само):

```python
# --- скаут-екрани суперника (opponent_scout) --------------------------------


@pytest.mark.parametrize("fixture", SCOUT)
def test_scout_gate_passes_own_fixtures(fixture):
    panels = detect_scout_panels(load(fixture))
    assert panels is not None and len(panels) == 5


@pytest.mark.parametrize("fixture", RACE_RESULT + COMPLETE + BEFORE_RACE + ACCORDION)
def test_scout_rejects_alien_without_ocr(fixture, no_ocr):
    extractor = OpponentScoutExtractor(track_resolver=None, map_matcher=None)
    assert extractor.extract(load(fixture)) == []


@pytest.mark.parametrize("fixture", SCOUT)
def test_other_gates_reject_scout_without_ocr(fixture, no_ocr):
    img = load(fixture)
    # у скаут-екрана немає розгорнутої панелі й немає 4 вузьких колонок
    segments = band_segments(img)
    assert find_expanded(segments) is None
    assert not has_accordion_columns(segments)
    assert not looks_like_race_result(img)
    assert not looks_like_challenge_complete(img)
```

Примітка: `find_expanded` імпортувати з `expanded_panel` (поряд з наявними
імпортами `band_segments`/`has_accordion_columns`). Якщо в наявних гейт-тестах
чужі екрани перевіряються через виклик екстрактора цілком (не через функції
гейтів) — переведи третій тест на той самий патерн, що в сусідів (виклики
відповідних екстракторів з `no_ocr`), щоб файл лишався однорідним.

- [x] **Step 2: Прогін**

Run: `.venv/Scripts/python -m pytest tests/test_screen_gates.py -v`
Expected: PASS. Особлива увага: `test_scout_rejects_alien_without_ocr` на
акордеонних фікстурах (ширина згорнутих колонок 0.08–0.10 проти нижньої межі
SCOUT_W_RANGE 0.115 — якщо якась фікстура на межі, звузити діапазон НЕ можна;
натомість дивись реальні ширини через band_segments і онови коментар у regions.py).

---

### Task 4: Інтеграція — конвеєр і тригер автопідбору

**Files:**
- Modify: `alu_gauntlet_helper/capture/capture_controller.py` (`_build_engine`)
- Modify: `alu_gauntlet_helper/services/session_manager.py` (`apply`)
- Test: `tests/test_session_manager.py`, `tests/test_engine.py` (прогін)

**Interfaces:**
- Consumes: `OpponentScoutExtractor`, `MapIconMatcher`, `MapsService.autocomplete("")`.
- Produces: скан скаут-екрана хоткеєм потрапляє в сесію; скани з полем `map` тригерять автопідбір (звуження треку + підбір авто відбуваються одразу після скану реванш-логу/пропозиції).

- [x] **Step 1: Тест тригера, що падає**

Додати в кінець `tests/test_session_manager.py`:

```python
def test_auto_pick_called_after_map_scan():
    # скан скаут-екрана (є лише карта) теж має запускати автопідбір:
    # він тягне resolve_tracks → звуження треку за часом (спека §6)
    from alu_gauntlet_helper.models import FieldGuess
    picked = []
    m = SessionManager(auto_pick=lambda s: picked.append(s))
    c = capture(1)
    c.map = FieldGuess(value=5, score=0.9)
    m.apply(result(c))
    assert picked == [m.active]
```

Run: `.venv/Scripts/python -m pytest tests/test_session_manager.py -v -k map_scan`
Expected: FAIL (`picked == []`).

- [x] **Step 2: Реалізація**

У `session_manager.py` в `apply` замінити рядок

```python
        has_opponent_data = any(c.opponent_time or c.opponent_car for c in result.captures)
```

на:

```python
        # карта зі скаут-екрана — теж дані суперника: тригерить resolve_tracks
        # (звуження за часом) і підбір одразу після скану
        has_opponent_data = any(c.opponent_time or c.opponent_car or c.map
                                for c in result.captures)
```

У `capture_controller.py`:

1. Імпорти:

```python
from alu_gauntlet_helper.screen_recognition.map_icon_matcher import MapIconMatcher
from alu_gauntlet_helper.screen_recognition.screens.opponent_scout import OpponentScoutExtractor
```

2. У `_build_engine` після рядка з `car_matcher`:

```python
        map_matcher = MapIconMatcher(APP_CONTEXT.maps_service.autocomplete(""))
```

і в список екстракторів — ПЕРЕД `ChallengeAccordionExtractor` (гейт «5 рівних
колонок» дешевий і специфічніший за акордеонний; порядок за ціною відмови
зберігається):

```python
            OpponentScoutExtractor(track_resolver, map_matcher),
```

- [x] **Step 3: Тести зелені**

Run: `.venv/Scripts/python -m pytest tests/test_session_manager.py tests/test_engine.py tests/test_captures_regression.py -v`
Expected: PASS.

- [x] **Step 4: Ручна перевірка (користувач)**

`python main.py` → у грі відкрити пропозицію суперника або реванш-лог → F8:
картки гонок наповнюються картами/треками/часами; для реванш-логу після скану
одразу спрацьовує звуження треку (трек «ймовірно» з «?», коли час влучає в
діапазон рівно одного треку карти) і чипи вибору треку.

---

### Task 5: Повний регрес і звірка зі спекою §3

**Files:** без нових змін.

- [x] **Step 1: Повний прогін**

Run: `.venv/Scripts/python -m pytest tests`
Expected: PASS.

- [x] **Step 2: Звірка зі спекою**

- §3 «екран 2»: гейт по геометрії 5 однакових панелей ✅; карта+трек текстом
  через наявний TrackResolver ✅.
- §3 «екран 3»: той самий гейт; іконка карти через matchTemplate по еталонах
  `resources/icons/maps` зі шкалюванням; час суперника ✅.
- Обидва вбудовані в конвеєр RecognitionEngine з гейтами до OCR ✅.
- Свідомо не робимо: `_is_uncertain` (збереження скріна для рев'ю) не враховує
  score поля `map` — шкала matchTemplate ≠ шкала OCR-матчерів, правильні збіги
  бувають зі скором 0.58; окремий поріг вводити немає потреби, поки не
  зʼявляться реальні промахи.

---

## Поправки після фінального ревʼю (внесені)

Фінальне ревʼю всієї частини «розпізнавання» знайшло крос-задачні проблеми;
виправлено однією хвилею фіксів:

1. **Поріг варіанта екрана** `SCOUT_TIME_PLATE_MIN_DARK` 0.25 → **0.40**:
   реальні виміри dark_fraction — екран 2: 0.13–0.24, екран 3: 0.56–0.58;
   старий поріг мав запас лише 0.011 до найтемнішої панелі екрана 2.
2. **Гард неоднозначності матчера:** марджин топ-1/топ-2 < 0.05 → score
   капиться до 0.6 (як `TrackResolver._AMBIGUITY_CAP`); чесні числа в
   докстрінгу (правильні збіги 0.55–0.94, мінімальний марджин ~0.03 — а не
   «0.87–0.90 проти ≤0.59», як стверджували прототипні заміри цього плану:
   вони робились на трохи іншому ROI).
3. **Конфлікт сесій за картою:** розбіжність `map` у слоті = інший
   суперник/челендж → детекція конфлікту (скани скаут-екранів різних
   суперників більше не зливаються — вимога спеки «дані не мержаться»).
   Тригер автопідбору розширено на скани з `map`/`track`.
4. **Карта звужує пошук треку (екран 2):** `resolve_track_only(text,
   map_name=...)` спершу шукає серед треків зматченої карти, з глобальним
   fallback-ом (страховка від хибної іконки); `MapIconMatcher.name_of()`.
5. Дрібне: `imdecode` замість `cv2.imread` (конвенція репо для не-ASCII
   шляхів), `OpponentScoutExtractor` у `scripts/survey_recognition.py`,
   рядок гейта в `docs/optimizing-recognition-speed.md`.

Твердження «діапазони ширин не перетинаються» у розділі вимірів стосується
ФАКТИЧНИХ ширин на фікстурах; самі константи `_COLUMN_W_RANGE` (0.05–0.13) і
`SCOUT_W_RANGE` (0.115–0.16) формально перетинаються на 0.115–0.13 — на інших
співвідношеннях сторін обидва гейти теоретично можуть спрацювати разом
(відкладено, зафіксовано в леджері).

**Відкрите (потрібен користувач):** RU-скріншоти екранів 2/3 — RU-шлях якоря
(«ГОНКА 1») не покритий фікстурами; якщо якір не прочитається, екстрактор
мовчки поверне [] на RU-екрані.
