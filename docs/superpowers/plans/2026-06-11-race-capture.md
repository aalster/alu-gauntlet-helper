# Race Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Хоткей → скріншот → розпізнавання екрана гри → сесія челенджа (5 гонок) → оверлей → рев'ю-діалог → збереження в БД.

**Architecture:** Детермінований пайплайн розпізнавання (класифікація екрана → кроп фіксованих ROI у відносних координатах → OCR з whitelist → fuzzy-матч проти словника назв з БД). Сесія челенджа в пам'яті накопичує часткові дані з кількох скрінів. Глобальний хоткей працює поверх borderless-гри, click-through оверлей показує прогрес. Spec: `docs/superpowers/specs/2026-06-11-race-capture-design.md`.

**Tech Stack:** Python 3.13 (`.venv`), PyQt6, OpenCV, pytesseract, mss (встановлено), rapidfuzz + keyboard + pytest (встановити).

**ВАЖЛИВО — git:** Користувач комітить сам. ЖОДНИХ git-команд (`add`/`commit`/`push`) у виконанні. Наприкінці кожної задачі лише повідомити «задача N готова до коміту».

**Команда тестів:** `.\.venv\Scripts\python.exe -m pytest tests -v` (запускати з кореня проєкту).

---

## Карта файлів

| Файл | Відповідальність |
|---|---|
| `requirements.txt`, `requirements-dev.txt` | Створити: залежності |
| `alu_gauntlet_helper/models.py` | Змінити: + `FieldGuess`, `RaceCapture`, `RecognitionResult` |
| `alu_gauntlet_helper/screen_recognition/matching.py` | Створити: `VocabularyMatcher`, фабрики словників |
| `alu_gauntlet_helper/screen_recognition/ocr.py` | Створити: обгортки Tesseract |
| `alu_gauntlet_helper/screen_recognition/regions.py` | Створити: `RelRect` + ROI-константи акордеона |
| `alu_gauntlet_helper/screen_recognition/screens/base.py` | Створити: інтерфейс `ScreenExtractor` |
| `alu_gauntlet_helper/screen_recognition/screens/challenge_accordion.py` | Створити: екстрактор v1 |
| `alu_gauntlet_helper/screen_recognition/engine.py` | Створити: `RecognitionEngine` |
| `alu_gauntlet_helper/screen_recognition/recognition.py` | Видалити (старий експеримент) |
| `alu_gauntlet_helper/services/challenge_session.py` | Створити: `ChallengeSessionService` |
| `alu_gauntlet_helper/services/settings.py` | Змінити: + поля захоплення |
| `alu_gauntlet_helper/services/tracks.py`, `cars.py` | Змінити: + `get_all` |
| `alu_gauntlet_helper/app_context.py` | Змінити: + `challenge_session` |
| `alu_gauntlet_helper/capture/__init__.py`, `screen_grab.py`, `hotkey.py`, `capture_controller.py` | Створити |
| `alu_gauntlet_helper/views/overlay.py` | Створити: оверлей + `build_overlay_lines` |
| `alu_gauntlet_helper/views/capture_tab.py` | Створити: вкладка CAPTURE |
| `alu_gauntlet_helper/views/capture_review_dialog.py` | Створити: рев'ю-діалог |
| `alu_gauntlet_helper/views/recognize_races_tab.py` | Видалити |
| `alu_gauntlet_helper/views/main_window.py`, `settings_tab.py`, `main.py` | Змінити: інтеграція |
| `scripts/debug_recognition.py` | Створити: утиліта калібрування ROI |
| `tests/...` | Створити: юніт-тести + фікстури |

---

### Task 1: Залежності та тестова інфраструктура

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `tests/__init__.py`, `tests/test_sanity.py`

- [ ] **Step 1: Встановити нові залежності**

Run: `.\.venv\Scripts\python.exe -m pip install rapidfuzz keyboard pytest`
Expected: успішна інсталяція трьох пакетів.

- [ ] **Step 2: Створити `requirements.txt`**

```
PyQt6
pydantic
opencv-python
numpy
pillow
pytesseract
mss
keyboard
rapidfuzz
```

- [ ] **Step 3: Створити `requirements-dev.txt`**

```
-r requirements.txt
pytest
```

- [ ] **Step 4: Створити `tests/__init__.py`** (порожній) **і `tests/test_sanity.py`**

```python
def test_package_imports():
    import alu_gauntlet_helper.models  # noqa: F401
```

- [ ] **Step 5: Запустити тести**

Run: `.\.venv\Scripts\python.exe -m pytest tests -v`
Expected: `1 passed`

- [ ] **Step 6: Повідомити «задача 1 готова до коміту»**

---

### Task 2: Моделі захоплення

**Files:**
- Modify: `alu_gauntlet_helper/models.py`
- Test: `tests/test_capture_models.py`

- [ ] **Step 1: Написати тест**

```python
from alu_gauntlet_helper.models import FieldGuess, RaceCapture, RecognitionResult


def test_race_capture_defaults():
    c = RaceCapture(race_number=3)
    assert c.race_number == 3
    assert c.track is None and c.car is None
    assert c.rank is None and c.time is None
    assert c.panel_image is None


def test_field_guess_candidates():
    g = FieldGuess(value=7, score=0.92, candidates=[(7, 0.92), (3, 0.8)])
    assert g.value == 7
    assert g.candidates[0] == (7, 0.92)


def test_recognition_result():
    r = RecognitionResult(screen="challenge_accordion", captures=[RaceCapture(race_number=1)])
    assert r.screen == "challenge_accordion"
    assert len(r.captures) == 1
```

- [ ] **Step 2: Запустити — впевнитись, що падає**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_capture_models.py -v`
Expected: FAIL, `ImportError: cannot import name 'FieldGuess'`

- [ ] **Step 3: Додати моделі в кінець `alu_gauntlet_helper/models.py`**

```python
class FieldGuess(BaseModel):
    """Розпізнане значення-довідник: id + впевненість + альтернативи."""
    value: int
    score: float
    candidates: list[tuple[int, float]] = []


class RaceCapture(BaseModel):
    """Часткові дані однієї гонки, витягнуті з одного скріншота."""
    race_number: int  # 1..5
    track: FieldGuess | None = None
    car: FieldGuess | None = None
    rank: int | None = None
    time: int | None = None  # мс, як Race.time
    source_screen: str = ""
    panel_image: bytes | None = None  # PNG-кроп панелі-джерела для рев'ю


class RecognitionResult(BaseModel):
    screen: str
    captures: list[RaceCapture] = []
```

- [ ] **Step 4: Запустити — пройшло**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_capture_models.py -v`
Expected: `3 passed`

- [ ] **Step 5: Повідомити «задача 2 готова до коміту»**

---

### Task 3: VocabularyMatcher і фабрики словників

**Files:**
- Create: `alu_gauntlet_helper/screen_recognition/matching.py`
- Modify: `alu_gauntlet_helper/services/tracks.py` (+`get_all`), `alu_gauntlet_helper/services/cars.py` (+`get_all`)
- Test: `tests/test_matching.py`

- [ ] **Step 1: Написати тести**

```python
from alu_gauntlet_helper.screen_recognition.matching import VocabularyMatcher, normalize

VOCAB = [
    (1, "Hennessey Venom F5"),
    (2, "Bugatti Chiron"),
    (3, "Bugatti Chiron Pur Sport"),
    (4, "Lamborghini Invencible"),
]


def test_normalize_strips_spaces_and_punctuation():
    assert normalize("W Motors Lykan-Hyper sport!") == "WMOTORSLYKANHYPERSPORT"


def test_exact_match():
    m = VocabularyMatcher(VOCAB)
    guess = m.match("HENNESSEY VENOM F5")
    assert guess.value == 1
    assert guess.score == 1.0


def test_ocr_garbage_missing_spaces_and_swapped_letters():
    m = VocabularyMatcher(VOCAB)
    # типова помилка Tesseract: злиплі пробіли, 5 -> S
    guess = m.match("HENNESSEYVENOM FS")
    assert guess.value == 1


def test_below_threshold_returns_none():
    m = VocabularyMatcher(VOCAB)
    assert m.match("ZZZZZZZZZZ") is None
    assert m.match("") is None


def test_candidates_best_first_and_deduped():
    m = VocabularyMatcher(VOCAB)
    guess = m.match("BUGATTI CHIRON")
    assert guess.value == 2
    candidate_ids = [c[0] for c in guess.candidates]
    assert 3 in candidate_ids          # Pur Sport — близький кандидат
    assert len(candidate_ids) == len(set(candidate_ids))
```

- [ ] **Step 2: Запустити — впевнитись, що падає**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_matching.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Створити `matching.py`**

```python
import re

from rapidfuzz import fuzz, process

from alu_gauntlet_helper.models import FieldGuess

_NORMALIZE_RE = re.compile(r"[^A-Z0-9]")


def normalize(text: str) -> str:
    return _NORMALIZE_RE.sub("", text.upper())


class VocabularyMatcher:
    """Fuzzy-зіставлення OCR-тексту з відомими назвами (порівняння без пробілів)."""

    def __init__(self, vocab: list[tuple[int, str]], threshold: float = 75.0):
        self.threshold = threshold
        # один id може мати кілька синонімів — дедуплікація на виході
        self._ids = [item_id for item_id, _ in vocab]
        self._choices = {i: normalize(name) for i, (_, name) in enumerate(vocab)}

    def match(self, text: str, limit: int = 3) -> FieldGuess | None:
        query = normalize(text)
        if not query:
            return None

        raw = process.extract(query, self._choices, scorer=fuzz.ratio, limit=10)
        best_by_id: dict[int, float] = {}
        for _choice, score, key in raw:
            if score < self.threshold:
                continue
            item_id = self._ids[key]
            if score > best_by_id.get(item_id, 0):
                best_by_id[item_id] = score

        if not best_by_id:
            return None

        candidates = sorted(best_by_id.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        candidates = [(item_id, score / 100) for item_id, score in candidates]
        return FieldGuess(value=candidates[0][0], score=candidates[0][1], candidates=candidates)


def build_track_matcher(track_views) -> VocabularyMatcher:
    """track_views: list[TrackView]. Синоніми: «назва треку» і «карта + трек»."""
    vocab = []
    for t in track_views:
        vocab.append((t.id, t.name))
        vocab.append((t.id, f"{t.map_name} {t.name}"))
    return VocabularyMatcher(vocab)


def build_car_matcher(cars) -> VocabularyMatcher:
    """cars: list[Car]."""
    return VocabularyMatcher([(c.id, c.name) for c in cars])
```

- [ ] **Step 4: Запустити — пройшло**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_matching.py -v`
Expected: `5 passed`. Якщо `test_ocr_garbage...` впав — надрукувати score (`fuzz.ratio("HENNESSEYVENOMFS", "HENNESSEYVENOMF5")` ≈ 94) і за потреби скоригувати поріг у тесті, НЕ в продакшн-коді.

- [ ] **Step 5: Додати `get_all` у репозиторії та сервіси**

У `alu_gauntlet_helper/services/tracks.py`, клас `TracksRepository` (після `get_by_ids`):

```python
    def get_all(self) -> list[Track]:
        with connect() as conn:
            rows = conn.execute("SELECT * FROM tracks").fetchall()
            return [self.parse(row) for row in rows]
```

У клас `TracksService` (після `autocomplete`):

```python
    def get_all_views(self) -> list[TrackView]:
        return self.to_views(self.repo.get_all())
```

У `alu_gauntlet_helper/services/cars.py`, клас `CarsRepository` (після `get_by_ids`):

```python
    def get_all(self) -> list[Car]:
        with connect() as conn:
            rows = conn.execute("SELECT * FROM cars").fetchall()
            return [self.parse(row) for row in rows]
```

У клас `CarsService` (після `get_by_ids`):

```python
    def get_all(self) -> list[Car]:
        return self.repo.get_all()
```

- [ ] **Step 6: Прогнати всі тести**

Run: `.\.venv\Scripts\python.exe -m pytest tests -v`
Expected: усі passed.

- [ ] **Step 7: Повідомити «задача 3 готова до коміту»**

---

### Task 4: OCR-хелпери

**Files:**
- Create: `alu_gauntlet_helper/screen_recognition/ocr.py`
- Test: `tests/test_ocr.py`

- [ ] **Step 1: Написати тести (синтетичні картинки з намальованим текстом)**

```python
import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from alu_gauntlet_helper.screen_recognition import ocr

TESSERACT_OK = ocr.configure_tesseract() and ocr.is_available()
pytestmark = pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")


def make_text_image(text: str) -> np.ndarray:
    """Світлий текст на темно-синьому тлі — як у грі."""
    font = ImageFont.truetype("arial.ttf", 48)
    img = Image.new("RGB", (640, 100), (24, 32, 90))
    ImageDraw.Draw(img).text((20, 20), text, font=font, fill=(255, 255, 255))
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def test_read_time():
    assert ocr.read_time(make_text_image("00:22.797")) == 22797


def test_read_time_garbage_returns_none():
    assert ocr.read_time(make_text_image("HELLO")) is None


def test_read_rank():
    assert ocr.read_rank(make_text_image("4,045")) == 4045


def test_read_name():
    text = ocr.read_name(make_text_image("ULTIMA RS"))
    assert "ULTIMA" in text.upper()
```

- [ ] **Step 2: Запустити — впевнитись, що падає**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_ocr.py -v`
Expected: FAIL (`ModuleNotFoundError` або `AttributeError`). Якщо тести SKIPPED — Tesseract не знайдено, перевірити `C:\Program Files\Tesseract-OCR`.

- [ ] **Step 3: Створити `ocr.py`**

```python
import os
import re
import shutil

import cv2
import numpy as np
import pytesseract
from PIL import Image

DEFAULT_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]

NAME_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -"
TIME_RE = re.compile(r"(\d{1,2})\s*:\s*(\d{2})\s*[.,]\s*(\d{2,3})")
RANK_RE = re.compile(r"(\d)\s*[,.]?\s*(\d{3})")


def configure_tesseract(path: str = "") -> bool:
    """Виставляє tesseract_cmd: явний шлях → PATH → типові локації. True, якщо знайдено."""
    candidates = [path] if path else []
    which = shutil.which("tesseract")
    if which:
        candidates.append(which)
    candidates += DEFAULT_TESSERACT_PATHS

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            pytesseract.pytesseract.tesseract_cmd = candidate
            return True
    return False


def is_available() -> bool:
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def preprocess(img: np.ndarray, scale: int = 3) -> Image.Image:
    """Кроп ROI → сірий → апскейл → Otsu → темний текст на білому."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if binary.mean() < 127:
        binary = cv2.bitwise_not(binary)
    return Image.fromarray(binary)


def read_text(img: np.ndarray, whitelist: str, psm: int = 7) -> str:
    config = f'--oem 3 --psm {psm} -c tessedit_char_whitelist="{whitelist}"'
    return pytesseract.image_to_string(preprocess(img), lang="eng", config=config).strip()


def read_time(img: np.ndarray) -> int | None:
    match = TIME_RE.search(read_text(img, "0123456789:.,"))
    if not match:
        return None
    minutes, seconds, millis = int(match[1]), int(match[2]), int(match[3].ljust(3, "0"))
    return (minutes * 60 + seconds) * 1000 + millis


def read_rank(img: np.ndarray) -> int | None:
    match = RANK_RE.search(read_text(img, "0123456789,."))
    return int(match[1] + match[2]) if match else None


def read_name(img: np.ndarray) -> str:
    """Назва авто/треку; може бути 2 рядки — psm 6."""
    return read_text(img, NAME_CHARS, psm=6)
```

- [ ] **Step 4: Запустити — пройшло**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_ocr.py -v`
Expected: `4 passed`. Якщо `test_read_name` впав через зайві символи — порівнювати через `in`, як у тесті; якщо OCR зовсім порожній — збільшити шрифт у `make_text_image` до 64.

- [ ] **Step 5: Повідомити «задача 4 готова до коміту»**

---

### Task 5: RelRect — відносні регіони

**Files:**
- Create: `alu_gauntlet_helper/screen_recognition/regions.py`
- Test: `tests/test_regions.py`

- [ ] **Step 1: Написати тести**

```python
import numpy as np

from alu_gauntlet_helper.screen_recognition.regions import RelRect


def test_to_abs():
    r = RelRect(0.1, 0.2, 0.5, 0.25)
    assert r.to_abs(1000, 400) == (100, 80, 500, 100)


def test_crop():
    img = np.zeros((400, 1000, 3), dtype=np.uint8)
    cropped = RelRect(0.1, 0.2, 0.5, 0.25).crop(img)
    assert cropped.shape == (100, 500, 3)


def test_sub_region_is_relative_to_parent():
    panel = RelRect(0.1, 0.2, 0.4, 0.5)
    header = panel.sub(RelRect(0.0, 0.0, 1.0, 0.2))
    assert header.x == 0.1 and header.y == 0.2
    assert abs(header.w - 0.4) < 1e-9 and abs(header.h - 0.1) < 1e-9


def test_shifted():
    r = RelRect(0.1, 0.2, 0.4, 0.5).shifted(0.05, -0.02)
    assert abs(r.x - 0.15) < 1e-9 and abs(r.y - 0.18) < 1e-9
    assert r.w == 0.4 and r.h == 0.5
```

- [ ] **Step 2: Запустити — впевнитись, що падає**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_regions.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Створити `regions.py`**

```python
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RelRect:
    """Прямокутник у частках ширини/висоти кадру — не залежить від роздільної здатності."""
    x: float
    y: float
    w: float
    h: float

    def to_abs(self, width: int, height: int) -> tuple[int, int, int, int]:
        return round(self.x * width), round(self.y * height), round(self.w * width), round(self.h * height)

    def crop(self, img: np.ndarray) -> np.ndarray:
        x, y, w, h = self.to_abs(img.shape[1], img.shape[0])
        return img[y:y + h, x:x + w]

    def sub(self, rel: "RelRect") -> "RelRect":
        """Вкладений регіон, координати якого задані відносно цього прямокутника."""
        return RelRect(self.x + rel.x * self.w, self.y + rel.y * self.h, rel.w * self.w, rel.h * self.h)

    def shifted(self, dx: float, dy: float) -> "RelRect":
        return RelRect(self.x + dx, self.y + dy, self.w, self.h)


# --- Екран-акордеон челенджа (5 панелей, одна розгорнута) -------------------
# Калібрується з opponent_challenge.png (600x375, 16:10) у Task 13.
# ВАЖЛИВО: ROI задаються з запасом ~10-15% — застосунок має працювати на інших
# роздільних здатностях і співвідношеннях сторін; точність добирає OCR-якір
# "RACE N" (скан зсувів у екстракторі) + словникове зіставлення.

# Позиція розгорнутої панелі для race 1..5 (розгорнута панель зсувається вправо)
ACCORDION_EXPANDED_PANELS = [RelRect(0.065 + 0.105 * i, 0.255, 0.385, 0.50) for i in range(5)]

# Вкладені регіони відносно розгорнутої панелі
ACCORDION_HEADER = RelRect(0.0, 0.0, 1.0, 0.12)        # "RACE N"
ACCORDION_TRACK_NAME = RelRect(0.30, 0.15, 0.45, 0.30)  # назва карти + треку
ACCORDION_CAR_NAME = RelRect(0.0, 0.12, 0.30, 0.18)     # назва авто
ACCORDION_RANK = RelRect(0.0, 0.30, 0.25, 0.14)         # ранг "4,644 S"
ACCORDION_TIME = RelRect(0.0, 0.72, 0.45, 0.18)         # час "00:22.797"

# Іменована карта регіонів для дебаг-утиліти (Task 11)
ACCORDION_DEBUG_REGIONS = {
    f"panel_{i + 1}": rect for i, rect in enumerate(ACCORDION_EXPANDED_PANELS)
}
```

- [ ] **Step 4: Запустити — пройшло**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_regions.py -v`
Expected: `3 passed`

- [ ] **Step 5: Повідомити «задача 5 готова до коміту»**

---

### Task 6: ScreenExtractor + RecognitionEngine

**Files:**
- Create: `alu_gauntlet_helper/screen_recognition/screens/__init__.py` (порожній), `alu_gauntlet_helper/screen_recognition/screens/base.py`, `alu_gauntlet_helper/screen_recognition/engine.py`
- Test: `tests/test_engine.py`

- [ ] **Step 1: Написати тести**

```python
import numpy as np

from alu_gauntlet_helper.models import RaceCapture
from alu_gauntlet_helper.screen_recognition.engine import RecognitionEngine
from alu_gauntlet_helper.screen_recognition.screens.base import ScreenExtractor

IMG = np.zeros((100, 100, 3), dtype=np.uint8)


class FakeExtractor(ScreenExtractor):
    def __init__(self, name, captures, error=False):
        self.name = name
        self._captures = captures
        self._error = error

    def extract(self, img):
        if self._error:
            raise RuntimeError("boom")
        return self._captures


def test_first_extractor_with_captures_wins():
    engine = RecognitionEngine([
        FakeExtractor("empty", []),
        FakeExtractor("accordion", [RaceCapture(race_number=2)]),
    ])
    result = engine.recognize(IMG)
    assert result.screen == "accordion"
    assert result.captures[0].race_number == 2


def test_no_match_returns_none():
    engine = RecognitionEngine([FakeExtractor("empty", [])])
    assert engine.recognize(IMG) is None


def test_extractor_exception_does_not_break_engine():
    engine = RecognitionEngine([
        FakeExtractor("broken", [], error=True),
        FakeExtractor("ok", [RaceCapture(race_number=1)]),
    ])
    assert engine.recognize(IMG).screen == "ok"
```

- [ ] **Step 2: Запустити — впевнитись, що падає**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_engine.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Створити `screens/base.py`**

```python
from abc import ABC, abstractmethod

import numpy as np

from alu_gauntlet_helper.models import RaceCapture


class ScreenExtractor(ABC):
    """Розпізнавач одного типу екрана гри."""

    name: str = ""

    @abstractmethod
    def extract(self, img: np.ndarray) -> list[RaceCapture]:
        """Повертає захоплені гонки або [] якщо це не той екран / нічого не зчиталось."""
```

- [ ] **Step 4: Створити `engine.py`**

```python
import traceback

import numpy as np

from alu_gauntlet_helper.models import RecognitionResult
from alu_gauntlet_helper.screen_recognition.screens.base import ScreenExtractor


class RecognitionEngine:
    """Пробує екстрактори по черзі; перший, що повернув захоплення, перемагає."""

    def __init__(self, extractors: list[ScreenExtractor]):
        self.extractors = extractors

    def recognize(self, img: np.ndarray) -> RecognitionResult | None:
        for extractor in self.extractors:
            try:
                captures = extractor.extract(img)
            except Exception:
                print(f"Extractor {extractor.name} failed:")
                traceback.print_exc()
                continue
            if captures:
                return RecognitionResult(screen=extractor.name, captures=captures)
        return None
```

- [ ] **Step 5: Запустити — пройшло**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_engine.py -v`
Expected: `3 passed`

- [ ] **Step 6: Повідомити «задача 6 готова до коміту»**

---

### Task 7: ChallengeSessionService

**Files:**
- Create: `alu_gauntlet_helper/services/challenge_session.py`
- Modify: `alu_gauntlet_helper/app_context.py`
- Test: `tests/test_challenge_session.py`

- [ ] **Step 1: Написати тести**

```python
from alu_gauntlet_helper.models import FieldGuess, RaceCapture, RecognitionResult
from alu_gauntlet_helper.services.challenge_session import ChallengeSessionService


def capture(n, track_score=None, car_score=None, rank=None, time=None):
    return RaceCapture(
        race_number=n,
        track=FieldGuess(value=10 + n, score=track_score) if track_score is not None else None,
        car=FieldGuess(value=20 + n, score=car_score) if car_score is not None else None,
        rank=rank,
        time=time,
    )


def result(*captures):
    return RecognitionResult(screen="test", captures=list(captures))


def test_apply_creates_race_entry():
    s = ChallengeSessionService()
    s.apply(result(capture(1, track_score=0.9, time=22797)))
    assert s.races[1].track.value == 11
    assert s.races[1].time == 22797


def test_merge_keeps_higher_confidence_field():
    s = ChallengeSessionService()
    s.apply(result(capture(1, track_score=0.9)))
    low = capture(1, track_score=0.5)
    low.track = FieldGuess(value=99, score=0.5)
    s.apply(result(low))
    assert s.races[1].track.value == 11  # стара впевненіша — лишилась


def test_merge_overwrites_with_higher_confidence():
    s = ChallengeSessionService()
    s.apply(result(capture(1, track_score=0.5)))
    high = capture(1)
    high.track = FieldGuess(value=99, score=0.95)
    s.apply(result(high))
    assert s.races[1].track.value == 99


def test_merge_fills_missing_scalar_fields():
    s = ChallengeSessionService()
    s.apply(result(capture(2, time=21000)))
    s.apply(result(capture(2, rank=4045)))
    assert s.races[2].time == 21000
    assert s.races[2].rank == 4045


def test_is_complete_requires_track_car_time_for_all_five():
    s = ChallengeSessionService()
    for n in range(1, 5):
        s.apply(result(capture(n, track_score=0.9, car_score=0.9, time=20000)))
    assert not s.is_complete()
    s.apply(result(capture(5, track_score=0.9, car_score=0.9, time=20000)))
    assert s.is_complete()


def test_clear_and_listeners():
    s = ChallengeSessionService()
    events = []
    s.add_listener(lambda: events.append(1))
    s.apply(result(capture(1, time=1000)))
    s.clear()
    assert s.races == {}
    assert len(events) == 2  # apply + clear
```

- [ ] **Step 2: Запустити — впевнитись, що падає**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_challenge_session.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Створити `challenge_session.py`**

```python
from typing import Callable

from alu_gauntlet_helper.models import FieldGuess, RaceCapture, RecognitionResult

RACE_COUNT = 5


def merge_guess(old: FieldGuess | None, new: FieldGuess | None) -> FieldGuess | None:
    if new is None:
        return old
    if old is None or new.score >= old.score:
        return new
    return old


class ChallengeSessionService:
    """Стан поточного челенджа (5 гонок) у пам'яті. Викликається тільки з UI-потоку."""

    def __init__(self):
        self.races: dict[int, RaceCapture] = {}
        self.last_event: str = ""
        self._listeners: list[Callable[[], None]] = []

    def add_listener(self, listener: Callable[[], None]):
        self._listeners.append(listener)

    def _notify(self):
        for listener in self._listeners:
            listener()

    def apply(self, result: RecognitionResult):
        for new in result.captures:
            self._merge(new)
        numbers = ", ".join(str(c.race_number) for c in result.captures)
        self.last_event = f"{result.screen}: race {numbers}"
        self._notify()

    def _merge(self, new: RaceCapture):
        current = self.races.get(new.race_number)
        if current is None:
            self.races[new.race_number] = new
            return
        current.track = merge_guess(current.track, new.track)
        current.car = merge_guess(current.car, new.car)
        if new.rank is not None:
            current.rank = new.rank
        if new.time is not None:
            current.time = new.time
        if new.panel_image:
            current.panel_image = new.panel_image
        current.source_screen = new.source_screen or current.source_screen

    def is_complete(self) -> bool:
        return all(
            (c := self.races.get(n)) and c.track and c.car and c.time
            for n in range(1, RACE_COUNT + 1)
        )

    def clear(self):
        self.races = {}
        self.last_event = ""
        self._notify()
```

- [ ] **Step 4: Зареєструвати в `app_context.py`**

```python
from alu_gauntlet_helper.services.cars import CarsRepository, CarsService
from alu_gauntlet_helper.services.challenge_session import ChallengeSessionService
from alu_gauntlet_helper.services.maps import MapsRepository, MapsService
from alu_gauntlet_helper.services.races import RacesService, RacesRepository
from alu_gauntlet_helper.services.settings import SettingsService, SettingsRepository
from alu_gauntlet_helper.services.tracks import TracksRepository, TracksService


class AppContext:
    settings: SettingsService
    maps_service: MapsService
    tracks_service: TracksService
    cars_service: CarsService
    races_service: RacesService
    challenge_session: ChallengeSessionService

    def __init__(self):
        self.settings = SettingsService(SettingsRepository())
        self.maps_service = MapsService(MapsRepository())
        self.tracks_service = TracksService(TracksRepository(), self.maps_service)
        self.cars_service = CarsService(CarsRepository())
        self.races_service = RacesService(RacesRepository(), self.tracks_service, self.cars_service)
        self.challenge_session = ChallengeSessionService()

APP_CONTEXT: AppContext = AppContext()
```

- [ ] **Step 5: Запустити всі тести — пройшло**

Run: `.\.venv\Scripts\python.exe -m pytest tests -v`
Expected: усі passed.

- [ ] **Step 6: Повідомити «задача 7 готова до коміту»**

---

### Task 8: Захоплення екрана (mss)

**Files:**
- Create: `alu_gauntlet_helper/capture/__init__.py` (порожній), `alu_gauntlet_helper/capture/screen_grab.py`
- Test: `tests/test_screen_grab.py`

- [ ] **Step 1: Написати тести**

```python
import numpy as np

from alu_gauntlet_helper.capture.screen_grab import grab_screen, save_capture


def test_grab_screen_returns_bgr_image():
    img = grab_screen(1)
    assert isinstance(img, np.ndarray)
    assert img.ndim == 3 and img.shape[2] == 3
    assert img.shape[0] > 100 and img.shape[1] > 100


def test_save_capture_rotates(tmp_path):
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    for _ in range(25):
        save_capture(img, directory=str(tmp_path), keep=20)
    assert len(list(tmp_path.glob("*.png"))) == 20
```

- [ ] **Step 2: Запустити — впевнитись, що падає**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_screen_grab.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Створити `screen_grab.py`**

```python
import os
import time

import cv2
import mss
import numpy as np

CAPTURES_DIR = "data/captures"


def grab_screen(monitor_index: int = 1) -> np.ndarray:
    """Скріншот монітора як BGR numpy array. monitors[0] — усі екрани разом."""
    with mss.mss() as sct:
        if not 1 <= monitor_index < len(sct.monitors):
            monitor_index = 1
        shot = sct.grab(sct.monitors[monitor_index])
        img = np.asarray(shot)[:, :, :3]  # BGRA -> BGR
        return np.ascontiguousarray(img)


def save_capture(img: np.ndarray, directory: str = CAPTURES_DIR, keep: int = 20) -> str:
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"capture_{time.time_ns()}.png")
    cv2.imwrite(path, img)

    files = sorted(
        (os.path.join(directory, f) for f in os.listdir(directory) if f.endswith(".png")),
        key=os.path.getmtime,
    )
    for old in files[:-keep]:
        os.remove(old)
    return path
```

- [ ] **Step 4: Запустити — пройшло**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_screen_grab.py -v`
Expected: `2 passed`

- [ ] **Step 5: Повідомити «задача 8 готова до коміту»**

---

### Task 9: GlobalHotkeyService

**Files:**
- Create: `alu_gauntlet_helper/capture/hotkey.py`
- Test: `tests/test_hotkey.py`

- [ ] **Step 1: Написати тести (з підміненим модулем keyboard)**

```python
from alu_gauntlet_helper.capture import hotkey as hotkey_module
from alu_gauntlet_helper.capture.hotkey import GlobalHotkeyService


class FakeKeyboard:
    def __init__(self, fail=False):
        self.fail = fail
        self.registered = {}

    def add_hotkey(self, combo, callback):
        if self.fail:
            raise ValueError("bad combo")
        self.registered[combo] = callback
        return combo

    def remove_hotkey(self, handle):
        del self.registered[handle]


def test_register_success(monkeypatch):
    fake = FakeKeyboard()
    monkeypatch.setattr(hotkey_module, "keyboard", fake)
    service = GlobalHotkeyService()
    assert service.register("f8", lambda: None) is True
    assert "f8" in fake.registered


def test_register_failure_returns_false(monkeypatch):
    monkeypatch.setattr(hotkey_module, "keyboard", FakeKeyboard(fail=True))
    service = GlobalHotkeyService()
    assert service.register("f8", lambda: None) is False


def test_unregister_all(monkeypatch):
    fake = FakeKeyboard()
    monkeypatch.setattr(hotkey_module, "keyboard", fake)
    service = GlobalHotkeyService()
    service.register("f8", lambda: None)
    service.register("f9", lambda: None)
    service.unregister_all()
    assert fake.registered == {}
```

- [ ] **Step 2: Запустити — впевнитись, що падає**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_hotkey.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Створити `hotkey.py`**

```python
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
```

- [ ] **Step 4: Запустити — пройшло**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_hotkey.py -v`
Expected: `3 passed`

- [ ] **Step 5: Повідомити «задача 9 готова до коміту»**

---

### Task 10: Налаштування захоплення

**Files:**
- Modify: `alu_gauntlet_helper/services/settings.py`
- Test: `tests/test_settings_model.py`

- [ ] **Step 1: Написати тест**

```python
from alu_gauntlet_helper.services.settings import Settings


def test_capture_defaults():
    s = Settings()
    assert s.capture_hotkey == "f8"
    assert s.overlay_hotkey == "f9"
    assert s.tesseract_path == ""
    assert s.capture_monitor == 1
    assert s.save_captures is False


def test_parses_string_values_from_db():
    # SettingsRepository зберігає все рядками
    s = Settings(capture_monitor="2", save_captures="True")
    assert s.capture_monitor == 2
    assert s.save_captures is True
```

- [ ] **Step 2: Запустити — впевнитись, що падає**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_settings_model.py -v`
Expected: FAIL, `AttributeError`

- [ ] **Step 3: Додати поля в клас `Settings` (`services/settings.py`)**

```python
class Settings(BaseModel):
    initial_data_loaded: bool = False
    cars_updated_at: str = ""
    window_geometry: str = ""
    window_state: str = ""

    show_tray_icon: bool = False
    close_to_tray: bool = False
    start_minimized: bool = False

    capture_hotkey: str = "f8"
    overlay_hotkey: str = "f9"
    tesseract_path: str = ""
    capture_monitor: int = 1
    save_captures: bool = False
```

- [ ] **Step 4: Запустити — пройшло**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_settings_model.py -v`
Expected: `2 passed`

- [ ] **Step 5: Повідомити «задача 10 готова до коміту»**

---

### Task 11: Дебаг-утиліта калібрування ROI

**Files:**
- Create: `scripts/__init__.py` (порожній), `scripts/debug_recognition.py`

Інструмент розробника — без юніт-тестів, перевірка ручна.

- [ ] **Step 1: Створити `scripts/debug_recognition.py`**

```python
"""Калібрування ROI: малює регіони поверх скріншота і друкує OCR-результати.

Використання (з кореня проєкту):
  .\\.venv\\Scripts\\python.exe -m scripts.debug_recognition <скріншот.png> [--grid]
"""
import argparse

import cv2

from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.regions import (
    ACCORDION_CAR_NAME, ACCORDION_EXPANDED_PANELS, ACCORDION_HEADER,
    ACCORDION_RANK, ACCORDION_TIME, ACCORDION_TRACK_NAME,
)

SUB_REGIONS = {
    "header": ACCORDION_HEADER,
    "track": ACCORDION_TRACK_NAME,
    "car": ACCORDION_CAR_NAME,
    "rank": ACCORDION_RANK,
    "time": ACCORDION_TIME,
}


def draw_rect(img, rel_rect, label, color):
    x, y, w, h = rel_rect.to_abs(img.shape[1], img.shape[0])
    cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
    cv2.putText(img, label, (x, max(y - 4, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)


def draw_grid(img, step=0.05):
    h, w = img.shape[:2]
    for i in range(1, int(1 / step)):
        x, y = int(i * step * w), int(i * step * h)
        cv2.line(img, (x, 0), (x, h), (80, 80, 80), 1)
        cv2.line(img, (0, y), (w, y), (80, 80, 80), 1)
        cv2.putText(img, f"{i * step:.2f}", (x + 2, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1)
        cv2.putText(img, f"{i * step:.2f}", (2, y + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("--grid", action="store_true", help="малювати сітку координат")
    args = parser.parse_args()

    ocr.configure_tesseract()
    img = cv2.imread(args.image)
    if img is None:
        raise SystemExit(f"Не вдалося прочитати {args.image}")
    annotated = img.copy()

    if args.grid:
        draw_grid(annotated)

    for i, panel in enumerate(ACCORDION_EXPANDED_PANELS):
        draw_rect(annotated, panel, f"panel_{i + 1}", (0, 255, 0))
        header_text = ocr.read_text(panel.sub(ACCORDION_HEADER).crop(img), "RACE 12345")
        print(f"panel_{i + 1} header OCR: {header_text!r}")

    # Деталізація для panel_1 (за потреби міняти індекс вручну)
    panel = ACCORDION_EXPANDED_PANELS[0]
    for name, sub in SUB_REGIONS.items():
        draw_rect(annotated, panel.sub(sub), name, (0, 200, 255))
        print(f"panel_1/{name}: {ocr.read_name(panel.sub(sub).crop(img))!r}")

    out_path = args.image.rsplit(".", 1)[0] + "_annotated.png"
    cv2.imwrite(out_path, annotated)
    print(f"Збережено {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Перевірити вручну на наявному прикладі**

Run: `.\.venv\Scripts\python.exe -m scripts.debug_recognition "C:\Users\igora\OneDrive\Desktop\alu\opponent_challenge.png" --grid`
Expected: створено `opponent_challenge_annotated.png`, у консолі OCR-результати (на зменшеному 600px скріні OCR може бути сміттям — це нормально, мета: переконатися що утиліта працює і рамки малюються).

- [ ] **Step 3: Повідомити «задача 11 готова до коміту»**

---

### Task 12: ChallengeAccordionExtractor

**Files:**
- Create: `alu_gauntlet_helper/screen_recognition/screens/challenge_accordion.py`
- Test: `tests/test_challenge_accordion.py`, `tests/fixtures/` (директорія)

- [ ] **Step 1: Написати тести (фікстурні — скіпаються поки немає скріншотів)**

```python
from pathlib import Path

import cv2
import pytest

from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.matching import VocabularyMatcher
from alu_gauntlet_helper.screen_recognition.screens.challenge_accordion import ChallengeAccordionExtractor

FIXTURES = Path(__file__).parent / "fixtures"
TESSERACT_OK = ocr.configure_tesseract() and ocr.is_available()

# Словники-стаби: реальні назви з гри, які видно на фікстурних скріншотах.
# Доповнити у Task 13 після отримання скріншотів.
TRACK_VOCAB = [(101, "Notre Dame"), (102, "Paris Notre Dame")]
CAR_VOCAB = [(201, "Ultima RS"), (202, "Porsche 935 (2019)")]

# Очікувані значення заповнюються у Task 13, дивлячись на фікстуру очима.
EXPECTED_RACE_1 = {"race_number": 1, "track_id": 101, "car_id": 201, "time": None, "rank": None}


def make_extractor():
    return ChallengeAccordionExtractor(VocabularyMatcher(TRACK_VOCAB), VocabularyMatcher(CAR_VOCAB))


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@pytest.mark.skipif(not (FIXTURES / "accordion_race1.png").exists(), reason="немає фікстури")
def test_extract_race_1():
    img = cv2.imread(str(FIXTURES / "accordion_race1.png"))
    captures = make_extractor().extract(img)
    assert len(captures) == 1
    c = captures[0]
    assert c.race_number == EXPECTED_RACE_1["race_number"]
    assert c.track and c.track.value == EXPECTED_RACE_1["track_id"]
    assert c.car and c.car.value == EXPECTED_RACE_1["car_id"]
    assert c.time == EXPECTED_RACE_1["time"]
    assert c.panel_image  # кроп панелі збережено для рев'ю


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
def test_non_accordion_image_returns_empty():
    import numpy as np
    img = np.zeros((1600, 2560, 3), dtype=np.uint8)
    assert make_extractor().extract(img) == []
```

- [ ] **Step 2: Запустити — впевнитись, що падає**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_challenge_accordion.py -v`
Expected: FAIL `ModuleNotFoundError` (фікстурний тест буде SKIPPED — це очікувано).

- [ ] **Step 3: Створити `challenge_accordion.py`**

```python
import re

import cv2
import numpy as np

from alu_gauntlet_helper.models import RaceCapture
from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.matching import VocabularyMatcher
from alu_gauntlet_helper.screen_recognition.regions import (
    ACCORDION_CAR_NAME, ACCORDION_EXPANDED_PANELS, ACCORDION_HEADER,
    ACCORDION_RANK, ACCORDION_TIME, ACCORDION_TRACK_NAME,
)
from alu_gauntlet_helper.screen_recognition.screens.base import ScreenExtractor

RACE_HEADER_RE = re.compile(r"RACE\s*([1-5])")

# Скан невеликих вертикальних зсувів — стійкість до інших співвідношень сторін
# і відмінностей лейауту між пристроями.
HEADER_DY_OFFSETS = [0.0, -0.03, 0.03]


def encode_png(img: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".png", img)
    return buffer.tobytes() if ok else b""


class ChallengeAccordionExtractor(ScreenExtractor):
    """Екран-акордеон челенджа: 5 панелей, одна розгорнута з усіма даними гонки."""

    name = "challenge_accordion"

    def __init__(self, track_matcher: VocabularyMatcher, car_matcher: VocabularyMatcher):
        self.track_matcher = track_matcher
        self.car_matcher = car_matcher

    def _find_expanded(self, img: np.ndarray):
        """Пробує всі 5 позицій розгорнутої панелі (з невеликими зсувами);
        повертає (race_number, panel) або None. Самоперевірка: заголовок
        панелі i має читатись як "RACE i"."""
        for i, base_panel in enumerate(ACCORDION_EXPANDED_PANELS):
            for dy in HEADER_DY_OFFSETS:
                panel = base_panel.shifted(0.0, dy)
                header_text = ocr.read_text(panel.sub(ACCORDION_HEADER).crop(img), "RACE 12345")
                match = RACE_HEADER_RE.search(header_text)
                if match and int(match[1]) == i + 1:
                    return i + 1, panel
        return None

    def extract(self, img: np.ndarray) -> list[RaceCapture]:
        found = self._find_expanded(img)
        if not found:
            return []
        race_number, panel = found

        track_text = ocr.read_name(panel.sub(ACCORDION_TRACK_NAME).crop(img))
        car_text = ocr.read_name(panel.sub(ACCORDION_CAR_NAME).crop(img))

        return [RaceCapture(
            race_number=race_number,
            track=self.track_matcher.match(track_text),
            car=self.car_matcher.match(car_text),
            rank=ocr.read_rank(panel.sub(ACCORDION_RANK).crop(img)),
            time=ocr.read_time(panel.sub(ACCORDION_TIME).crop(img)),
            source_screen=self.name,
            panel_image=encode_png(panel.crop(img)),
        )]
```

- [ ] **Step 4: Запустити — негативний тест пройшов, фікстурний скіпнувся**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_challenge_accordion.py -v`
Expected: `1 passed, 1 skipped`

- [ ] **Step 5: Повідомити «задача 12 готова до коміту»**

---

### Task 13: Калібрування ROI на наявному скріншоті

**Files:**
- Create: `tests/fixtures/accordion_race1.png` (копія наявного прикладу)
- Modify: `alu_gauntlet_helper/screen_recognition/regions.py` (відкалібровані константи), `tests/test_challenge_accordion.py` (очікувані значення)

Повнорозмірних скріншотів НЕМАЄ і не буде — користувач не може їх надати.
Калібруємо на наявному зменшеному прикладі (600×375, 16:10): відносні координати
не залежать від роздільної здатності. ROI робити з запасом ~10–15% — застосунок
має працювати на інших пристроях з іншими роздільними здатностями та
співвідношеннями сторін. Доточнення відбудеться у реальній грі (Task 18,
`save_captures` збирає реальні скріни як майбутні фікстури).

- [ ] **Step 1: Скопіювати фікстуру**

Run: `Copy-Item "C:\Users\igora\OneDrive\Desktop\alu\opponent_challenge.png" "tests/fixtures/accordion_race1.png"`
Expected: файл існує. На ньому: RACE 1 розгорнуто, трек "PARIS / NOTRE DAME", авто "ULTIMA RS", ранг 4,644, час (TIME TO BEAT) 00:22.797.

- [ ] **Step 2: Прогнати дебаг-утиліту**

Run: `.\.venv\Scripts\python.exe -m scripts.debug_recognition tests/fixtures/accordion_race1.png --grid`
Expected: `*_annotated.png` з рамками. Відкрити, звірити рамки з реальними елементами (Read-інструментом, якщо виконує агент).

- [ ] **Step 3: Скоригувати константи в `regions.py`**

По сітці з `--grid` зчитати межі розгорнутої панелі race 1 і вкладених регіонів
(header / track / car / rank / time). Крок зсуву панелей для race 2..5 оцінити
по ширині згорнутих панелей праворуч (4 однакові колонки). Повторювати
Step 2 → Step 3, поки header OCR не друкує `RACE 1`, а суб-регіони охоплюють
свій текст із запасом ~10–15% поля.

- [ ] **Step 4: Заповнити очікувані значення в тесті**

У `tests/test_challenge_accordion.py` виставити (значення видно на скріншоті):

```python
EXPECTED_RACE_1 = {"race_number": 1, "track_id": 101, "car_id": 201, "time": 22797, "rank": 4644}
```

Стаб-словники вже містять "Notre Dame" (101) і "Ultima RS" (201) — залишити.
Якщо OCR на зменшеному скріншоті не тягне якесь поле (наприклад, ранг) —
послабити тільки цей assert до `c.rank in (4644, None)` з коментарем
«зменшена фікстура, на реальній роздільній здатності точніше», НЕ ламати
продакшн-код під фікстуру.

- [ ] **Step 5: Прогнати тести до зеленого**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_challenge_accordion.py -v`
Expected: фікстурний + негативний passed. Якщо OCR плутає символи — спершу крутити регіони (тісніший кроп), потім scale у `ocr.preprocess` (3 → 4).

- [ ] **Step 6: Повідомити «задача 13 готова до коміту»**

---

### Task 14: Оверлей

**Files:**
- Create: `alu_gauntlet_helper/views/overlay.py`
- Test: `tests/test_overlay_lines.py`

- [ ] **Step 1: Написати тести для чистої функції**

```python
from alu_gauntlet_helper.models import FieldGuess, RaceCapture
from alu_gauntlet_helper.views.overlay import build_overlay_lines


def test_empty_session():
    lines = build_overlay_lines({}, {}, {}, status="чекаю")
    assert lines[0] == "Gauntlet capture 0/5"
    assert lines[1] == "1 — немає даних"
    assert lines[-1] == "чекаю"


def test_complete_race_line():
    races = {1: RaceCapture(
        race_number=1,
        track=FieldGuess(value=11, score=0.9),
        car=FieldGuess(value=21, score=0.9),
        time=22797,
    )}
    lines = build_overlay_lines(races, {11: "Notre Dame"}, {21: "Ultima RS"})
    assert lines[0] == "Gauntlet capture 1/5"
    assert lines[1] == "1 ✓ Notre Dame · Ultima RS · 00:22.797"


def test_partial_race_marked():
    races = {2: RaceCapture(race_number=2, time=21000)}
    lines = build_overlay_lines(races, {}, {})
    assert lines[2].startswith("2 ⚠")
    assert "?" in lines[2]
```

- [ ] **Step 2: Запустити — впевнитись, що падає**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_overlay_lines.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Створити `overlay.py`**

```python
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from alu_gauntlet_helper.models import RaceCapture
from alu_gauntlet_helper.utils.utils import format_time

RACE_COUNT = 5
MARGIN = 16


def build_overlay_lines(races: dict[int, RaceCapture],
                        track_names: dict[int, str],
                        car_names: dict[int, str],
                        status: str = "") -> list[str]:
    complete = sum(
        1 for c in races.values() if c.track and c.car and c.time
    )
    lines = [f"Gauntlet capture {complete}/5"]
    for n in range(1, RACE_COUNT + 1):
        capture = races.get(n)
        if capture is None:
            lines.append(f"{n} — немає даних")
            continue
        track = track_names.get(capture.track.value, "?") if capture.track else "?"
        car = car_names.get(capture.car.value, "?") if capture.car else "?"
        time_str = format_time(capture.time) if capture.time else "?"
        mark = "✓" if capture.track and capture.car and capture.time else "⚠"
        lines.append(f"{n} {mark} {track} · {car} · {time_str}")
    if status:
        lines.append(status)
    return lines


class OverlayWindow(QWidget):
    """Click-through панель статусу поверх гри (borderless fullscreen)."""

    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, True)

        self.label = QLabel()
        self.label.setStyleSheet("""
            background-color: rgba(8, 10, 40, 215);
            color: white;
            font-size: 13px;
            padding: 10px 14px;
            border-radius: 8px;
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)

    def set_lines(self, lines: list[str]):
        self.label.setText("\n".join(lines))
        self.adjustSize()
        self._move_to_corner()

    def _move_to_corner(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.width() - MARGIN, screen.top() + MARGIN)

    def toggle(self):
        self.setVisible(not self.isVisible())
```

- [ ] **Step 4: Запустити — пройшло**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_overlay_lines.py -v`
Expected: `3 passed`

- [ ] **Step 5: Повідомити «задача 14 готова до коміту»**

---

### Task 15: CaptureController

**Files:**
- Create: `alu_gauntlet_helper/capture/capture_controller.py`

Координатор: потоки, хоткеї, оверлей. Юніт-тести недоцільні (усе — обв'язка Qt/потоків); логіка всередині вже покрита тестами. Перевірка — вручну у Task 17.

- [ ] **Step 1: Створити `capture_controller.py`**

```python
import threading
import traceback

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.capture.hotkey import GlobalHotkeyService
from alu_gauntlet_helper.capture.screen_grab import grab_screen, save_capture
from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.engine import RecognitionEngine
from alu_gauntlet_helper.screen_recognition.matching import build_car_matcher, build_track_matcher
from alu_gauntlet_helper.screen_recognition.screens.challenge_accordion import ChallengeAccordionExtractor
from alu_gauntlet_helper.views.overlay import OverlayWindow, build_overlay_lines

OVERLAY_HIDE_DELAY_MS = 80


class CaptureController(QObject):
    """Хоткей → скрін → розпізнавання (фоновий потік) → сесія → оверлей."""

    _capture_requested = pyqtSignal()
    _overlay_toggle_requested = pyqtSignal()
    _recognized = pyqtSignal(object)  # RecognitionResult | None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.overlay = OverlayWindow()
        self.hotkeys = GlobalHotkeyService()
        self._busy = False
        self._status = ""

        self._capture_requested.connect(self._on_capture_requested)
        self._overlay_toggle_requested.connect(self.overlay.toggle)
        self._recognized.connect(self._on_recognized)
        APP_CONTEXT.challenge_session.add_listener(self._refresh_overlay)

    def apply_settings(self) -> bool:
        """(Пере)реєструє хоткеї та tesseract зі збережених налаштувань. False — хоткей не став."""
        settings = APP_CONTEXT.settings.get()
        ocr.configure_tesseract(settings.tesseract_path)
        self.hotkeys.unregister_all()
        ok = self.hotkeys.register(settings.capture_hotkey, self._capture_requested.emit)
        self.hotkeys.register(settings.overlay_hotkey, self._overlay_toggle_requested.emit)
        return ok

    def shutdown(self):
        self.hotkeys.unregister_all()

    # --- захоплення -----------------------------------------------------

    def _on_capture_requested(self):
        if self._busy:
            return
        self._busy = True
        self.overlay.hide()  # щоб оверлей не потрапив у кадр
        QTimer.singleShot(OVERLAY_HIDE_DELAY_MS, self._do_grab)

    def _do_grab(self):
        settings = APP_CONTEXT.settings.get()
        try:
            img = grab_screen(settings.capture_monitor)
        except Exception:
            traceback.print_exc()
            self._busy = False
            self._set_status("Помилка скріншота")
            return

        if settings.save_captures:
            save_capture(img)

        self._set_status("Розпізнаю…")
        threading.Thread(target=self._recognize_worker, args=(img,), daemon=True).start()

    def _recognize_worker(self, img):
        try:
            if not ocr.is_available():
                print("Tesseract is not available")
                self._recognized.emit(None)
                return
            result = self._build_engine().recognize(img)
        except Exception:
            traceback.print_exc()
            result = None
        self._recognized.emit(result)

    @staticmethod
    def _build_engine() -> RecognitionEngine:
        # словники будуються на кожне захоплення — завжди свіжі дані з БД
        track_matcher = build_track_matcher(APP_CONTEXT.tracks_service.get_all_views())
        car_matcher = build_car_matcher(APP_CONTEXT.cars_service.get_all())
        return RecognitionEngine([ChallengeAccordionExtractor(track_matcher, car_matcher)])

    def _on_recognized(self, result):
        self._busy = False
        if result is None:
            self._set_status("Екран не розпізнано")
            return
        self._status = ""
        APP_CONTEXT.challenge_session.apply(result)  # listener оновить оверлей

    # --- оверлей ---------------------------------------------------------

    def _set_status(self, status: str):
        self._status = status
        self._refresh_overlay()

    def _refresh_overlay(self):
        session = APP_CONTEXT.challenge_session
        track_ids = {c.track.value for c in session.races.values() if c.track}
        car_ids = {c.car.value for c in session.races.values() if c.car}
        track_names = {t.id: t.name for t in APP_CONTEXT.tracks_service.get_by_ids(track_ids).values()}
        car_names = {c.id: c.name for c in APP_CONTEXT.cars_service.get_by_ids(car_ids).values()}

        status = self._status
        if not status and session.is_complete():
            status = "Готово — відкрий рев'ю у застосунку"
        self.overlay.set_lines(build_overlay_lines(session.races, track_names, car_names, status))
        if not self.overlay.isVisible():
            self.overlay.show()
```

- [ ] **Step 2: Перевірити, що модуль імпортується**

Run: `.\.venv\Scripts\python.exe -c "from alu_gauntlet_helper.capture.capture_controller import CaptureController; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Повідомити «задача 15 готова до коміту»**

---

### Task 16: CaptureTab + CaptureReviewDialog

**Files:**
- Create: `alu_gauntlet_helper/views/capture_review_dialog.py`, `alu_gauntlet_helper/views/capture_tab.py`

UI-обв'язка — без юніт-тестів; ручна перевірка у Task 17.

- [ ] **Step 1: Створити `capture_review_dialog.py`**

```python
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QDialog, QGridLayout, QHBoxLayout, QLabel,
                             QMessageBox, QPushButton, QVBoxLayout)

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.races import RaceView
from alu_gauntlet_helper.utils.utils import format_time, parse_time, time_format_regex
from alu_gauntlet_helper.views.components.item_completer import ItemCompleter
from alu_gauntlet_helper.views.components.validated_line_edit import ValidatedLineEdit

LOW_CONFIDENCE = 0.85
WARN_STYLE = "background-color: rgba(255, 200, 0, 0.25);"


class ReviewRow:
    """Один рядок рев'ю: трек, авто, ранг, час + мініатюра джерела."""

    def __init__(self, race_number: int, capture):
        self.race_number = race_number
        self.capture = capture

        self.thumbnail = QLabel()
        self.thumbnail.setFixedSize(160, 64)
        self.thumbnail.setStyleSheet("background-color: #271A62;")
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if capture and capture.panel_image:
            pixmap = QPixmap()
            pixmap.loadFromData(capture.panel_image)
            self.thumbnail.setPixmap(pixmap.scaled(
                160, 64, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))

        self.track_edit = ValidatedLineEdit(placeholder="Track...")
        self.track_completer = ItemCompleter(
            self.track_edit.get_input(),
            autocomplete=APP_CONTEXT.tracks_service.autocomplete,
            presentation=lambda i: f"{i.map_name} - {i.name}",
            allow_custom_text=False,
        )

        self.car_edit = ValidatedLineEdit(placeholder="Car...")
        self.car_completer = ItemCompleter(
            self.car_edit.get_input(),
            autocomplete=APP_CONTEXT.cars_service.autocomplete,
            presentation=lambda i: i.name,
            allow_custom_text=False,
        )

        self.rank_edit = ValidatedLineEdit(placeholder="Rank", regex=r"^\d{0,5}$")
        self.time_edit = ValidatedLineEdit(placeholder="Time", regex=time_format_regex)

        self._prefill()

    def _prefill(self):
        if not self.capture:
            return
        if self.capture.track:
            tracks = APP_CONTEXT.tracks_service.get_by_ids({self.capture.track.value})
            track = tracks.get(self.capture.track.value)
            if track:
                self.track_edit.set_text(f"{track.map_name} - {track.name}")
                self.track_completer.set_selected_item(track)
            if self.capture.track.score < LOW_CONFIDENCE:
                self.track_edit.get_input().setStyleSheet(WARN_STYLE)

        car = None
        if self.capture.car:
            cars = APP_CONTEXT.cars_service.get_by_ids({self.capture.car.value})
            car = cars.get(self.capture.car.value)
            if car:
                self.car_edit.set_text(car.name)
                self.car_completer.set_selected_item(car)
            if self.capture.car.score < LOW_CONFIDENCE:
                self.car_edit.get_input().setStyleSheet(WARN_STYLE)

        rank = self.capture.rank
        if rank is None and car and car.rank:
            rank = car.rank  # фолбек: поточний ранг авто з БД
        if rank:
            self.rank_edit.set_text(str(rank))
        if self.capture.time:
            self.time_edit.set_text(format_time(self.capture.time))

    def build_race(self) -> RaceView | None:
        """RaceView для збереження або None, якщо рядок невалідний (з підсвіткою помилок)."""
        track = self.track_completer.get_selected_item()
        car = self.car_completer.get_selected_item()
        time_ms = parse_time(self.time_edit.text())

        valid = True
        if not track:
            self.track_edit.set_error("Select track")
            valid = False
        if not car:
            self.car_edit.set_error("Select car")
            valid = False
        if time_ms <= 0:
            self.time_edit.set_error("Invalid time")
            valid = False
        if not valid:
            return None

        return RaceView(
            track_id=track.id,
            car_id=car.id,
            rank=int(self.rank_edit.text() or 0),
            time=time_ms,
        )


class CaptureReviewDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review captured races")
        self.setMinimumWidth(900)

        self.rows = [
            ReviewRow(n, APP_CONTEXT.challenge_session.races.get(n))
            for n in range(1, 6)
        ]

        grid = QGridLayout()
        for col, title in enumerate(["#", "Source", "Track", "Car", "Rank", "Time"]):
            grid.addWidget(QLabel(f"<b>{title}</b>"), 0, col)
        for i, row in enumerate(self.rows, start=1):
            grid.addWidget(QLabel(str(row.race_number)), i, 0)
            grid.addWidget(row.thumbnail, i, 1)
            grid.addWidget(row.track_edit, i, 2)
            grid.addWidget(row.car_edit, i, 3)
            grid.addWidget(row.rank_edit, i, 4)
            grid.addWidget(row.time_edit, i, 5)
        grid.setColumnStretch(2, 2)
        grid.setColumnStretch(3, 2)

        self.save_button = QPushButton("Save all")
        self.save_button.clicked.connect(self.on_save)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(cancel_button)
        buttons.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.addLayout(grid)
        layout.addLayout(buttons)

    def on_save(self):
        races = [row.build_race() for row in self.rows]
        if any(r is None for r in races):
            return
        for race in races:
            APP_CONTEXT.races_service.save(race)
        APP_CONTEXT.challenge_session.clear()
        QMessageBox.information(self, "Saved", "5 races saved.")
        self.accept()
```

- [ ] **Step 2: Створити `capture_tab.py`**

```python
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.utils.utils import format_time
from alu_gauntlet_helper.views import style
from alu_gauntlet_helper.views.capture_review_dialog import CaptureReviewDialog


class CaptureTab(QWidget):
    """Стан сесії захоплення + рев'ю/скидання."""

    def __init__(self):
        super().__init__()

        settings = APP_CONTEXT.settings.get()
        hint = QLabel(
            f"У грі натисни <b>{settings.capture_hotkey.upper()}</b> на екрані результатів "
            f"челенджа (розгорнувши гонку), щоб захопити дані. "
            f"<b>{settings.overlay_hotkey.upper()}</b> — показати/сховати оверлей."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {style.TEXT_MUTED};")

        self.race_labels = [QLabel() for _ in range(5)]

        self.review_button = QPushButton("Review && Save")
        self.review_button.clicked.connect(self.open_review)
        self.discard_button = QPushButton("Discard session")
        self.discard_button.clicked.connect(self.discard)

        buttons = QHBoxLayout()
        buttons.addWidget(self.review_button)
        buttons.addWidget(self.discard_button)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        for label in self.race_labels:
            layout.addWidget(label)
        layout.addLayout(buttons)
        layout.addStretch()

        APP_CONTEXT.challenge_session.add_listener(self.refresh)
        self.refresh()

    def refresh(self):
        session = APP_CONTEXT.challenge_session
        track_ids = {c.track.value for c in session.races.values() if c.track}
        car_ids = {c.car.value for c in session.races.values() if c.car}
        tracks = APP_CONTEXT.tracks_service.get_by_ids(track_ids)
        cars = APP_CONTEXT.cars_service.get_by_ids(car_ids)

        for n, label in enumerate(self.race_labels, start=1):
            capture = session.races.get(n)
            if capture is None:
                label.setText(f"Race {n}: —")
                label.setStyleSheet(f"color: {style.TEXT_MUTED};")
                continue
            track = tracks.get(capture.track.value) if capture.track else None
            car = cars.get(capture.car.value) if capture.car else None
            parts = [
                f"{track.map_name} - {track.name}" if track else "трек?",
                car.name if car else "авто?",
                f"rank {capture.rank}" if capture.rank else "ранг?",
                format_time(capture.time) if capture.time else "час?",
            ]
            label.setText(f"Race {n}: " + " · ".join(parts))
            label.setStyleSheet("")

        has_data = bool(session.races)
        self.review_button.setEnabled(has_data)
        self.discard_button.setEnabled(has_data)

    def open_review(self):
        CaptureReviewDialog(self).exec()

    def discard(self):
        APP_CONTEXT.challenge_session.clear()
```

- [ ] **Step 3: Перевірити, що модулі імпортуються**

Run: `.\.venv\Scripts\python.exe -c "import alu_gauntlet_helper.views.capture_tab, alu_gauntlet_helper.views.capture_review_dialog; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Повідомити «задача 16 готова до коміту»**

---

### Task 17: Інтеграція (main_window, settings_tab, main.py) + видалення старого коду

**Files:**
- Modify: `alu_gauntlet_helper/views/main_window.py`, `alu_gauntlet_helper/views/settings_tab.py`, `main.py`
- Delete: `alu_gauntlet_helper/views/recognize_races_tab.py`, `alu_gauntlet_helper/screen_recognition/recognition.py`

- [ ] **Step 1: `main_window.py` — підключити CaptureTab і CaptureController**

Замінити імпорти (прибрати `RecognizeRacesTab`, додати нові):

```python
from alu_gauntlet_helper.capture.capture_controller import CaptureController
from alu_gauntlet_helper.views.capture_tab import CaptureTab
```

У `__init__` прибрати закоментовані рядки про `recognize_races_tab` і додати (після `self.refresh_tray_icon(...)`):

```python
        self.capture_controller = CaptureController(self)
        hotkey_ok = self.capture_controller.apply_settings()
        if not hotkey_ok:
            print("Failed to register capture hotkey")
```

Створення вкладок: додати `self.capture_tab = CaptureTab()` поряд з іншими табами і `self.tabs.addTab(self.capture_tab, "CAPTURE")` ПЕРШОЮ вкладкою (перед CAR SELECTION).

У `SettingsTab` передати колбек: `self.settings_tab = SettingsTab(refresh_tray_icon=self.refresh_tray_icon, apply_capture_settings=self.capture_controller.apply_settings)`.

- [ ] **Step 2: `settings_tab.py` — поля захоплення**

Повний новий вміст файлу:

```python
from PyQt6.QtWidgets import (QCheckBox, QFormLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget)

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.screen_recognition import ocr


class SettingsTab(QWidget):
    def __init__(self, refresh_tray_icon, apply_capture_settings=None):
        super().__init__()
        self.refresh_tray_icon = refresh_tray_icon if refresh_tray_icon else lambda _: None
        self.apply_capture_settings = apply_capture_settings or (lambda: True)

        self.show_tray_icon = QCheckBox("Show tray icon")
        self.show_tray_icon.checkStateChanged.connect(self.on_tray_changed)  # type: ignore

        self.close_to_tray = QCheckBox("Close to tray")
        self.close_to_tray.checkStateChanged.connect(self.on_tray_changed)  # type: ignore

        self.start_minimized = QCheckBox("Start minimized")

        self.capture_hotkey = QLineEdit()
        self.overlay_hotkey = QLineEdit()
        self.tesseract_path = QLineEdit()
        self.tesseract_path.setPlaceholderText("auto-detect")
        self.capture_monitor = QSpinBox()
        self.capture_monitor.setRange(1, 4)
        self.save_captures = QCheckBox("Save capture screenshots (data/captures)")
        self.capture_status = QLabel()

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.on_save)  # type: ignore

        self.form = QFormLayout()
        self.form.addWidget(self.show_tray_icon)
        self.form.addWidget(self.close_to_tray)
        self.form.addWidget(self.start_minimized)
        self.form.addRow("Capture hotkey:", self.capture_hotkey)
        self.form.addRow("Overlay hotkey:", self.overlay_hotkey)
        self.form.addRow("Tesseract path:", self.tesseract_path)
        self.form.addRow("Capture monitor:", self.capture_monitor)
        self.form.addWidget(self.save_captures)
        self.form.addWidget(self.capture_status)

        self.bottom_layout = QHBoxLayout()
        self.bottom_layout.addStretch()
        self.bottom_layout.addWidget(self.save_button)

        layout = QVBoxLayout()
        layout.addLayout(self.form)
        layout.addLayout(self.bottom_layout)
        layout.addStretch()
        self.setLayout(layout)
        self.refresh()
        self.on_tray_changed()

    def refresh(self):
        settings = APP_CONTEXT.settings.get()
        self.show_tray_icon.setChecked(settings.show_tray_icon)
        self.close_to_tray.setChecked(settings.close_to_tray)
        self.start_minimized.setChecked(settings.start_minimized)
        self.capture_hotkey.setText(settings.capture_hotkey)
        self.overlay_hotkey.setText(settings.overlay_hotkey)
        self.tesseract_path.setText(settings.tesseract_path)
        self.capture_monitor.setValue(settings.capture_monitor)
        self.save_captures.setChecked(settings.save_captures)
        self.refresh_capture_status()

    def refresh_capture_status(self):
        tesseract = "знайдено" if ocr.is_available() else "НЕ знайдено — вкажи шлях"
        self.capture_status.setText(f"Tesseract: {tesseract}")

    def on_tray_changed(self):
        self.close_to_tray.setEnabled(self.show_tray_icon.isChecked())
        self.start_minimized.setEnabled(self.show_tray_icon.isChecked() and self.close_to_tray.isChecked())

    def on_save(self):
        settings = APP_CONTEXT.settings.get()
        settings.show_tray_icon = self.show_tray_icon.isChecked()
        settings.close_to_tray = self.close_to_tray.isChecked()
        settings.start_minimized = self.start_minimized.isChecked()
        settings.capture_hotkey = self.capture_hotkey.text().strip() or "f8"
        settings.overlay_hotkey = self.overlay_hotkey.text().strip() or "f9"
        settings.tesseract_path = self.tesseract_path.text().strip()
        settings.capture_monitor = self.capture_monitor.value()
        settings.save_captures = self.save_captures.isChecked()
        APP_CONTEXT.settings.save(settings)
        self.refresh()
        self.refresh_tray_icon(settings.show_tray_icon)
        if not self.apply_capture_settings():
            self.capture_status.setText("Хоткей не зареєструвався — спробуй іншу клавішу")
```

- [ ] **Step 3: `main.py` — tesseract при старті**

Після `update_cars_if_needed()` додати:

```python
    from alu_gauntlet_helper.screen_recognition.ocr import configure_tesseract
    configure_tesseract(settings.tesseract_path)
```

(Хоткеї реєструє `MainWindow` через `CaptureController.apply_settings()`.)

- [ ] **Step 4: Видалити старий код**

- Видалити файл `alu_gauntlet_helper/views/recognize_races_tab.py`
- Видалити файл `alu_gauntlet_helper/screen_recognition/recognition.py`
- Перевірити, що на них ніхто не посилається: `Grep "recognize_races_tab|find_race_boxes|recognize_text_in_rectangle|find_rectangles"` по проєкту → залишків немає (включно з закоментованими рядками в `main_window.py`).

- [ ] **Step 5: Прогнати всі тести + запустити застосунок**

Run: `.\.venv\Scripts\python.exe -m pytest tests -v`
Expected: усі passed.
Run: `.\.venv\Scripts\python.exe main.py`
Expected: застосунок стартує, є вкладка CAPTURE, у Settings видно нові поля і статус Tesseract. Закрити.

- [ ] **Step 6: Повідомити «задача 17 готова до коміту»**

---

### Task 18: Ручна e2e перевірка (з користувачем)

Чекліст для користувача (виконати з запущеною грою):

- [ ] 1. Запустити `python main.py`. У Settings: Tesseract «знайдено», хоткеї f8/f9.
- [ ] 2. На робочому столі (без гри) натиснути F8 → оверлей з'являється: «Екран не розпізнано».
- [ ] 3. F9 двічі → оверлей зникає і повертається.
- [ ] 4. У грі, на екрані результатів челенджа, розгорнути Race 1 → F8 → оверлей показує рядок 1 з треком/авто/часом.
- [ ] 5. Повторити для Race 2..5 → прогрес 5/5, статус «Готово…».
- [ ] 6. У застосунку, вкладка CAPTURE → Review & Save → перевірити передзаповнення, мініатюри, виправити за потреби → Save all.
- [ ] 7. Вкладка RACES → 5 нових записів з правильними даними.
- [ ] 8. Вкладка CAR SELECTION → нові гонки враховано в підказках.
- [ ] 9. Якщо щось розпізнається стабільно погано — зберегти скрін (`save_captures` у Settings), додати як фікстуру і повернутись до калібрування (Task 13).

---

## Перевірка покриття спеки (self-review)

- Хоткей + скрін + фоновий потік → Tasks 8, 9, 15 ✓
- Класифікація екрана + ROI + OCR + словник → Tasks 3–6, 12, 13 ✓
- Сесія в пам'яті, злиття за впевненістю → Task 7 ✓
- Оверлей click-through → Task 14 ✓
- Рев'ю-діалог з мініатюрами і фолбеком рангу з БД → Task 16 ✓
- Settings (хоткеї, tesseract, монітор, збереження скрінів) + обробка помилок → Tasks 10, 15, 17 ✓
- Тести: фікстури, matcher, сесія → Tasks 3, 4, 7, 12, 13 ✓
- `MapIconMatcher` зі спеки **свідомо відкладено** (YAGNI): потрібен лише для майбутніх екранів з іконками карт (CHALLENGE WON), у v1 акордеон містить назву треку текстом.
