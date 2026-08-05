# Асистент проти суперника — Етап 3 (частина «логіка»): звуження треку, песимістична оцінка, чипи

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Уміти працювати з гонками, де трек не визначено точно: поле карти в моделях, ручний/виведений вибір треку (`track_fix`), звуження треку за часом суперника (спека §6), песимістична оцінка min-p̂ по треках-кандидатах в автопідборі та шансі перемоги (спека §5), чипи треків у UI (спека §4).

**Scope note (що НЕ в цьому плані):** Екстрактори екранів 2/3 і матчинг іконок карт (спека §3) вимагають скріншотів цих екранів, яких у репо немає — вони підуть ОКРЕМИМ планом, коли користувач надасть скріншоти. Цей план самодостатній: чипи треків працюють уже сьогодні для неоднозначних сканів акордеона (TrackResolver повертає близьких кандидатів зі заниженим score), а вся логіка карт/звуження вкривається юніт-тестами й буде підхоплена екстрактором екрана 3 без змін.

**Architecture:** `RaceCapture.map` — нове незалежне поле-здогад карти (джерело: майбутній екстрактор екрана 3). `ChallengeSessionService.track_fix` — драфт-рівневий вибір треку при неоднозначності: слабший за ручний драфт і за впевнений скан, сильніший за невпевнений скан. `AssistantService` отримує `tracks` і три нові методи: `chip_tracks` (кандидати для чипів/оцінки), `narrow_track` (звуження за діапазоном моїх часів ±10%), `resolve_tracks` (проставляє виведені фікси; викликається на початку `auto_pick`). Песимістична оцінка — min p̂ по треках-кандидатах — вбудовується в `auto_pick`/`win_chance`. UI: ряд чипів над списком пропозицій + map-only відображення на картці гонки.

**Tech Stack:** Python 3.10+ анотації (`X | None`), Pydantic, PyQt6, pytest. Чиста логіка тестується без Qt і без БД (фейки в стилі `tests/test_assistant.py`).

## Global Constraints

- **Жодних міграцій БД і нових таблиць/колонок** — усі нові дані живуть лише в памʼяті процесу (спека, розділ «Мета»). Новий SQL — тільки читання наявної таблиці `races`.
- **Git-коміти НЕ робити** — користувач комітить сам (його явне правило). Завдання закінчуються зеленими тестами, без кроку commit.
- Нові UI-рядки — в ОБИДВІ мови `ui_lang.TRANSLATIONS` («en» і «uk»).
- Коментарі в коді — українською, в стилі наявних файлів.
- Тести запускати як `.venv/Scripts/python -m pytest tests/<file> -v` з кореня репо (у Git Bash `python` з PATH відсутній). OCR-тести без Tesseract скіпаються — це нормально.
- Спека: `docs/superpowers/specs/2026-08-02-opponent-assistant-design.md`, розділи 1, 4, 5, 6.

## Довідка по наявному коду (для виконавця без контексту)

- `alu_gauntlet_helper/models.py` — `FieldGuess(value, score, candidates: list[tuple[int, float]])`, `RaceCapture` (поля `track`, `car`, `rank`, `time`, `opponent_time`, `opponent_car`).
- `alu_gauntlet_helper/services/challenge_session.py` — `ChallengeSessionService` (стан у памʼяті: `races` OCR-шар, `drafts` ручний шар, `suggested`/`pinned_races` рекомендації), `EffectiveRace` (злиті дані), `merge_guess`, константи `RACE_COUNT = 5`, `LOW_CONFIDENCE = 0.85`.
- `alu_gauntlet_helper/services/assistant.py` — `AssistantService(races, cars)` з `suggestions_vs`, `aggregates_vs`, `auto_pick`, `win_chance`, `beat_stats`; `laplace(wins, n)`.
- `alu_gauntlet_helper/services/opponent_picker.py` — `Candidate(car_id, p, margin)`, `pick_cars`, `prob_at_least`.
- `alu_gauntlet_helper/services/tracks.py` — `TracksService.autocomplete(query, map_id=None) -> list[TrackView]` (порожній query + map_id → усі треки карти).
- `alu_gauntlet_helper/app_context.py` — синглтон `APP_CONTEXT` зі сервісами.
- `alu_gauntlet_helper/views/assistant_tab.py` — `SessionView` (картки 5 гонок + список пропозицій + низ), `AssistantTab`.
- `alu_gauntlet_helper/views/components/race_card.py` — `RaceCard.update_card(e, track, car, beat, checked, selected, suggested)`.

---

### Task 1: Поле карти в моделях (`RaceCapture.map`, `EffectiveRace.map_id`/`track_candidates`)

**Files:**
- Modify: `alu_gauntlet_helper/models.py` (клас `RaceCapture`)
- Modify: `alu_gauntlet_helper/services/challenge_session.py` (`EffectiveRace`, `_merge`, `effective`)
- Test: `tests/test_challenge_session.py`

**Interfaces:**
- Consumes: наявні `FieldGuess`, `merge_guess`.
- Produces (на це спираються Task 2, 4, 5, 6): `RaceCapture.map: FieldGuess | None`; `EffectiveRace.map_id: int` (0 = невідома; ненульова ЛИШЕ коли трек не визначено сканом/драфтом), `EffectiveRace.track_candidates: list[tuple[int, float]]` (сирі кандидати OCR-треку, заповнені лише при невпевненому треку).

- [x] **Step 1: Написати тести, що падають**

Додати в кінець `tests/test_challenge_session.py`:

```python
# --- поле карти (map) і кандидати треку — етап 3 ---------------------------


def map_capture(n, map_id, map_score=0.9, opp_time=None, track_score=None):
    c = capture(n, track_score=track_score)
    c.map = FieldGuess(value=map_id, score=map_score)
    c.opponent_time = opp_time
    return c


def test_map_field_default_none():
    assert capture(1).map is None


def test_map_only_capture_visible():
    # скан екрана 3 дав лише карту — картка гонки має зʼявитись
    s = ChallengeSessionService()
    s.apply(result(map_capture(3, map_id=5)))
    e = s.effective(3)
    assert e is not None
    assert e.map_id == 5 and e.track_id == 0


def test_map_hidden_when_track_confident():
    # трек визначено впевнено — карта зайва (трек сам її дає)
    s = ChallengeSessionService()
    s.apply(result(map_capture(1, map_id=5, track_score=0.9)))
    e = s.effective(1)
    assert e.track_id == 11 and e.map_id == 0


def test_map_merge_by_score():
    s = ChallengeSessionService()
    s.apply(result(map_capture(2, map_id=5, map_score=0.9)))
    s.apply(result(map_capture(2, map_id=7, map_score=0.5)))
    assert s.races[2].map.value == 5  # упевненіша лишилась


def test_track_candidates_exposed_when_uncertain():
    s = ChallengeSessionService()
    c = capture(4)
    c.track = FieldGuess(value=41, score=0.6, candidates=[(41, 0.93), (42, 0.91)])
    s.apply(result(c))
    e = s.effective(4)
    assert e.track_id == 41 and e.track_uncertain
    assert e.track_candidates == [(41, 0.93), (42, 0.91)]


def test_track_candidates_empty_when_confident():
    s = ChallengeSessionService()
    c = capture(4)
    c.track = FieldGuess(value=41, score=0.95, candidates=[(41, 0.95), (42, 0.7)])
    s.apply(result(c))
    assert s.effective(4).track_candidates == []
```

- [x] **Step 2: Переконатися, що тести падають**

Run: `.venv/Scripts/python -m pytest tests/test_challenge_session.py -v -k "map or candidates"`
Expected: FAIL (`map` — unknown attribute / ValidationError).

- [x] **Step 3: Реалізація**

У `models.py` в `RaceCapture` після поля `opponent_car`:

```python
    # Здогад карти з матчингу її іконки (екран 3 скаутингу) — коли трек невідомий
    map: FieldGuess | None = None
```

У `challenge_session.py`:

1. В `EffectiveRace` після `opponent_car_id`:

```python
    # карта гонки, коли трек не визначено сканом/драфтом (джерело: екран 3);
    # разом із track_candidates живить чипи треків і песимістичну оцінку
    map_id: int = 0
    # сирі кандидати OCR-треку (id, score) — заповнені лише при невпевненому треку
    track_candidates: list[tuple[int, float]] = []
```

2. В `EffectiveRace.is_empty` розширити умову (map-only картка — не порожня):

```python
        return not (self.track_id > 0 or self.has_car or self.rank > 0
                    or self.time > 0 or self.note or self.bad_timing
                    or self.opponent_time > 0 or self.opponent_car_id > 0
                    or self.map_id > 0)
```

3. У `ChallengeSessionService._merge` після рядка з `current.opponent_car`:

```python
            current.map = merge_guess(current.map, new.map)
```

4. У `effective()` в гілці `if capture:` замінити блок треку

```python
            if e.track_id <= 0 and capture.track:
                e.track_id = capture.track.value
                e.track_uncertain = capture.track.score < LOW_CONFIDENCE
```

на:

```python
            if e.track_id <= 0 and capture.track:
                e.track_id = capture.track.value
                e.track_uncertain = capture.track.score < LOW_CONFIDENCE
                if e.track_uncertain:
                    e.track_candidates = capture.track.candidates
            if e.track_id <= 0 and capture.map:
                # карту показуємо лише поки трек не визначено (спека §1)
                e.map_id = capture.map.value
```

(Task 2 переробить цей блок ще раз під `track_fix` — тут мінімальна версія.)

- [x] **Step 4: Тести зелені**

Run: `.venv/Scripts/python -m pytest tests/test_challenge_session.py tests/test_capture_models.py -v`
Expected: PASS (усі, включно зі старими).

---

### Task 2: `track_fix` — ручний/виведений вибір треку в сесії

**Files:**
- Modify: `alu_gauntlet_helper/services/challenge_session.py`
- Test: `tests/test_challenge_session.py`

**Interfaces:**
- Consumes: Task 1 (`map_id`, `track_candidates`).
- Produces (на це спираються Task 4, 6):
  - `ChallengeSessionService.track_fix: dict[int, int]` (race_number → track_id), `inferred_tracks: set[int]` (які фікси виведені звуженням, а не ручні);
  - `set_track_fix(race_number: int, track_id: int | None, inferred: bool = False) -> None`;
  - `EffectiveRace.track_inferred: bool` — трек узято з виведеного фікса (бейдж «ймовірно» в UI);
  - пріоритет треку в `effective()`: драфт > упевнений скан (score ≥ LOW_CONFIDENCE) > track_fix > невпевнений скан; `map_id` видимий і тоді, коли трек узято з фікса (щоб чипи карти не зникали після вибору).

- [x] **Step 1: Написати тести, що падають**

Додати в кінець `tests/test_challenge_session.py`:

```python
# --- track_fix: ручний/виведений вибір треку при неоднозначності -----------


def uncertain_track_capture(n, best=41, second=42):
    c = capture(n)
    c.track = FieldGuess(value=best, score=0.6, candidates=[(best, 0.93), (second, 0.91)])
    return c


def test_track_fix_overrides_uncertain_scan():
    s = ChallengeSessionService()
    s.apply(result(uncertain_track_capture(1)))
    s.set_track_fix(1, 42)
    e = s.effective(1)
    assert e.track_id == 42
    assert not e.track_uncertain and not e.track_inferred
    assert e.track_candidates == [(41, 0.93), (42, 0.91)]  # чипи лишаються видимі


def test_confident_scan_overrides_track_fix():
    # «пізніший упевнений скан може скоригувати» (спека §1)
    s = ChallengeSessionService()
    s.apply(result(uncertain_track_capture(1)))
    s.set_track_fix(1, 42)
    sure = capture(1)
    sure.track = FieldGuess(value=43, score=0.95)
    s.apply(result(sure))
    assert s.effective(1).track_id == 43


def test_track_fix_applies_without_scan_track():
    # map-only гонка (екран 3): треку з OCR немає взагалі
    s = ChallengeSessionService()
    s.apply(result(map_capture(2, map_id=5)))
    s.set_track_fix(2, 21, inferred=True)
    e = s.effective(2)
    assert e.track_id == 21 and e.track_inferred
    assert e.map_id == 5  # карта видима — чипи не зникають після вибору


def test_draft_track_beats_fix():
    s = ChallengeSessionService()
    s.apply(result(map_capture(2, map_id=5)))
    s.set_track_fix(2, 21)
    s.set_draft(2, RaceView(track_id=99))
    assert s.effective(2).track_id == 99


def test_set_track_fix_none_clears():
    s = ChallengeSessionService()
    s.apply(result(map_capture(2, map_id=5)))
    s.set_track_fix(2, 21, inferred=True)
    s.set_track_fix(2, None)
    e = s.effective(2)
    assert e.track_id == 0 and not e.track_inferred
    assert s.track_fix == {} and s.inferred_tracks == set()


def test_track_fix_notifies_and_clears():
    s = ChallengeSessionService()
    events = []
    s.add_listener(lambda: events.append(1))
    s.set_track_fix(3, 31)
    assert len(events) == 1
    s.clear()
    assert s.track_fix == {} and s.inferred_tracks == set()
```

- [x] **Step 2: Переконатися, що тести падають**

Run: `.venv/Scripts/python -m pytest tests/test_challenge_session.py -v -k track_fix`
Expected: FAIL (`set_track_fix` не існує).

- [x] **Step 3: Реалізація**

У `ChallengeSessionService.__init__` після `self.pinned_races`:

```python
        # вибір треку при неоднозначності (чип користувача або звуження за
        # часом): {race_number: track_id}; слабший за драфт і впевнений скан
        self.track_fix: dict[int, int] = {}
        self.inferred_tracks: set[int] = set()  # які фікси виведені (бейдж «ймовірно»)
```

В `EffectiveRace` після `track_candidates`:

```python
    track_inferred: bool = False  # трек узято з виведеного (не ручного) фікса
```

Метод після `clear_pins`:

```python
    def set_track_fix(self, race_number: int, track_id: int | None, inferred: bool = False):
        """Вибір треку при неоднозначності (клік по чипу або звуження за часом
        суперника). Драфт-рівень: ручний драфт і пізніший УПЕВНЕНИЙ скан мають
        пріоритет в effective(); None — зняти вибір."""
        if track_id is None:
            self.track_fix.pop(race_number, None)
            self.inferred_tracks.discard(race_number)
        else:
            self.track_fix[race_number] = track_id
            if inferred:
                self.inferred_tracks.add(race_number)
            else:
                self.inferred_tracks.discard(race_number)
        self._notify()
```

У `clear()` додати `self.track_fix = {}` та `self.inferred_tracks = set()`.

У `effective()` замінити блок треку/карти з Task 1 на версію з фіксом
(локальна змінна `track_from_fix` відстежує джерело треку):

```python
            fix = self.track_fix.get(race_number, 0)
            track_from_fix = False
            if e.track_id <= 0 and capture.track:
                confident = capture.track.score >= LOW_CONFIDENCE
                if not confident:
                    e.track_candidates = capture.track.candidates
                if fix and not confident:
                    # вибір користувача/звуження сильніший за невпевнений скан,
                    # але впевнений пізніший скан коригує і його (спека §1)
                    e.track_id = fix
                    track_from_fix = True
                else:
                    e.track_id = capture.track.value
                    e.track_uncertain = not confident
            elif e.track_id <= 0 and fix:
                e.track_id = fix
                track_from_fix = True
            if track_from_fix:
                e.track_inferred = race_number in self.inferred_tracks
            if capture.map and (e.track_id <= 0 or track_from_fix):
                # карту показуємо, поки трек не визначено сканом/драфтом:
                # після вибору чипом вона лишається — чипи не зникають
                e.map_id = capture.map.value
```

- [x] **Step 4: Тести зелені**

Run: `.venv/Scripts/python -m pytest tests/test_challenge_session.py -v`
Expected: PASS.

---

### Task 3: Репозиторій — діапазон моїх часів на треку

**Files:**
- Modify: `alu_gauntlet_helper/services/races.py` (`RacesRepository`, `RacesService`)

**Interfaces:**
- Consumes: таблиця `races` (наявна схема: `track_id`, `time`, `bad_timing`).
- Produces (на це спирається Task 4): `RacesRepository.get_time_range_for_track(track_id: int) -> tuple[int, int] | None` — (min, max) часів усіх ЧИСТИХ (без 👎) заїздів на треку по всіх авто; None, якщо заїздів немає. `RacesService`-обгортка з тією самою сигнатурою.

- [x] **Step 1: Реалізація** (юніт-тестів на репозиторій у проєкті немає — SQL покривається фейками в Task 4 і повним прогоном; метод тримати мінімальним)

У `RacesRepository` після `get_recent_clean_times_by_car`:

```python
    def get_time_range_for_track(self, track_id: int) -> tuple[int, int] | None:
        """(min, max) моїх часів на треку по ВСІХ авто, лише чисті заїзди (без 👎).
        Для звуження треку за часом суперника (спека §6); None — заїздів немає."""
        with connect() as conn:
            row = conn.execute(
                "SELECT MIN(time) AS lo, MAX(time) AS hi FROM races "
                "WHERE track_id = :track_id AND time > 0 AND bad_timing = 0",
                {"track_id": track_id}).fetchone()
            if row is None or row["lo"] is None:
                return None
            return row["lo"], row["hi"]
```

У `RacesService` після `get_recent_clean_times_by_car`:

```python
    def get_time_range_for_track(self, track_id: int) -> tuple[int, int] | None:
        return self.repo.get_time_range_for_track(track_id)
```

- [x] **Step 2: Наявні тести не зламано**

Run: `.venv/Scripts/python -m pytest tests/test_assistant.py tests/test_challenge_session.py -v`
Expected: PASS.

---

### Task 4: AssistantService — `chip_tracks`, `narrow_track`, `resolve_tracks`

**Files:**
- Modify: `alu_gauntlet_helper/services/assistant.py`
- Modify: `alu_gauntlet_helper/app_context.py` (третій аргумент конструктора)
- Test: `tests/test_assistant.py`

**Interfaces:**
- Consumes: `EffectiveRace.map_id/track_candidates/track_inferred` (Task 1–2), `set_track_fix` (Task 2), `get_time_range_for_track` (Task 3), `TracksService.autocomplete("", map_id=...)`.
- Produces (на це спираються Task 5, 6):
  - `AssistantService(races, cars, tracks=None)` — новий необовʼязковий параметр `tracks` (`TracksService`); `app_context` передає `tracks_service`;
  - `chip_tracks(e: EffectiveRace) -> list[int]` — треки-кандидати гонки для чипів і песимістичної оцінки; `[]` — кандидатів немає (трек визначений або даних замало);
  - `narrow_track(track_ids: list[int], opponent_time: int) -> int | None` — id єдиного трека, у чий діапазон моїх часів (±10%) влучає час суперника; None — влучань 0 або ≥2;
  - `resolve_tracks(session) -> None` — для map-гонок проставляє виведені фікси (`set_track_fix(..., inferred=True)`); ручні фікси не чіпає; викликається на початку `auto_pick` (обидва режими).

- [x] **Step 1: Написати тести, що падають**

Додати в кінець `tests/test_assistant.py`:

```python
# --- Етап 3: chip_tracks / narrow_track / resolve_tracks -------------------


class FakeTracks:
    """{map_id: [track_id, ...]} — сигнатура TracksService.autocomplete."""
    def __init__(self, by_map):
        self.by_map = by_map

    def autocomplete(self, query, map_id=None):
        return [SimpleNamespace(id=t) for t in self.by_map.get(map_id, [])]


class RangeFakeRaces(TrackAwareFakeRaces):
    """+ діапазони часів треків: {track_id: (lo, hi)}."""
    def __init__(self, by_track, ranges=None):
        super().__init__(by_track)
        self.ranges = ranges or {}

    def get_time_range_for_track(self, track_id):
        return self.ranges.get(track_id)


def stage3_service(by_track=None, ranges=None, by_map=None):
    by_track = by_track or {}
    ids = {c for cars in by_track.values() for c in cars}
    return AssistantService(RangeFakeRaces(by_track, ranges),
                            FakeCars([fake_car(i) for i in ids]),
                            FakeTracks(by_map or {}))


def map_race(n, map_id, opp_time=None):
    return RaceCapture(race_number=n,
                       map=FieldGuess(value=map_id, score=0.9),
                       opponent_time=opp_time)


def test_chip_tracks_from_map():
    svc = stage3_service(by_map={5: [21, 22]})
    s = session_with(map_race(1, 5))
    assert svc.chip_tracks(s.effective(1)) == [21, 22]


def test_chip_tracks_from_ocr_candidates_window():
    svc = stage3_service()
    s = ChallengeSessionService()
    c = RaceCapture(race_number=1,
                    track=FieldGuess(value=41, score=0.6,
                                     candidates=[(41, 0.93), (42, 0.91), (43, 0.70)]))
    s.apply(RecognitionResult(screen="test", captures=[c]))
    # 43 відпадає: далі за вікно 0.05 від топового 0.93
    assert svc.chip_tracks(s.effective(1)) == [41, 42]


def test_chip_tracks_empty_when_confident():
    svc = stage3_service(by_map={5: [21, 22]})
    s = session_with(race(1, 7))  # упевнений трек — без чипів
    assert svc.chip_tracks(s.effective(1)) == []


def test_narrow_track_unique_hit():
    svc = stage3_service(ranges={21: (19000, 21000), 22: (30000, 33000)})
    assert svc.narrow_track([21, 22], 20000) == 21
    assert svc.narrow_track([21, 22], 31000) == 22


def test_narrow_track_margin_10_percent():
    svc = stage3_service(ranges={21: (20000, 21000)})
    assert svc.narrow_track([21], 18000) == 21   # 18000 == 20000*0.9 — на межі
    assert svc.narrow_track([21], 17999) is None


def test_narrow_track_ambiguous_or_missed():
    svc = stage3_service(ranges={21: (19000, 25000), 22: (20000, 26000)})
    assert svc.narrow_track([21, 22], 21000) is None  # в обидва — невизначено
    assert svc.narrow_track([21, 22], 50000) is None  # в жоден
    assert svc.narrow_track([21, 22], 21000) is None
    # без моїх заїздів (None-діапазон) трек не претендує на влучання
    svc2 = stage3_service(ranges={21: (19000, 25000)})
    assert svc2.narrow_track([21, 22], 21000) == 21


def test_resolve_tracks_sets_inferred_fix():
    svc = stage3_service(ranges={21: (19000, 21000), 22: (30000, 33000)},
                         by_map={5: [21, 22]})
    s = session_with(map_race(1, 5, opp_time=20000))
    svc.resolve_tracks(s)
    e = s.effective(1)
    assert e.track_id == 21 and e.track_inferred


def test_resolve_tracks_single_track_map():
    svc = stage3_service(by_map={5: [21]})
    s = session_with(map_race(1, 5))
    svc.resolve_tracks(s)
    assert s.effective(1).track_id == 21


def test_resolve_tracks_keeps_manual_fix():
    svc = stage3_service(ranges={21: (19000, 21000), 22: (30000, 33000)},
                         by_map={5: [21, 22]})
    s = session_with(map_race(1, 5, opp_time=20000))
    s.set_track_fix(1, 22)  # ручний вибір користувача
    svc.resolve_tracks(s)
    assert s.effective(1).track_id == 22 and not s.effective(1).track_inferred


def test_auto_pick_runs_resolve_tracks():
    svc = stage3_service(by_track={21: {501: [19000] * 10}},
                         ranges={21: (19000, 21000), 22: (30000, 33000)},
                         by_map={5: [21, 22]})
    s = session_with(map_race(1, 5, opp_time=20000))
    svc.auto_pick(s)
    e = s.effective(1)
    assert e.track_id == 21 and e.suggested_car_id == 501
```

- [x] **Step 2: Переконатися, що тести падають**

Run: `.venv/Scripts/python -m pytest tests/test_assistant.py -v -k "chip or narrow or resolve"`
Expected: FAIL (`chip_tracks` не існує / TypeError конструктора).

- [x] **Step 3: Реалізація**

У `assistant.py`:

1. Вгорі модуля константи:

```python
# вікно скорів, у якому OCR-кандидати треку вважаються нерозрізненними
# (узгоджено з TrackResolver._AMBIGUITY_WINDOW)
CHIP_SCORE_WINDOW = 0.05
CHIP_LIMIT = 3
# запас діапазону моїх часів при звуженні треку за часом суперника (спека §6)
NARROW_MARGIN = 0.10
```

2. Конструктор:

```python
    def __init__(self, races, cars, tracks=None):
        self.races = races
        self.cars = cars
        self.tracks = tracks
```

3. Нові методи (після `beat_stats`):

```python
    # --- невизначений трек: кандидати, звуження, виведені фікси (спека §4, §6) --

    def _map_tracks(self, map_id: int) -> list[int]:
        if not self.tracks or map_id <= 0:
            return []
        return [t.id for t in self.tracks.autocomplete("", map_id=map_id)]

    def chip_tracks(self, e) -> list[int]:
        """Треки-кандидати гонки для чипів і песимістичної оцінки.

        Невпевнений OCR-трек → кандидати з майже рівним скором (вікно від топу);
        трек невідомий, але карта є (екран 3) → усі треки карти. Порожній список —
        вибирати немає з чого (трек визначений або даних замало)."""
        if e.track_candidates:
            top = e.track_candidates[0][1]
            ids = [tid for tid, s in e.track_candidates
                   if top - s <= CHIP_SCORE_WINDOW][:CHIP_LIMIT]
            if e.track_id > 0 and e.track_id not in ids:
                ids.insert(0, e.track_id)  # вибраний фіксом трек — теж чип
            return ids if len(ids) > 1 else []
        if e.track_id <= 0 or e.map_id > 0:
            ids = self._map_tracks(e.map_id)
            return ids if len(ids) > 1 else []
        return []

    def narrow_track(self, track_ids: list[int], opponent_time: int) -> int | None:
        """Звуження: час суперника влучає в діапазон моїх часів (±10%) рівно
        одного кандидата → це він; 0 або ≥2 влучань → None (невизначено)."""
        hits = []
        for tid in track_ids:
            rng = self.races.get_time_range_for_track(tid)
            if rng and rng[0] * (1 - NARROW_MARGIN) <= opponent_time <= rng[1] * (1 + NARROW_MARGIN):
                hits.append(tid)
        return hits[0] if len(hits) == 1 else None

    def resolve_tracks(self, session):
        """Проставляє ВИВЕДЕНІ фікси треків для map-гонок: карта з єдиним треком
        визначає його одразу, з кількома — пробуємо звузити за часом суперника.
        Ручні фікси користувача недоторкані; виведені можна перерахувати."""
        for n in range(1, RACE_COUNT + 1):
            e = session.effective(n)
            if e is None or e.map_id <= 0:
                continue
            if n in session.track_fix and n not in session.inferred_tracks:
                continue  # ручний вибір — не чіпаємо
            ids = self._map_tracks(e.map_id)
            if not ids:
                continue
            hit = ids[0] if len(ids) == 1 else (
                self.narrow_track(ids, e.opponent_time) if e.opponent_time else None)
            if hit and hit != session.track_fix.get(n):
                session.set_track_fix(n, hit, inferred=True)
```

4. На початку `auto_pick` (першим рядком тіла, до перевірки пінів):

```python
        self.resolve_tracks(session)
```

У `app_context.py`:

```python
        self.assistant = AssistantService(self.races_service, self.cars_service,
                                          self.tracks_service)
```

- [x] **Step 4: Тести зелені**

Run: `.venv/Scripts/python -m pytest tests/test_assistant.py -v`
Expected: PASS.

---

### Task 5: Песимістична оцінка min-p̂ в `auto_pick` і `win_chance`

**Files:**
- Modify: `alu_gauntlet_helper/services/assistant.py`
- Test: `tests/test_assistant.py`

**Interfaces:**
- Consumes: `chip_tracks` (Task 4), `Candidate`, `pick_cars`, `laplace`, `beat_stats`.
- Produces (на це спирається Task 7): гонки з невизначеним треком і кандидатами беруть участь в автопідборі й шансі перемоги з p̂ = **min** по треках-кандидатах (кандидат без моїх даних дає 0.5) — спека §5.

- [x] **Step 1: Написати тести, що падають**

Додати в кінець `tests/test_assistant.py`:

```python
# --- Етап 3: песимістична оцінка min-p̂ по треках-кандидатах ----------------


def test_auto_pick_pessimistic_min_over_candidates():
    # авто 501 сильне лише на треку 21 (на 22 даних немає → 0.5);
    # авто 502 стабільне на обох → песимістично краще, його і беремо
    svc = stage3_service(
        by_track={21: {501: [19000] * 10, 502: [21000] * 10},
                  22: {502: [21500] * 10}},
        ranges={21: (19000, 25000), 22: (20000, 26000)},  # звуження не спрацює
        by_map={5: [21, 22]})
    s = session_with(map_race(1, 5, opp_time=24000))
    svc.auto_pick(s)
    assert s.effective(1).suggested_car_id == 502


def test_auto_pick_pessimistic_without_opponent_time():
    # без часу суперника: p=0.5 всюди, margin = min(-avg) — найкращий гірший avg
    svc = stage3_service(
        by_track={21: {501: [19000] * 5, 502: [20000] * 5},
                  22: {501: [30000] * 5, 502: [20500] * 5}},
        by_map={5: [21, 22]})
    s = session_with(map_race(1, 5))
    svc.auto_pick(s)
    assert s.effective(1).suggested_car_id == 502  # min(-avg): 502 стабільніше


def test_win_chance_pessimistic_min():
    svc = stage3_service(
        by_track={21: {501: [19000] * 10}},  # на 22 даних немає
        ranges={21: (19000, 25000), 22: (20000, 26000)},
        by_map={5: [21, 22]})
    s = session_with(map_race(1, 5, opp_time=24000))
    svc.auto_pick(s)
    assert s.effective(1).suggested_car_id == 501
    from alu_gauntlet_helper.services.opponent_picker import prob_at_least
    # p гонки 1 = min(11/12 на треку 21, 0.5 на 22) = 0.5; решта — монетки
    expected = prob_at_least([0.5, 0.5, 0.5, 0.5, 0.5], 3)
    assert abs(svc.win_chance(s) - expected) < 1e-9
```

- [x] **Step 2: Переконатися, що тести падають**

Run: `.venv/Scripts/python -m pytest tests/test_assistant.py -v -k pessimistic`
Expected: FAIL (гонка без track_id пропускається — `suggested_car_id == 0`).

- [x] **Step 3: Реалізація**

У `assistant.py`:

1. Приватний хелпер (після `resolve_tracks`):

```python
    def _pessimistic_candidates(self, track_ids: list[int],
                                opp: int | None) -> list["Candidate"]:
        """Кандидати авто для гонки з невизначеним треком: p̂ і маржин авто —
        МІНІМУМ по треках-кандидатах; трек без моїх даних дає 0.5/0 —
        оцінка «не менше ніж» (спека §5)."""
        per_track = {tid: {v.car_id: v for v in self.suggestions_vs(tid, opp)}
                     for tid in track_ids}
        car_ids = set().union(*per_track.values())
        result = []
        for car_id in car_ids:
            ps, margins = [], []
            for tid in track_ids:
                v = per_track[tid].get(car_id)
                ps.append(v.p_smoothed if v else 0.5)
                margins.append((v.delta if opp else -v.avg_time) if v else 0)
            result.append(Candidate(car_id, min(ps), min(margins)))
        result.sort(key=lambda c: (-c.p, -c.margin))
        return result
```

2. В `auto_pick` замінити рядок

```python
            if e is None or e.track_id <= 0:
                continue
```

на:

```python
            if e is None:
                continue
            if e.track_id <= 0:
                # трек не визначено: якщо є кандидати (карта/близькі OCR-збіги) —
                # песимістична оцінка min-p̂, інакше гонку пропускаємо
                tracks = self.chip_tracks(e)
                if tracks and not e.has_car:
                    cands = self._pessimistic_candidates(tracks, e.opponent_time or None)
                    if cands:
                        race_candidates[n] = cands
                        if n in session.pinned_races and e.suggested_car_id:
                            fixed[n] = e.suggested_car_id
                continue
```

3. У `win_chance` замінити гілку

```python
            elif e and opp and car_id and e.track_id > 0:
                has_opponent = True
                stats = self.beat_stats(e.track_id, car_id, opp)
                probs.append(laplace(*stats) if stats else 0.5)
```

на:

```python
            elif e and opp and car_id and (e.track_id > 0 or self.chip_tracks(e)):
                has_opponent = True
                tracks = [e.track_id] if e.track_id > 0 else self.chip_tracks(e)
                # невизначений трек: песимістичний min по кандидатах (спека §5)
                probs.append(min(
                    laplace(*stats) if (stats := self.beat_stats(t, car_id, opp))
                    else 0.5
                    for t in tracks))
```

- [x] **Step 4: Тести зелені**

Run: `.venv/Scripts/python -m pytest tests/test_assistant.py tests/test_opponent_picker.py -v`
Expected: PASS.

---

### Task 6: UI — чипи треків, map-only картка, бейдж «ймовірно»

**Files:**
- Modify: `alu_gauntlet_helper/views/assistant_tab.py` (`SessionView`)
- Modify: `alu_gauntlet_helper/views/components/race_card.py` (`RaceCard.update_card`)
- Modify: `alu_gauntlet_helper/ui_lang.py` (нові ключі в «en» і «uk»)

**Interfaces:**
- Consumes: `chip_tracks` (Task 4), `set_track_fix` (Task 2), `EffectiveRace.map_id/track_inferred`, `MapsService.get_by_ids`, `TrackInfoWidget`.
- Produces: панель гонки показує ряд чипів `[Трек A] [Трек B]` при неоднозначності (клік — ручний фікс + перерахунок підбору; повторний клік — зняти); картка map-only гонки показує іконку/назву карти і «Трек?»; виведений звуженням трек позначається «?» після назви.

- [x] **Step 1: Переклади**

У `ui_lang.py` в обидва словники після ключів `assistant.*`:

«en»:

```python
        "assistant.track_unknown": "Track?",
        "assistant.track_probable_tooltip": "Likely track — narrowed down by the opponent's time. Click a chip to change.",
```

«uk»:

```python
        "assistant.track_unknown": "Трек?",
        "assistant.track_probable_tooltip": "Ймовірний трек — звужено за часом суперника. Клікни чип, щоб змінити.",
```

- [x] **Step 2: Чипи в SessionView**

У `assistant_tab.py`:

1. Імпорт `QPushButton` уже є; в `SessionView.__init__` після створення `self.suggestions` додати:

```python
        # чипи вибору треку при неоднозначності (спека §4): [Трек A] [Трек B]
        self.chips_widget = QWidget()
        self.chips_row = QHBoxLayout(self.chips_widget)
        self.chips_row.setContentsMargins(0, 0, 0, 0)
        self.chips_row.setSpacing(6)
        self.chips_widget.hide()
```

і в layout між картками та списком:

```python
        layout.addLayout(cards_row)
        layout.addWidget(self.chips_widget)
        layout.addWidget(self.suggestions, stretch=1)
```

2. У `refresh()` перед `self._refresh_suggestions(effective)` додати
`self._refresh_chips(effective)`; нові методи після `_refresh_suggestions`:

```python
    def _refresh_chips(self, effective):
        while self.chips_row.count():
            item = self.chips_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        e = effective.get(self.selected_race)
        ids = APP_CONTEXT.assistant.chip_tracks(e) if e else []
        if not ids:
            self.chips_widget.hide()
            return
        tracks = APP_CONTEXT.tracks_service.get_by_ids(set(ids))
        for tid in ids:
            track = tracks.get(tid)
            name = track.display_name if track else str(tid)
            chip = QPushButton(name)
            chip.setObjectName("secondary")
            chip.setCheckable(True)
            chip.setChecked(bool(e) and e.track_id == tid)
            if e and e.track_id == tid and e.track_inferred:
                chip.setText(name + " ?")
                chip.setToolTip(ui_lang.t("assistant.track_probable_tooltip"))
            chip.clicked.connect(lambda _, t=tid: self._on_chip_clicked(t))
            self.chips_row.addWidget(chip)
        self.chips_row.addStretch()
        self.chips_widget.show()

    def _on_chip_clicked(self, track_id: int):
        e = self.session.effective(self.selected_race)
        # повторний клік по вибраному — зняти ручний вибір
        self.session.set_track_fix(
            self.selected_race,
            None if e is not None and e.track_id == track_id else track_id)
        # трек змінився — перерахувати рекомендації (авто-режим шанує піни)
        APP_CONTEXT.assistant.auto_pick(self.session)
```

3. `_refresh_suggestions`: без змін — при виборі чипа `track_id > 0` і список
   пропозицій оживає сам.

- [x] **Step 3: Map-only картка і бейдж «?»**

1. У `SessionView.refresh()` після `tracks = ...` додати збір карт:

```python
        map_ids = {e.map_id for e in effective.values() if e.map_id and not e.track_id}
        maps = APP_CONTEXT.maps_service.get_by_ids(map_ids)
```

і в циклі карток передати карту:

```python
            map_ = maps.get(e.map_id) if e and e.map_id and not e.track_id else None
            ...
            card.update_card(e, track, car, beat, checked=self._is_checked(n, e),
                             selected=(n == self.selected_race), suggested=suggested,
                             map_=map_)
```

2. У `race_card.py` розширити сигнатуру і блок треку `update_card`:

```python
    def update_card(self, e, track, car, beat, checked: bool, selected: bool,
                    suggested: bool = False, map_=None):
```

(докстрінг доповнити: `map_: Map | None — карта map-only гонки (трек ще не
визначено), показується замість треку з підписом «Трек?»`), а блок

```python
        if track is not None:
            warn = WARN_ICON if e is not None and e.track_uncertain else ""
            self._set_track_info(TrackInfoWidget(
                track.map_icon or "", track.icon or "",
                track.display_map_name, warn + track.display_name))
        else:
            # трек невідомий — компонент не показуємо зовсім (порожнє місце)
            self._set_track_info(TrackInfoWidget("", "", "", ""))
        self.track_info.setVisible(track is not None)
```

замінити на:

```python
        if track is not None:
            warn = WARN_ICON if e is not None and e.track_uncertain else ""
            # трек, виведений звуженням за часом, — з позначкою «?» (спека §4)
            probable = " ?" if e is not None and e.track_inferred else ""
            self._set_track_info(TrackInfoWidget(
                track.map_icon or "", track.icon or "",
                track.display_map_name, warn + track.display_name + probable))
        elif map_ is not None:
            # карта відома (екран 3), трек — ще ні: іконка карти + «Трек?»
            self._set_track_info(TrackInfoWidget(
                map_.icon or "", "", map_.display_name,
                ui_lang.t("assistant.track_unknown")))
        else:
            # ні треку, ні карти — компонент не показуємо зовсім (порожнє місце)
            self._set_track_info(TrackInfoWidget("", "", "", ""))
        self.track_info.setVisible(track is not None or map_ is not None)
```

- [x] **Step 4: Повний прогін тестів**

Run: `.venv/Scripts/python -m pytest tests`
Expected: PASS (UI-віджети юніт-тестами не покриваються — у проєкті їх немає; логіка чипів покрита Task 4).

- [x] **Step 5: Ручна перевірка (користувач або виконавець із дисплеєм)**

Запустити `python main.py`, відсканувати акордеон BEFORE із треком, який
розпізнається неоднозначно (або тимчасово підкинути в сесію
`FieldGuess(score=0.6, candidates=[(a, 0.93), (b, 0.91)])`): над списком
пропозицій має зʼявитися ряд чипів; клік перемикає трек картки і список
пропозицій; повторний клік знімає вибір; Edit-діалог (ручний трек) ховає чипи.

---

### Task 7: Регрес і самоперевірка проти спеки

**Files:** без нових змін (лише прогін і звірка).

- [x] **Step 1: Повний прогін**

Run: `.venv/Scripts/python -m pytest tests`
Expected: PASS (OCR-тести можуть скіпатись без Tesseract — це нормально).

- [x] **Step 2: Звірка зі спекою (розділи 1, 4, 5, 6)**

- §1: `RaceCapture.map` є; `track_fix` є; `EffectiveRace` має `map_id`,
  `track_candidates`, `track_inferred` — так.
- §4: чипи `[Трек A] [Трек B]` з бейджем «?» на звуженому; фолбек-автокомплит
  при невідомій карті — наявний Edit-діалог (RaceDialog з автокомплитом).
- §5: невизначений трек → min-p̂ по кандидатах в auto_pick і win_chance.
- §6: звуження ±10%, рівно один кандидат → «ймовірно визначений».
- Розпізнавальна частина §3 (екрани 2/3, іконки карт) — свідомо поза планом,
  чекає скріншотів користувача.

---

## Поправки після фінального ревʼю (спека переважає план)

Фінальне ревʼю всієї гілки знайшло дві розбіжності коду цього плану зі
затвердженою спекою; виправлено в бік спеки:

1. **Песимістична оцінка (§5) діє і для невпевненого OCR-треку.** У плані
   min-p̂ вмикався лише при `track_id <= 0`, але effective() завжди ставить
   топ-кандидата у `track_id` — тож min-p̂ був недосяжний для сьогоднішнього
   (акордеонного) сценарію чипів. Додано `AssistantService._estimate_tracks(e)`:
   визначений трек (упевнений скан/драфт/фікс) → він сам; невпевнений або
   map-only → кандидати; `auto_pick`/`win_chance` рахують по ньому. Ручний чи
   виведений фікс лишається «довіреним» (оптимістична оцінка по вибраному треку).
2. **Звуження (§6) вимагає моїх заїздів на ВСІХ кандидатах.** Планова версія
   `narrow_track` виводила трек із відсутності даних (кандидат без заїздів
   ніколи не «влучає»); за спекою «немає моїх заїздів → трек невизначений» —
   тепер будь-який кандидат без діапазону робить звуження неможливим.

Дрібні супутні фікси: ліміт чипів застосовується після вставки фікс-треку;
повторний клік по чипу (deselect) не викликає auto_pick (інакше resolve_tracks
миттєво повертав би виведений фікс); подвійний виклик `chip_tracks` у
`win_chance` усунено; авто, відоме на гонці з невизначеним треком, резервується
в переборі (`fixed`), щоб інші гонки його не забирали.
