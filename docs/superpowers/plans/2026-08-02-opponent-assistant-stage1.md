# Асистент проти суперника — Етап 1: план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Читати дані суперника з акордеона BEFORE (авто + TIME TO BEAT), вести кілька незалежних сесій із правилами мержу/конфлікту, і в новому табі асистента підбирати 5 різних авто проти часів суперника (вручну і кнопкою «Авто» з максимізацією P(виграти ≥3 з 5)).

**Architecture:** Дані суперника — нові незалежні поля в `RaceCapture`/`EffectiveRace` (мерж полів «про мене» і «про суперника» не перетинається). Новий `SessionManager` тримає список `ChallengeSessionService`-сесій, роутить скани в активну і відщеплює/замінює сесії при конфлікті часів суперника. Чиста математика підбору — окремий модуль `opponent_picker`; глю зі статистикою БД — `AssistantService`. UI — новий `AssistantTab` (картки 5 гонок + панель підбору + збереження), який замінює `CaptureTab`.

**Tech Stack:** Python 3.9+ (у коді реально використовуються 3.10+ анотації `X | None` — дотримуйся стилю файлів), PyQt6, pytest, наявний OCR-конвеєр (Tesseract через dll).

## Global Constraints

- **Жодних міграцій БД і нових таблиць/колонок** — усі нові дані живуть лише в памʼяті процесу (спека, розділ «Мета»).
- **Git-коміти НЕ робити** — користувач комітить сам (його явне правило). Завдання закінчуються зеленими тестами, без кроку commit.
- Мова UI-рядків: додавати ключі в ОБИДВІ мови `ui_lang.TRANSLATIONS` («en» і «uk»).
- Коментарі в коді — українською, в стилі наявних файлів.
- Тести запускати як `python -m pytest tests/<file> -v` з кореня репо. OCR-тести самі скіпаються без Tesseract/фікстур — це нормально.
- Спека: `docs/superpowers/specs/2026-08-02-opponent-assistant-design.md`. Скріншоти акордеона вже є у `tests/fixtures/` (значення суперника задокументовані в докстрінгах наявних тестів).
- УВАГА: `python` на цій машині — Windows; шляхи в командах через `/` працюють у Git Bash.

---

### Task 1: Поля суперника в моделях і мерж у сесії

**Files:**
- Modify: `alu_gauntlet_helper/models.py` (клас `RaceCapture`)
- Modify: `alu_gauntlet_helper/services/challenge_session.py` (`EffectiveRace`, `_merge`, `effective`)
- Test: `tests/test_challenge_session.py`

**Interfaces:**
- Consumes: наявні `FieldGuess`, `merge_guess`.
- Produces: `RaceCapture.opponent_time: int | None`, `RaceCapture.opponent_car: FieldGuess | None`; `EffectiveRace.opponent_time: int` (0 = невідомий), `EffectiveRace.opponent_car_id: int` (0 = невідоме). Групи полів «про мене» (`car/rank/time`) і «про суперника» (`opponent_*`) мержаться незалежно — на це спираються Task 3 і 4.

- [ ] **Step 1: Написати тести, що падають**

Додати в кінець `tests/test_challenge_session.py` (хелпер `capture` розширити параметрами):

```python
# --- дані суперника (opponent_time / opponent_car) -----------------------


def opp_capture(n, opp_time=None, opp_car_score=None, **kw):
    c = capture(n, **kw)
    c.opponent_time = opp_time
    if opp_car_score is not None:
        c.opponent_car = FieldGuess(value=30 + n, score=opp_car_score)
    return c


def test_opponent_fields_default_none():
    c = capture(1)
    assert c.opponent_time is None and c.opponent_car is None


def test_merge_opponent_fields_independent_of_mine():
    # BEFORE-скан (суперник) і мій результат чергуються — не затирають одне одного
    s = ChallengeSessionService()
    s.apply(result(opp_capture(1, opp_time=19152, opp_car_score=0.9)))
    s.apply(result(capture(1, car_score=0.9, rank=4795, time=19130)))
    r = s.races[1]
    assert r.opponent_time == 19152 and r.opponent_car.value == 31
    assert r.time == 19130 and r.car.value == 21


def test_merge_opponent_car_by_score():
    s = ChallengeSessionService()
    s.apply(result(opp_capture(1, opp_car_score=0.9)))
    low = opp_capture(1)
    low.opponent_car = FieldGuess(value=99, score=0.5)
    s.apply(result(low))
    assert s.races[1].opponent_car.value == 31  # впевненіше лишилось


def test_effective_exposes_opponent_fields():
    s = ChallengeSessionService()
    s.apply(result(opp_capture(2, opp_time=26591, opp_car_score=0.9, track_score=0.9)))
    e = s.effective(2)
    assert e.opponent_time == 26591
    assert e.opponent_car_id == 32


def test_effective_not_none_for_opponent_only_capture():
    # скан дав лише час суперника (без треку) — картка має бути видимою
    s = ChallengeSessionService()
    s.apply(result(opp_capture(3, opp_time=30000)))
    assert s.effective(3) is not None
    assert s.effective(3).opponent_time == 30000
```

- [ ] **Step 2: Переконатися, що тести падають**

Run: `python -m pytest tests/test_challenge_session.py -v -k opponent`
Expected: FAIL (`opponent_time` — unknown attribute / ValidationError).

- [ ] **Step 3: Реалізація**

У `models.py` до `RaceCapture` після `time`:

```python
    # Дані суперника з BEFORE-варіанта акордеона — НЕЗАЛЕЖНА група полів:
    # ніколи не мержиться з полями гравця (car/rank/time) і навпаки.
    opponent_time: int | None = None  # мс, "TIME TO BEAT"
    opponent_car: FieldGuess | None = None
```

У `challenge_session.py` до `EffectiveRace` після `note`:

```python
    opponent_time: int = 0
    opponent_car_id: int = 0
```

В `EffectiveRace.is_empty` розширити умову:

```python
        return not (self.track_id > 0 or self.has_car or self.rank > 0
                    or self.time > 0 or self.note or self.bad_timing
                    or self.opponent_time > 0 or self.opponent_car_id > 0)
```

У `ChallengeSessionService._merge` після рядка з `current.time`:

```python
        if new.opponent_time is not None:
            current.opponent_time = new.opponent_time
        current.opponent_car = merge_guess(current.opponent_car, new.opponent_car)
```

У `effective()` в гілці `if capture:` (драфти суперника не редагують — беремо з OCR напряму):

```python
            if capture.opponent_time:
                e.opponent_time = capture.opponent_time
            if capture.opponent_car:
                e.opponent_car_id = capture.opponent_car.value
```

- [ ] **Step 4: Тести зелені**

Run: `python -m pytest tests/test_challenge_session.py tests/test_capture_models.py -v`
Expected: PASS (усі, включно зі старими).

---

### Task 2: Закріплення авто і «одноразовість» сесії

**Files:**
- Modify: `alu_gauntlet_helper/services/challenge_session.py`
- Test: `tests/test_challenge_session.py`

**Interfaces:**
- Produces (на це спираються Task 4, 7, 10):
  - `ChallengeSessionService.assigned_cars: dict[int, int]` (race_number → car_id), `pinned_races: set[int]`, `created_at: datetime`;
  - `set_assigned(race_number: int, car_id: int | None, pinned: bool = True) -> None` — ручне закріплення; одне авто — одна гонка (перекріплення знімає зі старої);
  - `set_assignments(assignment: dict[int, int]) -> None` — результат автопідбору: перезаписує лише НЕзапінені гонки;
  - `clear_pins() -> None` — зняти всі піни (для кнопки «Авто»);
  - `is_disposable: bool` (property) — немає моїх часів і драфтів;
  - `timed_count: int` (property) — кількість гонок з моїм часом (для заголовка таба сесії).

- [ ] **Step 1: Тести, що падають**

```python
# --- закріплення авто / одноразовість сесії -------------------------------


def test_set_assigned_one_car_one_race():
    s = ChallengeSessionService()
    s.set_assigned(1, 501)
    s.set_assigned(2, 502)
    s.set_assigned(3, 501)  # перекріплення: авто 501 переїжджає з гонки 1 на 3
    assert s.assigned_cars == {2: 502, 3: 501}
    assert s.pinned_races == {2, 3}


def test_set_assigned_none_unassigns():
    s = ChallengeSessionService()
    s.set_assigned(1, 501)
    s.set_assigned(1, None)
    assert s.assigned_cars == {} and s.pinned_races == set()


def test_set_assignments_keeps_pins():
    s = ChallengeSessionService()
    s.set_assigned(2, 502)                      # ручний пін
    s.set_assigned(4, 504, pinned=False)        # авто-призначення
    s.set_assignments({1: 501, 2: 999, 3: 503})  # автопідбір
    assert s.assigned_cars == {2: 502, 1: 501, 3: 503}  # пін гонки 2 не перезаписано, 4 знято
    assert s.pinned_races == {2}


def test_clear_pins():
    s = ChallengeSessionService()
    s.set_assigned(2, 502)
    s.clear_pins()
    assert s.pinned_races == set()
    assert s.assigned_cars == {2: 502}  # закріплення лишилось, лише статус піна знято


def test_assignment_notifies_listeners():
    s = ChallengeSessionService()
    events = []
    s.add_listener(lambda: events.append(1))
    s.set_assigned(1, 501)
    s.set_assignments({2: 502})
    assert len(events) == 2


def test_clear_resets_assignments():
    s = ChallengeSessionService()
    s.set_assigned(1, 501)
    s.clear()
    assert s.assigned_cars == {} and s.pinned_races == set()


def test_is_disposable():
    s = ChallengeSessionService()
    assert s.is_disposable  # порожня
    s.apply(result(opp_capture(1, opp_time=19152, track_score=0.9)))
    s.set_assigned(1, 501)
    assert s.is_disposable  # лише дані суперника і піни — все ще одноразова
    s.apply(result(capture(2, time=20000)))
    assert not s.is_disposable  # з'явився МІЙ час


def test_is_disposable_false_with_draft():
    s = ChallengeSessionService()
    s.set_draft(1, draft(note="x"))
    assert not s.is_disposable


def test_timed_count():
    s = ChallengeSessionService()
    s.apply(result(capture(1, time=20000)))
    s.apply(result(opp_capture(2, opp_time=19152)))
    s.set_draft(3, draft(time=21000))
    assert s.timed_count == 2  # мій OCR-час + час у драфті; час суперника не рахується
```

- [ ] **Step 2: Переконатися, що падають**

Run: `python -m pytest tests/test_challenge_session.py -v -k "assigned or disposable or pins or timed"`
Expected: FAIL (`set_assigned` не існує).

- [ ] **Step 3: Реалізація**

У `ChallengeSessionService.__init__` додати:

```python
        self.created_at = datetime.now()
        self.assigned_cars: dict[int, int] = {}  # race_number -> car_id (закріплені авто)
        self.pinned_races: set[int] = set()      # гонки, закріплені вручну (автопідбір не чіпає)
```

(імпорт `from datetime import datetime` угорі файлу). Методи:

```python
    # --- закріплення авто (порада «яким авто їхати цю гонку») -------------

    def set_assigned(self, race_number: int, car_id: int | None, pinned: bool = True):
        """Закріпити авто за гонкою (None — зняти). Одне авто — одна гонка:
        повторний вибір знімає авто з попередньої гонки й закріплює за новою."""
        if car_id is None:
            self.assigned_cars.pop(race_number, None)
            self.pinned_races.discard(race_number)
        else:
            for n, c in list(self.assigned_cars.items()):
                if c == car_id and n != race_number:
                    del self.assigned_cars[n]
                    self.pinned_races.discard(n)
            self.assigned_cars[race_number] = car_id
            if pinned:
                self.pinned_races.add(race_number)
            else:
                self.pinned_races.discard(race_number)
        self._notify()

    def set_assignments(self, assignment: dict[int, int]):
        """Результат автопідбору: перезаписує лише незапінені гонки, піни недоторкані."""
        for n in list(self.assigned_cars):
            if n not in self.pinned_races:
                del self.assigned_cars[n]
        for n, car_id in assignment.items():
            if n not in self.pinned_races:
                self.assigned_cars[n] = car_id
        self._notify()

    def clear_pins(self):
        self.pinned_races = set()

    @property
    def is_disposable(self) -> bool:
        """Немає моїх часів і ручних правок — сесію можна тихо замінити новою
        (це і є поведінка скаутингу «кожен скан кандидата затирає попереднього»)."""
        return not self.drafts and not any(c.time for c in self.races.values())

    @property
    def timed_count(self) -> int:
        """Кількість гонок з моїм часом — для заголовка таба відщепленої сесії."""
        return sum(1 for n in range(1, RACE_COUNT + 1)
                   if (e := self.effective(n)) is not None and e.time > 0)
```

У `clear()` додати `self.assigned_cars = {}` та `self.pinned_races = set()`.

- [ ] **Step 4: Тести зелені**

Run: `python -m pytest tests/test_challenge_session.py -v`
Expected: PASS.

---

### Task 3: Акордеон — читання авто і часу суперника

**Files:**
- Modify: `alu_gauntlet_helper/screen_recognition/regions.py`
- Modify: `alu_gauntlet_helper/screen_recognition/screens/challenge_accordion.py`
- Test: `tests/test_challenge_accordion.py`

**Interfaces:**
- Consumes: `ocr.read_time(img) -> int | None`, `ocr.read_name(img) -> str`, `car_matcher.match(text) -> FieldGuess | None`, `RaceCapture.opponent_*` з Task 1.
- Produces: обидва варіанти акордеона (BEFORE і AFTER) повертають `RaceCapture` з заповненими `opponent_car`/`opponent_time`; нові константи `ACCORDION_OPPONENT_CAR`, `ACCORDION_OPPONENT_TIME` у `regions.py`.

- [ ] **Step 1: Тести, що падають**

У `tests/test_challenge_accordion.py`:

1. У словник авто додати суперника з фікстури shanghai (він тепер ПОТРІБЕН, а не лише «пастка»):

```python
CAR_MITSUBISHI_LANCER = 208
```

і в `CAR_VOCAB` рядок `(CAR_MITSUBISHI_LANCER, "Mitsubishi Lancer Evolution"),`.

2. Доповнити наявні тести асертами на суперника (значення — з докстрінгів цих самих тестів; коментар «дані суперника не витягуються» в секції BEFORE замінити на «дані суперника йдуть в ОКРЕМІ поля opponent_*»):

```python
# test_after_1_player_data — додати:
    assert c.opponent_car and c.opponent_car.value == CAR_BUGATTI_CHIRON
    assert c.opponent_time == 19152

# test_after_2_player_data — додати:
    assert c.opponent_car and c.opponent_car.value == CAR_KOENIGSEGG_CCXR
    assert c.opponent_time == 26591

# test_after_4_lost_race_red_time — додати:
    assert c.opponent_car and c.opponent_car.value == CAR_LYKAN_HYPERSPORT
    assert c.opponent_time == 24164

# test_after_shanghai_paris_of_the_east_track — додати:
    assert c.opponent_car and c.opponent_car.value == CAR_MITSUBISHI_LANCER
    assert c.opponent_time == 37672

# test_before_1_no_opponent_data — додати (і перейменувати
# на test_before_1_opponent_in_dedicated_fields):
    assert c.opponent_car and c.opponent_car.value == CAR_BUGATTI_CHIRON
    assert c.opponent_time == 19152

# test_before_3_no_opponent_data → test_before_3_opponent_in_dedicated_fields:
    assert c.opponent_car and c.opponent_car.value == CAR_RIMAC_NEVERA_TA
    assert c.opponent_time == 19736

# test_before_5_no_opponent_data → test_before_5_opponent_in_dedicated_fields:
    assert c.opponent_car and c.opponent_car.value == CAR_ULTIMA_RS
    assert c.opponent_time == 30847

# test_old_fixture_race1_is_before_variant — додати:
    assert c.opponent_car and c.opponent_car.value == CAR_ULTIMA_RS
    assert c.opponent_time == 22797
```

ВАЖЛИВО: наявні асерти `c.time is None` / `c.rank is None` у BEFORE-тестах ЛИШАЮТЬСЯ — поля гравця, як і раніше, не заповнюються з BEFORE-екрана. RU-тести (`test_ru_car_selection`) не чіпати: значення суперника для тих фікстур не задокументовані.

- [ ] **Step 2: Переконатися, що падають**

Run: `python -m pytest tests/test_challenge_accordion.py -v`
Expected: FAIL на нових асертах (`opponent_time is None`). Якщо все скіпнулось — немає Tesseract; тоді виконуй Step 3 і перевір на машині з Tesseract (він тут має бути — див. `TESSERACT_OK`).

- [ ] **Step 3: Реалізація**

У `regions.py` після `AFTER_PLAYER_TIME`:

```python
# ЛІВИЙ бік розгорнутої панелі — суперник. Присутній в ОБОХ варіантах екрана
# (before/after): авто суперника зверху зліва, "TIME TO BEAT" знизу зліва.
# Початкові значення — дзеркало правих регіонів гравця; калібрувати за
# tests/fixtures/accordion_before_{1,3,5}.png у разі промахів OCR.
ACCORDION_OPPONENT_CAR = RelRect(0.0, 0.12, 0.38, 0.18)   # бренд + модель авто суперника
ACCORDION_OPPONENT_TIME = RelRect(0.0, 0.78, 0.45, 0.18)  # час "00:19.152" (без лейбла TIME TO BEAT)
```

У `challenge_accordion.py`:

1. В імпорт з `regions` додати `ACCORDION_OPPONENT_CAR, ACCORDION_OPPONENT_TIME`.
2. У `extract()` після рядка `race_number, panel, language = found` додати:

```python
        # Лівий бік — суперник (є в обох варіантах): авто + "TIME TO BEAT".
        # Йдуть у ВИДІЛЕНІ поля opponent_* і ніколи — у поля гравця.
        opponent_time = ocr.read_time(panel.sub(ACCORDION_OPPONENT_TIME).crop(img))
        opponent_car = self.car_matcher.match(
            ocr.read_name(panel.sub(ACCORDION_OPPONENT_CAR).crop(img)))
```

3. В ОБИДВА `return [RaceCapture(...)]` додати аргументи:

```python
                opponent_time=opponent_time,
                opponent_car=opponent_car,
```

4. Оновити докстрінг класу: BEFORE тепер повертає «номер гонки, трек + дані суперника в opponent_*».

- [ ] **Step 4: Тести зелені (з калібруванням за потреби)**

Run: `python -m pytest tests/test_challenge_accordion.py -v`
Expected: PASS.

Якщо OCR не читає час/авто суперника — регіони треба калібрувати. Метод: зберегти кропи в scratchpad і подивитися очима, що саме ріжеться:

```python
# запусти: python calibrate_opponent.py (тимчасовий файл У SCRATCHPAD, не в репо)
import cv2
from alu_gauntlet_helper.screen_recognition.regions import (
    ACCORDION_AFTER_PANELS, ACCORDION_OPPONENT_CAR, ACCORDION_OPPONENT_TIME)
img = cv2.imread("tests/fixtures/accordion_before_1.png")
panel = ACCORDION_AFTER_PANELS[0]  # RACE 1 розгорнута
cv2.imwrite("opp_car.png", panel.sub(ACCORDION_OPPONENT_CAR).crop(img))
cv2.imwrite("opp_time.png", panel.sub(ACCORDION_OPPONENT_TIME).crop(img))
```

Рухати `x/y/w/h` частками панелі, поки кроп не міститиме рівно текст (без рамок панелі — вертикальна лінія на краю ламає tesseract, див. коментар до `ACCORDION_HEADER`). Після зелених тестів тимчасовий скрипт видалити.

- [ ] **Step 5: Повний прогін розпізнавання**

Run: `python -m pytest tests/test_challenge_accordion.py tests/test_car_selection_fast.py tests/test_engine.py tests/test_screen_gates.py tests/test_captures_regression.py -v`
Expected: PASS (регресії інших екранів немає).

---

### Task 4: SessionManager

**Files:**
- Create: `alu_gauntlet_helper/services/session_manager.py`
- Test: `tests/test_session_manager.py`

**Interfaces:**
- Consumes: `ChallengeSessionService` (Task 1–2), `RecognitionResult`.
- Produces (на це спираються Task 8, 10):
  - `SessionManager(auto_pick: Callable[[ChallengeSessionService], None] | None = None)`;
  - `sessions: list[ChallengeSessionService]` (остання — активна), `active: ChallengeSessionService` (property);
  - `apply(result: RecognitionResult) -> None` — роутинг скану з правилом конфлікту;
  - `close(session) -> None` — після Save/Discard; завжди лишається ≥1 сесія;
  - `add_listener(fn)/remove_listener(fn)` — єдина точка підписки для UI/оверлея: спрацьовує і на зміни всередині будь-якої сесії, і на структурні зміни (нова/закрита сесія).

- [ ] **Step 1: Тести, що падають**

Створити `tests/test_session_manager.py`:

```python
from alu_gauntlet_helper.models import FieldGuess, RaceCapture, RecognitionResult
from alu_gauntlet_helper.services.session_manager import SessionManager


def capture(n, opp_time=None, time=None, track_score=None):
    return RaceCapture(
        race_number=n,
        track=FieldGuess(value=10 + n, score=track_score) if track_score is not None else None,
        time=time,
        opponent_time=opp_time,
    )


def result(*captures):
    return RecognitionResult(screen="test", captures=list(captures))


def test_starts_with_one_empty_active_session():
    m = SessionManager()
    assert len(m.sessions) == 1
    assert m.active is m.sessions[0]


def test_apply_routes_to_active():
    m = SessionManager()
    m.apply(result(capture(1, opp_time=19152)))
    assert m.active.races[1].opponent_time == 19152


def test_same_opponent_time_merges_no_new_session():
    m = SessionManager()
    m.apply(result(capture(1, opp_time=19152)))
    m.apply(result(capture(1, opp_time=19152, track_score=0.9)))
    assert len(m.sessions) == 1
    assert m.active.races[1].track.value == 11


def test_track_mismatch_is_not_conflict():
    # розбіжність лише треку — корекція розпізнавання, НЕ новий суперник
    m = SessionManager()
    first = capture(1, opp_time=19152, track_score=0.6)
    m.apply(result(first))
    better = capture(1, opp_time=19152)
    better.track = FieldGuess(value=99, score=0.95)
    m.apply(result(better))
    assert len(m.sessions) == 1
    assert m.active.races[1].track.value == 99


def test_conflict_replaces_disposable_session():
    # скаутинг: новий кандидат затирає попереднього (немає моїх часів)
    m = SessionManager()
    m.apply(result(capture(1, opp_time=19152)))
    old = m.active
    m.apply(result(capture(1, opp_time=25000)))
    assert len(m.sessions) == 1
    assert m.active is not old
    assert m.active.races[1].opponent_time == 25000


def test_conflict_detaches_valuable_session():
    # у сесії мій час → вона відщеплюється табом, нова стає активною
    m = SessionManager()
    m.apply(result(capture(1, opp_time=19152), capture(2, time=20000)))
    old = m.active
    m.apply(result(capture(1, opp_time=25000)))
    assert len(m.sessions) == 2
    assert m.sessions[0] is old            # стара збережена
    assert m.active.races[1].opponent_time == 25000
    assert old.races[1].opponent_time == 19152  # стара недоторкана


def test_close_removes_and_keeps_at_least_one():
    m = SessionManager()
    m.apply(result(capture(1, opp_time=19152), capture(2, time=20000)))
    old = m.active
    m.apply(result(capture(1, opp_time=25000)))
    m.close(old)
    assert old not in m.sessions and len(m.sessions) == 1
    m.close(m.active)
    assert len(m.sessions) == 1  # нова порожня створена
    assert m.active.races == {}


def test_listener_fires_on_session_changes_and_structure():
    m = SessionManager()
    events = []
    m.add_listener(lambda: events.append(1))
    m.apply(result(capture(1, opp_time=19152)))          # 1 подія (apply сесії)
    m.apply(result(capture(1, opp_time=25000)))          # заміна (структурна) + apply
    assert len(events) >= 3
    n = len(events)
    m.close(m.active)                                     # структурна
    assert len(events) > n


def test_closed_session_stops_notifying():
    m = SessionManager()
    # мій час + час суперника: сесія цінна, і конфлікт буде детектовано
    m.apply(result(capture(2, time=20000, opp_time=30000)))
    old = m.active
    m.apply(result(capture(2, opp_time=1)))  # конфлікт → old відщеплюється
    assert len(m.sessions) == 2
    m.close(old)
    events = []
    m.add_listener(lambda: events.append(1))
    old.clear()  # зміни в закритій сесії — менеджер мовчить
    assert events == []


def test_auto_pick_called_after_opponent_scan():
    picked = []
    m = SessionManager(auto_pick=lambda s: picked.append(s))
    m.apply(result(capture(1, time=20000)))     # мій результат — без автопідбору
    assert picked == []
    m.apply(result(capture(1, opp_time=19152)))  # дані суперника — автопідбір
    assert picked == [m.active]


def test_empty_result_is_noop():
    m = SessionManager()
    events = []
    m.add_listener(lambda: events.append(1))
    m.apply(result())
    assert events == [] and len(m.sessions) == 1
```

- [ ] **Step 2: Переконатися, що падають**

Run: `python -m pytest tests/test_session_manager.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Реалізація**

Створити `alu_gauntlet_helper/services/session_manager.py`:

```python
from typing import Callable

from alu_gauntlet_helper.models import RecognitionResult
from alu_gauntlet_helper.services.challenge_session import ChallengeSessionService


class SessionManager:
    """Список сесій челенджів. Скани завжди йдуть в АКТИВНУ (останню) сесію.

    Конфлікт = розбіжність opponent_time (мс — практично унікальний відбиток
    суперника) у будь-якому слоті. Розбіжність лише треку/авто конфліктом не є —
    це корекція розпізнавання, вирішується звичайним мержем за score.

    При конфлікті одноразова сесія (без моїх часів і правок) тихо замінюється,
    цінна — лишається в списку табом (read-only для сканів), нова стає активною.
    Викликається тільки з UI-потоку (як і ChallengeSessionService)."""

    def __init__(self, auto_pick: Callable[[ChallengeSessionService], None] | None = None):
        self._auto_pick = auto_pick
        self.sessions: list[ChallengeSessionService] = []
        self._listeners: list[Callable[[], None]] = []
        self._new_session()

    @property
    def active(self) -> ChallengeSessionService:
        return self.sessions[-1]

    # --- listener-и: єдина точка підписки для UI й оверлея -----------------

    def add_listener(self, listener: Callable[[], None]):
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[], None]):
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify(self):
        for listener in list(self._listeners):
            listener()

    # --- життєвий цикл -----------------------------------------------------

    def _new_session(self) -> ChallengeSessionService:
        session = ChallengeSessionService()
        session.add_listener(self._notify)  # зміни сесії ретранслюються нагору
        self.sessions.append(session)
        return session

    def _drop(self, session: ChallengeSessionService):
        session.remove_listener(self._notify)
        if session in self.sessions:
            self.sessions.remove(session)

    def close(self, session: ChallengeSessionService):
        """Після Save або Discard: сесія зникає зі списку; завжди лишається ≥1."""
        self._drop(session)
        if not self.sessions:
            self._new_session()
        self._notify()

    # --- роутинг сканів ----------------------------------------------------

    @staticmethod
    def _conflicts(session: ChallengeSessionService, result: RecognitionResult) -> bool:
        for c in result.captures:
            current = session.races.get(c.race_number)
            if (current is not None and current.opponent_time and c.opponent_time
                    and current.opponent_time != c.opponent_time):
                return True
        return False

    def apply(self, result: RecognitionResult):
        if not result.captures:
            return
        if self._conflicts(self.active, result):
            if self.active.is_disposable:
                self._drop(self.active)  # скаутинг: свіжий кандидат затирає старого
            self._new_session()
            self._notify()  # структурна зміна — UI перемикається на нову активну
        has_opponent_data = any(c.opponent_time or c.opponent_car for c in result.captures)
        self.active.apply(result)  # сесія сама нотифікує через ретрансляцію
        if has_opponent_data and self._auto_pick:
            self._auto_pick(self.active)
```

- [ ] **Step 4: Тести зелені**

Run: `python -m pytest tests/test_session_manager.py -v`
Expected: PASS.

---

### Task 5: Статистика «мої часи проти часу суперника»

**Files:**
- Modify: `alu_gauntlet_helper/services/races.py` (`RacesRepository`, `RacesService`)
- Create: `alu_gauntlet_helper/services/assistant.py` (модель `VsSuggestion` + `AssistantService.suggestions_vs`)
- Test: `tests/test_assistant.py`

**Interfaces:**
- Consumes: `CarSuggestion` (base-модель полів авто), `CarsService.get_by_ids`.
- Produces (на це спираються Task 6–7, 9–10):
  - `RacesRepository.get_recent_clean_times_by_car(track_id: int, limit: int = 10) -> dict[int, list[int]]` — car_id → часи останніх ≤10 чистих (без 👎) заїздів на треку; `RacesService`-обгортка з тією самою сигнатурою;
  - `class VsSuggestion(CarSuggestion)`: `beat_count: int`, `sample_count: int`, `delta: int` (opponent_time − avg_time, мс; >0 — я в середньому швидший; 0 якщо час суперника невідомий), `p_smoothed: float`;
  - `AssistantService(races: RacesService, cars: CarsService)`;
  - `AssistantService.suggestions_vs(track_id: int, opponent_time: int | None) -> list[VsSuggestion]` — сортування: з часом суперника за (−p_smoothed, −delta); без — favorite ↓, avg_time ↑ (як наявні пропозиції).

- [ ] **Step 1: Тести, що падають**

Створити `tests/test_assistant.py` (сервіс тестуємо з фейковими репо — без БД, у стилі стабів проєкту):

```python
from types import SimpleNamespace

from alu_gauntlet_helper.services.assistant import AssistantService, VsSuggestion


def fake_car(car_id, name="Car", favorite=False):
    return SimpleNamespace(id=car_id, name=name, brand="B", model=name, car_class="S",
                           rank=4000, favorite=favorite, icon="")


class FakeRaces:
    def __init__(self, times_by_car):
        self.times_by_car = times_by_car

    def get_recent_clean_times_by_car(self, track_id, limit=10):
        return self.times_by_car


class FakeCars:
    def __init__(self, cars):
        self.cars = {c.id: c for c in cars}

    def get_by_ids(self, ids):
        return {i: self.cars[i] for i in ids if i in self.cars}


def service(times_by_car, cars=None):
    ids = list(times_by_car)
    return AssistantService(FakeRaces(times_by_car),
                            FakeCars(cars or [fake_car(i) for i in ids]))


def test_beat_count_and_delta_vs_opponent():
    s = service({501: [19000, 19100, 20000, 21000]})  # avg 19775
    [v] = s.suggestions_vs(track_id=1, opponent_time=19950)
    assert v.beat_count == 2      # 19000 і 19100 швидші за 19950
    assert v.sample_count == 4
    assert v.avg_time == 19775
    assert v.delta == 175          # 19950 - 19775 > 0: я в середньому швидший
    assert abs(v.p_smoothed - (2 + 1) / (4 + 2)) < 1e-9


def test_sorted_by_p_then_delta():
    s = service({
        501: [19000] * 10,   # 10/10 швидші, p̂ = 11/12
        502: [19000] * 2,    # 2/2 швидші, p̂ = 3/4 — менше за 9/10 попри "100%"
        503: [30000] * 10,   # 0/10
    })
    result = s.suggestions_vs(1, opponent_time=20000)
    assert [v.car_id for v in result] == [501, 502, 503]


def test_no_opponent_time_sorted_by_favorite_then_avg():
    cars = [fake_car(501), fake_car(502, favorite=True), fake_car(503)]
    s = service({501: [19000], 502: [25000], 503: [18000]}, cars)
    result = s.suggestions_vs(1, opponent_time=None)
    assert [v.car_id for v in result] == [502, 503, 501]  # favorite перший, далі avg
    assert all(v.p_smoothed == 0.5 and v.delta == 0 and v.beat_count == 0 for v in result)


def test_empty_track_gives_empty_list():
    assert service({}).suggestions_vs(1, 20000) == []
```

- [ ] **Step 2: Переконатися, що падають**

Run: `python -m pytest tests/test_assistant.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Реалізація**

У `RacesRepository` (races.py, після `get_car_stats_for_track`):

```python
    def get_recent_clean_times_by_car(self, track_id: int, limit: int = 10) -> dict[int, list[int]]:
        """car_id → часи останніх `limit` ЧИСТИХ (без 👎) заїздів авто на треку.
        Та сама вибірка, що й у avg_recent агрегатів — для підбору проти суперника."""
        with connect() as conn:
            sql = """
            WITH ranked AS (
                SELECT car_id, time,
                       ROW_NUMBER() OVER (PARTITION BY car_id ORDER BY created_at DESC) AS rn
                FROM races
                WHERE track_id = :track_id AND car_id > 0 AND time > 0 AND bad_timing = 0
            )
            SELECT car_id, time FROM ranked WHERE rn <= :limit
            """
            rows = conn.execute(sql, {"track_id": track_id, "limit": limit}).fetchall()
            times: dict[int, list[int]] = {}
            for row in rows:
                times.setdefault(row["car_id"], []).append(row["time"])
            return times
```

У `RacesService`:

```python
    def get_recent_clean_times_by_car(self, track_id: int, limit: int = 10) -> dict[int, list[int]]:
        return self.repo.get_recent_clean_times_by_car(track_id, limit)
```

Створити `alu_gauntlet_helper/services/assistant.py`:

```python
from alu_gauntlet_helper.services.races import CarSuggestion


def laplace(wins: int, n: int) -> float:
    """Згладжена ймовірність (wins+1)/(n+2): 2/2 (~0.75) не переважає 9/10 (~0.83)."""
    return (wins + 1) / (n + 2)


class VsSuggestion(CarSuggestion):
    """Пропозиція авто проти конкретного часу суперника."""
    beat_count: int = 0    # скільки з вибірки швидші за суперника (сирі числа для UI)
    sample_count: int = 0  # розмір вибірки (останні ≤10 чистих заїздів)
    delta: int = 0         # opponent_time - avg_time, мс; >0 — я в середньому швидший
    p_smoothed: float = 0.5


class AssistantService:
    """Статистика підбору авто проти суперника. Читає БД через RacesService."""

    def __init__(self, races, cars):
        self.races = races
        self.cars = cars

    def suggestions_vs(self, track_id: int, opponent_time: int | None) -> list[VsSuggestion]:
        times_by_car = self.races.get_recent_clean_times_by_car(track_id)
        if not times_by_car:
            return []
        cars = self.cars.get_by_ids(set(times_by_car))
        result = []
        for car_id, times in times_by_car.items():
            car = cars.get(car_id)
            avg = round(sum(times) / len(times))
            beat = sum(1 for t in times if t < opponent_time) if opponent_time else 0
            result.append(VsSuggestion(
                car_id=car_id,
                car_name=car.name if car else "Unknown Car",
                car_brand=car.brand if car else "",
                car_model=car.model if car else "",
                car_class=car.car_class if car else "",
                car_rank=car.rank if car else 0,
                car_favorite=car.favorite if car else False,
                car_icon=car.icon if car else "",
                avg_time=avg,
                race_count=len(times),
                beat_count=beat,
                sample_count=len(times),
                delta=(opponent_time - avg) if opponent_time else 0,
                p_smoothed=laplace(beat, len(times)) if opponent_time else 0.5,
            ))
        if opponent_time:
            result.sort(key=lambda v: (-v.p_smoothed, -v.delta))
        else:
            result.sort(key=lambda v: (not v.car_favorite, v.avg_time))
        return result
```

- [ ] **Step 4: Тести зелені**

Run: `python -m pytest tests/test_assistant.py -v`
Expected: PASS.

---

### Task 6: Модуль автопідбору (чиста математика)

**Files:**
- Create: `alu_gauntlet_helper/services/opponent_picker.py`
- Test: `tests/test_opponent_picker.py`

**Interfaces:**
- Consumes: нічого з проєкту (чистий модуль).
- Produces (на це спирається Task 7):
  - `class Candidate(NamedTuple): car_id: int; p: float; margin: int`;
  - `prob_at_least(probs: list[float], k: int) -> float` — точна P(≥k успіхів), Пуассон-біноміальний DP;
  - `pick_cars(race_candidates: dict[int, list[Candidate]], pinned: dict[int, int]) -> dict[int, int]` — повне призначення race_number → car_id (включно з pinned); максимізує (P(≥3), сума маржинів) лексикографічно; топ-K кандидатів, K = кількість вільних гонок.

- [ ] **Step 1: Тести, що падають**

Створити `tests/test_opponent_picker.py`:

```python
from itertools import permutations

from alu_gauntlet_helper.services.opponent_picker import Candidate, pick_cars, prob_at_least


def test_prob_at_least_exact_values():
    assert prob_at_least([], 3) == 0.0
    assert prob_at_least([1.0, 1.0, 1.0, 0.0, 0.0], 3) == 1.0
    assert abs(prob_at_least([0.5] * 5, 3) - 0.5) < 1e-9  # симетрія біноміального
    # 4 гонки по 0.5: P(>=3) = (C(4,3)+C(4,4))/16 = 5/16
    assert abs(prob_at_least([0.5] * 4, 3) - 5 / 16) < 1e-9


def test_pick_assigns_distinct_cars():
    shared = [Candidate(1, 0.9, 100), Candidate(2, 0.8, 100), Candidate(3, 0.7, 100)]
    picks = pick_cars({1: shared, 2: shared, 3: shared}, pinned={})
    assert sorted(picks) == [1, 2, 3]
    assert len(set(picks.values())) == 3  # усі авто різні


def test_pick_prefers_reliability_over_one_star_race():
    # авто 1 сильне всюди; жадібний віддав би його гонці 1, але глобально
    # краще як у оптимумі — перевіряємо проти повного перебору
    candidates = {
        1: [Candidate(1, 0.9, 500), Candidate(2, 0.85, 100)],
        2: [Candidate(1, 0.6, 50), Candidate(3, 0.55, 40)],
        3: [Candidate(1, 0.95, 300), Candidate(4, 0.5, 10)],
    }
    picks = pick_cars(candidates, pinned={})
    # оптимум у цьому кейсі єдиний — можна порівняти призначення напряму
    assert picks == brute_force(candidates)[0]


def score_of(race_candidates, assignment):
    """(P(≥3), сума маржинів) призначення — та сама ціль, що й у pick_cars."""
    chosen = [next(c for c in race_candidates[r] if c.car_id == car_id)
              for r, car_id in assignment.items()]
    return (prob_at_least([c.p for c in chosen], 3), sum(c.margin for c in chosen))


def brute_force(race_candidates):
    races = sorted(race_candidates)
    best, best_score = None, (-1.0, float("-inf"))
    pools = [race_candidates[r] for r in races]
    def rec(i, used, acc):
        nonlocal best, best_score
        if i == len(races):
            probs = [c.p for c in acc]
            score = (prob_at_least(probs, 3), sum(c.margin for c in acc))
            if score > best_score:
                best_score, best = score, {r: c.car_id for r, c in zip(races, acc)}
            return
        for c in pools[i]:
            if c.car_id not in used:
                rec(i + 1, used | {c.car_id}, acc + [c])
    rec(0, set(), [])
    return best, best_score


def test_pick_matches_brute_force_on_dense_case():
    # 5 гонок × 6 спільних авто з різними p/margin — топ-K не має губити оптимум.
    # Порівнюємо СКОРИ, а не словники: оптимумів з однаковим скором може бути кілька.
    cars = range(1, 7)
    candidates = {
        r: [Candidate(c, ((c * 7 + r * 3) % 10) / 10 + 0.05, (c * 13 + r * 5) % 200)
            for c in cars]
        for r in range(1, 6)
    }
    picks = pick_cars(candidates, pinned={})
    _, best_score = brute_force(candidates)
    got_p, got_margin = score_of(candidates, picks)
    assert abs(got_p - best_score[0]) < 1e-9
    assert got_margin == best_score[1]


def test_pinned_car_excluded_from_other_races():
    shared = [Candidate(1, 0.9, 100), Candidate(2, 0.8, 90), Candidate(3, 0.7, 80)]
    picks = pick_cars({1: shared, 2: shared, 3: shared}, pinned={2: 1})
    assert picks[2] == 1
    assert picks[1] != 1 and picks[3] != 1


def test_race_without_free_candidates_left_unassigned():
    picks = pick_cars({1: [Candidate(1, 0.9, 10)], 2: [Candidate(1, 0.9, 10)]}, pinned={})
    # авто одне на двох — одна гонка лишається без призначення
    assert len(picks) == 1


def test_tie_break_by_margin_sum():
    candidates = {
        1: [Candidate(1, 0.8, 10), Candidate(2, 0.8, 500)],
        2: [Candidate(1, 0.8, 500), Candidate(2, 0.8, 10)],
    }
    picks = pick_cars(candidates, pinned={})
    assert picks == {1: 2, 2: 1}  # однакове P, але сума маржинів 1000 > 20
```

- [ ] **Step 2: Переконатися, що падають**

Run: `python -m pytest tests/test_opponent_picker.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Реалізація**

Створити `alu_gauntlet_helper/services/opponent_picker.py`:

```python
"""Чиста математика автопідбору авто проти суперника (перемога = ≥3 гонки з 5).

Обґрунтування K = кількості вільних гонок (аргумент обміну): інші N-1 гонок
займають щонайбільше N-1 авто з топ-N будь-якої гонки, тож завжди лишається
вільний кандидат не гірший за будь-якого поза топ-N; P(≥3) монотонна по
кожному p окремо, тому обмін не погіршує рішення. Умова коректності:
кандидати ранжуються ТИМ САМИМ ключем (p ↓, margin ↓), що й цільова функція.
"""
from typing import NamedTuple

WINS_NEEDED = 3


class Candidate(NamedTuple):
    car_id: int
    p: float    # згладжена ймовірність побити час суперника (0.5 = невідомо)
    margin: int  # запас, мс: opponent_time - avg_recent (або -avg без часу суперника)


def prob_at_least(probs: list[float], k: int) -> float:
    """Точна P(≥k успіхів) незалежних подій — Пуассон-біноміальний DP."""
    dist = [1.0]  # dist[j] = P(рівно j успіхів серед оброблених)
    for p in probs:
        nxt = [0.0] * (len(dist) + 1)
        for j, q in enumerate(dist):
            nxt[j] += q * (1 - p)
            nxt[j + 1] += q * p
        dist = nxt
    return sum(dist[k:]) if k < len(dist) else 0.0


def pick_cars(race_candidates: dict[int, list[Candidate]],
              pinned: dict[int, int]) -> dict[int, int]:
    """Оптимальне призначення різних авто на гонки.

    race_candidates — лише гонки, де є що обирати (може бути < 5).
    pinned {race_number: car_id} — зафіксовані вручну: входять у відповідь
    як є, їхні авто виключаються з пулів інших гонок.
    Ціль: max (P(≥3 перемог), сума маржинів) лексикографічно."""
    pinned_cars = set(pinned.values())
    free_races = [r for r in sorted(race_candidates) if r not in pinned]

    k = max(1, len(free_races))
    pools = {}
    for r in free_races:
        pool = [c for c in race_candidates[r] if c.car_id not in pinned_cars]
        pool.sort(key=lambda c: (-c.p, -c.margin))
        pools[r] = pool[:k]

    # внесок запінених гонок у ймовірність: p їхнього авто (0.5, як невідомо)
    base_probs = []
    for r, car_id in pinned.items():
        cand = next((c for c in race_candidates.get(r, []) if c.car_id == car_id), None)
        base_probs.append(cand.p if cand else 0.5)

    best_score = (-1.0, float("-inf"))
    best_picks: dict[int, int] = {}

    def dfs(idx: int, used: set, picks: dict, probs: list, margin_sum: int):
        nonlocal best_score, best_picks
        if idx == len(free_races):
            score = (prob_at_least(base_probs + probs, WINS_NEEDED), margin_sum)
            if score > best_score:
                best_score, best_picks = score, dict(picks)
            return
        r = free_races[idx]
        options = [c for c in pools[r] if c.car_id not in used]
        if not options:  # всі кандидати розібрані — гонка без призначення
            dfs(idx + 1, used, picks, probs + [0.5], margin_sum)
            return
        for c in options:
            used.add(c.car_id)
            picks[r] = c.car_id
            dfs(idx + 1, used, picks, probs + [c.p], margin_sum + c.margin)
            del picks[r]
            used.discard(c.car_id)

    dfs(0, set(), {}, [], 0)
    return {**pinned, **best_picks}
```

- [ ] **Step 4: Тести зелені**

Run: `python -m pytest tests/test_opponent_picker.py -v`
Expected: PASS. Якщо `test_pick_matches_brute_force_on_dense_case` падає — звір ранжування пулів з ключем цілі (мають збігатися) і що `options` без кандидатів дає гілку `0.5`.

---

### Task 7: AssistantService.auto_pick і win_chance

**Files:**
- Modify: `alu_gauntlet_helper/services/assistant.py`
- Test: `tests/test_assistant.py`

**Interfaces:**
- Consumes: `pick_cars`, `Candidate`, `prob_at_least`, `laplace` (Task 5–6); `ChallengeSessionService.effective/set_assignments/clear_pins/pinned_races` (Task 1–2).
- Produces (на це спираються Task 4-wiring у Task 8 і UI Task 10):
  - `AssistantService.auto_pick(session, force: bool = False) -> None` — будує кандидатів по гонках з відомим треком і кличе `session.set_assignments`; авто-режим (force=False) нічого не робить, якщо є ручні піни; force=True знімає піни і перепризначає все;
  - `AssistantService.win_chance(session) -> float | None` — P(≥3) за закріпленими авто; None, якщо в сесії немає жодного часу суперника;
  - `AssistantService.beat_stats(track_id: int, car_id: int, opponent_time: int) -> tuple[int, int] | None` — (beat_count, sample_count) для бейджа «7/10» на картці гонки.

- [ ] **Step 1: Тести, що падають**

Додати в `tests/test_assistant.py`:

```python
from alu_gauntlet_helper.models import FieldGuess, RaceCapture, RecognitionResult
from alu_gauntlet_helper.services.challenge_session import ChallengeSessionService


def session_with(*captures):
    s = ChallengeSessionService()
    s.apply(RecognitionResult(screen="test", captures=list(captures)))
    return s


def race(n, track_id, opp_time=None):
    return RaceCapture(race_number=n,
                       track=FieldGuess(value=track_id, score=0.9),
                       opponent_time=opp_time)


class TrackAwareFakeRaces:
    """Різні треки — різні вибірки: {track_id: {car_id: [times]}}."""
    def __init__(self, by_track):
        self.by_track = by_track

    def get_recent_clean_times_by_car(self, track_id, limit=10):
        return self.by_track.get(track_id, {})


def track_service(by_track):
    ids = {c for cars in by_track.values() for c in cars}
    return AssistantService(TrackAwareFakeRaces(by_track),
                            FakeCars([fake_car(i) for i in ids]))


def test_auto_pick_assigns_unpinned():
    svc = track_service({
        7: {501: [19000] * 10, 502: [30000] * 10},
        8: {501: [19000] * 10, 502: [20000] * 10},
    })
    s = session_with(race(1, 7, opp_time=25000), race(2, 8, opp_time=25000))
    svc.auto_pick(s)
    # обидва авто мають призначення, різні; жодне не запінене
    assert sorted(s.assigned_cars) == [1, 2]
    assert set(s.assigned_cars.values()) == {501, 502}
    assert s.pinned_races == set()


def test_auto_pick_skips_when_pinned_and_not_forced():
    svc = track_service({7: {501: [19000] * 10}})
    s = session_with(race(1, 7, opp_time=25000))
    s.set_assigned(1, 999)  # ручний пін
    svc.auto_pick(s)
    assert s.assigned_cars == {1: 999}  # нічого не змінилось


def test_auto_pick_force_overrides_pins():
    svc = track_service({7: {501: [19000] * 10}})
    s = session_with(race(1, 7, opp_time=25000))
    s.set_assigned(1, 999)
    svc.auto_pick(s, force=True)
    assert s.assigned_cars == {1: 501}
    assert s.pinned_races == set()


def test_auto_pick_without_opponent_time_uses_best_avg():
    svc = track_service({7: {501: [21000] * 5, 502: [19000] * 5}})
    s = session_with(race(1, 7))  # трек є, часу суперника немає
    svc.auto_pick(s)
    assert s.assigned_cars == {1: 502}  # найкращий avg


def test_win_chance_none_without_opponent_times():
    svc = track_service({7: {501: [19000] * 10}})
    s = session_with(race(1, 7))
    assert svc.win_chance(s) is None


def test_win_chance_uses_assigned_cars():
    svc = track_service({7: {501: [19000] * 10}})
    s = session_with(race(1, 7, opp_time=25000))
    svc.auto_pick(s)
    chance = svc.win_chance(s)
    # гонка 1: p̂ = 11/12; гонки 2-5 невідомі (0.5 кожна)
    from alu_gauntlet_helper.services.opponent_picker import prob_at_least
    assert abs(chance - prob_at_least([11 / 12, 0.5, 0.5, 0.5, 0.5], 3)) < 1e-9


def test_beat_stats():
    svc = track_service({7: {501: [19000, 19100, 21000]}})
    assert svc.beat_stats(7, 501, 20000) == (2, 3)
    assert svc.beat_stats(7, 999, 20000) is None
```

- [ ] **Step 2: Переконатися, що падають**

Run: `python -m pytest tests/test_assistant.py -v -k "auto_pick or win_chance or beat_stats"`
Expected: FAIL (`auto_pick` не існує).

- [ ] **Step 3: Реалізація**

В `assistant.py` (додати імпорти вгорі):

```python
from alu_gauntlet_helper.services.challenge_session import RACE_COUNT
from alu_gauntlet_helper.services.opponent_picker import Candidate, pick_cars, prob_at_least
```

Методи `AssistantService`:

```python
    def auto_pick(self, session, force: bool = False):
        """Оптимальне призначення авто на гонки з відомим треком.

        force=False — авто-режим після скану: мовчки виходить, якщо гравець уже
        пінив руками. force=True — кнопка «Авто»: знімає піни й перепризначає все."""
        if session.pinned_races and not force:
            return
        if force:
            session.clear_pins()
        race_candidates: dict[int, list[Candidate]] = {}
        for n in range(1, RACE_COUNT + 1):
            e = session.effective(n)
            if e is None or e.track_id <= 0:
                continue
            opp = e.opponent_time or None
            suggestions = self.suggestions_vs(e.track_id, opp)
            if not suggestions:
                continue
            # без часу суперника p=0.5 для всіх, margin=-avg: топ-K і тай-брейк
            # природно обирають найкращий avg (спека, розділ 5)
            race_candidates[n] = [
                Candidate(v.car_id, v.p_smoothed, v.delta if opp else -v.avg_time)
                for v in suggestions
            ]
        if not race_candidates:
            return
        session.set_assignments(pick_cars(race_candidates, pinned=dict(
            (n, session.assigned_cars[n]) for n in session.pinned_races
            if n in session.assigned_cars)))

    def win_chance(self, session) -> float | None:
        """P(виграти ≥3 з 5) за закріпленими авто. None — немає часів суперника."""
        probs = []
        has_opponent = False
        for n in range(1, RACE_COUNT + 1):
            e = session.effective(n)
            opp = e.opponent_time if e else 0
            car_id = session.assigned_cars.get(n, 0)
            if e and opp and car_id and e.track_id > 0:
                has_opponent = True
                stats = self.beat_stats(e.track_id, car_id, opp)
                probs.append(laplace(*stats) if stats else 0.5)
            else:
                if opp:
                    has_opponent = True
                probs.append(0.5)  # невідома гонка — монетка
        return prob_at_least(probs, 3) if has_opponent else None

    def beat_stats(self, track_id: int, car_id: int, opponent_time: int) -> tuple[int, int] | None:
        """(скільки побито, розмір вибірки) для бейджа «7/10». None — немає заїздів."""
        times = self.races.get_recent_clean_times_by_car(track_id).get(car_id)
        if not times:
            return None
        return sum(1 for t in times if t < opponent_time), len(times)
```

- [ ] **Step 4: Тести зелені**

Run: `python -m pytest tests/test_assistant.py tests/test_opponent_picker.py -v`
Expected: PASS.

---

### Task 8: AppContext і CaptureController переходять на SessionManager

**Files:**
- Modify: `alu_gauntlet_helper/app_context.py`
- Modify: `alu_gauntlet_helper/capture/capture_controller.py`
- Test: наявні тести + ручний запуск

**Interfaces:**
- Consumes: `SessionManager` (Task 4), `AssistantService` (Task 5/7).
- Produces: `APP_CONTEXT.session_manager: SessionManager`, `APP_CONTEXT.assistant: AssistantService`. Атрибут `challenge_session` ВИДАЛЯЄТЬСЯ (щоб не було двох джерел правди); всі споживачі — через `session_manager`. Task 9–10 спираються саме на це.

- [ ] **Step 1: Оновити AppContext**

```python
from alu_gauntlet_helper.services.assistant import AssistantService
from alu_gauntlet_helper.services.session_manager import SessionManager
```

У `AppContext` замінити анотацію і конструкцію `challenge_session` на:

```python
    assistant: AssistantService
    session_manager: SessionManager
```

```python
        self.assistant = AssistantService(self.races_service, self.cars_service)
        self.session_manager = SessionManager(auto_pick=self.assistant.auto_pick)
```

(рядок `self.challenge_session = ChallengeSessionService()` та імпорт `ChallengeSessionService` видалити).

- [ ] **Step 2: Оновити CaptureController**

Всі звернення `APP_CONTEXT.challenge_session` замінити:

- `__init__`: `self.overlay.dislike_toggled.connect(self._toggle_bad_timing)` (новий метод нижче) та `APP_CONTEXT.session_manager.add_listener(self._refresh_overlay)`;
- `shutdown`: `APP_CONTEXT.session_manager.remove_listener(self._refresh_overlay)`;
- `_on_recognized`: `APP_CONTEXT.session_manager.apply(result)`;
- `_refresh_overlay`: `session = APP_CONTEXT.session_manager.active`;
- новий метод (👎 з оверлея завжди стосується активної сесії):

```python
    @staticmethod
    def _toggle_bad_timing(race_number: int):
        APP_CONTEXT.session_manager.active.toggle_bad_timing(race_number)
```

- у `_is_uncertain` додати перевірку авто суперника (щоб непевні скани зберігались для рев'ю):

```python
            if c.opponent_car and c.opponent_car.score < LOW_CONFIDENCE:
                return True
```

- [ ] **Step 3: Тимчасовий міст для старого CaptureTab**

`views/capture_tab.py` ще звертається до `APP_CONTEXT.challenge_session` (3 місця: `add_listener` у `__init__`, `_effective_map`, `open_edit`/`save_selected`/`discard`). До Task 10 (заміна таба) зробити мінімальну правку, щоб застосунок лишався робочим: замінити в `capture_tab.py` всі `APP_CONTEXT.challenge_session` на `APP_CONTEXT.session_manager.active`, а `add_listener/…` — на `APP_CONTEXT.session_manager.add_listener(self.refresh)`; у `save_selected` замість `session.clear()` — `APP_CONTEXT.session_manager.close(session)` (session взяти в змінну на початку методу), у `discard` так само.

- [ ] **Step 4: Перевірка**

Run: `python -m pytest tests -v --ignore=tests/test_challenge_accordion.py -q` (повний прогін швидких тестів)
Expected: PASS (провалів через відсутній `challenge_session` немає).

Ручний запуск: `python main.py` → вкладка ASSISTANT працює як раніше: «Load screenshot» з `tests/fixtures/accordion_before_1.png` наповнює рядок гонки 1 (трек), оверлей оновлюється, Discard чистить.

---

### Task 9: Віджети — картка гонки і пропозиція «проти суперника»

**Files:**
- Create: `alu_gauntlet_helper/views/components/race_card.py`
- Create: `alu_gauntlet_helper/views/components/vs_suggestion.py`
- Modify: `alu_gauntlet_helper/ui_lang.py` (нові ключі, en + uk)
- Test: ручна перевірка в Task 10 (Qt-віджети в проєкті юніт-тестами не покриваються)

**Interfaces:**
- Consumes: `EffectiveRace` (Task 1), `VsSuggestion` (Task 5), `TrackView`, `Car`, `style`, `load_pixmap_cover`, `format_time`.
- Produces (використовує Task 10):
  - `RaceCard(race_number)` з сигналом `clicked = pyqtSignal(int)` і методом `update_card(e: EffectiveRace | None, track: TrackView | None, car, beat: tuple[int, int] | None, selected: bool)` (`car` — обʼєкт Car закріпленого авто або None);
  - `VsSuggestionWidget(item: VsSuggestion, track_id: int)` — рядок списку пропозицій; атрибути `car_id`, методи `set_dimmed(bool)`, `set_assigned_here(bool)`;
  - хелпер `format_delta(ms: int) -> str` у `vs_suggestion.py` (напр. `+0.175s` / `−1.204s`).

- [ ] **Step 1: Ключі перекладу**

У `ui_lang.TRANSLATIONS["en"]` (секцію нових ключів додати поряд з capture.*):

```python
        # assistant (opponent picker)
        "assistant.race_n": "Race {n}",
        "assistant.no_track": "Track?",
        "assistant.beat_target": "beat {time}",
        "assistant.no_car_assigned": "pick a car",
        "assistant.beaten": "{wins}/{n} beaten",
        "assistant.auto_pick": "Auto",
        "assistant.win_chance": "Win chance ~{pct}%",
        "assistant.no_suggestions": "No runs on this track yet",
        "assistant.no_track_selected": "Track unknown — scan the accordion",
        "assistant.session_current": "▶ current",
        "assistant.session_paused": "⏸ {time} · {n}",
```

У `TRANSLATIONS["uk"]`:

```python
        # асистент (підбір проти суперника)
        "assistant.race_n": "Гонка {n}",
        "assistant.no_track": "Трек?",
        "assistant.beat_target": "побити {time}",
        "assistant.no_car_assigned": "оберіть авто",
        "assistant.beaten": "{wins}/{n} побито",
        "assistant.auto_pick": "Авто",
        "assistant.win_chance": "Шанс перемоги ~{pct}%",
        "assistant.no_suggestions": "На цьому треку ще немає заїздів",
        "assistant.no_track_selected": "Трек невідомий — відскануй акордеон",
        "assistant.session_current": "▶ поточна",
        "assistant.session_paused": "⏸ {time} · {n}",
```

Run: `python -m pytest tests/test_ui_lang.py -v` → PASS (тест паритету ключів мов, якщо він є, має пройти).

- [ ] **Step 2: RaceCard**

Створити `alu_gauntlet_helper/views/components/race_card.py`:

```python
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from alu_gauntlet_helper import ui_lang
from alu_gauntlet_helper.utils.utils import format_time, load_pixmap_cover
from alu_gauntlet_helper.views import style

CARD_BORDER_SELECTED = style.ACCENT if hasattr(style, "ACCENT") else "#FFC107"


class RaceCard(QFrame):
    """Клікабельна картка гонки в ряду з 5: трек, час суперника, закріплене авто,
    «7/10». Всі 5 видно завжди — з будь-якої гонки видно вибір у решті."""

    clicked = pyqtSignal(int)

    def __init__(self, race_number: int, parent=None):
        super().__init__(parent)
        self.race_number = race_number
        self.setObjectName("raceCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(150)

        self.title_label = QLabel(ui_lang.t("assistant.race_n").format(n=race_number))
        title_font = QFont()
        title_font.setBold(True)
        self.title_label.setFont(title_font)

        self.map_icon = QLabel()
        self.map_icon.setFixedSize(28, 28)

        self.track_label = QLabel(ui_lang.t("assistant.no_track"))
        self.track_label.setWordWrap(True)

        self.opponent_label = QLabel("")  # "побити 00:19.152"
        self.opponent_label.setStyleSheet(f"color: {style.TEXT_MUTED}; font-size: 11px;")

        self.car_label = QLabel(ui_lang.t("assistant.no_car_assigned"))
        self.car_label.setStyleSheet(f"color: {style.TEXT_MUTED};")
        self.car_label.setWordWrap(True)

        self.beat_label = QLabel("")  # "7/10 побито"
        self.beat_label.setStyleSheet("font-size: 11px;")

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(self.map_icon)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        layout.addLayout(header)
        layout.addWidget(self.track_label)
        layout.addWidget(self.opponent_label)
        layout.addWidget(self.car_label)
        layout.addWidget(self.beat_label)
        layout.addStretch()

    def mousePressEvent(self, event):
        self.clicked.emit(self.race_number)
        super().mousePressEvent(event)

    def update_card(self, e, track, car, beat, selected: bool):
        """e: EffectiveRace | None; track: TrackView | None; car: Car закріпленого
        авто | None; beat: (wins, n) | None; selected — чи це відкрита панель."""
        if track is not None:
            self.track_label.setText(f"{track.display_map_name} · {track.display_name}")
            pixmap = load_pixmap_cover(track.map_icon, w=28, h=28) if track.map_icon else None
            if pixmap:
                self.map_icon.setPixmap(pixmap)
            else:
                self.map_icon.clear()
        else:
            self.track_label.setText(ui_lang.t("assistant.no_track"))
            self.map_icon.clear()

        opp = e.opponent_time if e else 0
        self.opponent_label.setText(
            ui_lang.t("assistant.beat_target").format(time=format_time(opp)) if opp else "")

        if car is not None:
            self.car_label.setText(car.model or car.name)
            self.car_label.setStyleSheet("")
        else:
            self.car_label.setText(ui_lang.t("assistant.no_car_assigned"))
            self.car_label.setStyleSheet(f"color: {style.TEXT_MUTED};")

        self.beat_label.setText(
            ui_lang.t("assistant.beaten").format(wins=beat[0], n=beat[1]) if beat else "")

        # мій час уже є — гонка зіграна, підсвічуємо заголовок зеленим (як оверлей)
        played = e is not None and e.time > 0
        self.title_label.setStyleSheet("color: #4CAF50;" if played else "")

        border = CARD_BORDER_SELECTED if selected else "transparent"
        self.setStyleSheet(f"QFrame#raceCard {{ border: 1px solid {border}; border-radius: 6px; }}")
```

(Хелпер `load_pixmap_cover` повертає `QPixmap | None` — див. використання в `car_selection_tab.py`.)
Перед реалізацією звір константи кольорів зі `style.py` (наприклад, точну назву акцентної константи — якщо `ACCENT` немає, взяти жовтий `#FFC107`, як `WARN_ICON` у capture_tab).

- [ ] **Step 3: VsSuggestionWidget**

Створити `alu_gauntlet_helper/views/components/vs_suggestion.py` — копія структури `CarSuggestionWidget` з `car_selection_tab.py` з додатковими показниками (не успадковуємо, бо правий блок інший):

```python
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from alu_gauntlet_helper import ui_lang
from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.assistant import VsSuggestion
from alu_gauntlet_helper.utils.utils import format_time, load_pixmap_cover
from alu_gauntlet_helper.views import style
from alu_gauntlet_helper.views.components.common import ListItemWidget


def format_delta(ms: int) -> str:
    """Δ між часом суперника і моїм avg: +0.175s — я швидший, −1.204s — повільніший."""
    sign = "+" if ms >= 0 else "−"
    return f"{sign}{abs(ms) / 1000:.3f}s"


class VsSuggestionWidget(ListItemWidget):
    """Рядок пропозиції авто проти суперника: авто + avg + «7/10 побито» + Δ."""

    def __init__(self, item: VsSuggestion, track_id: int, has_opponent_time: bool, parent=None):
        super().__init__(item, parent)
        self.car_id = item.car_id
        self.car_name = item.car_name
        self.track_id = track_id

        self.car_icon = QLabel()
        self.car_icon.setFixedSize(96, 48)
        self.car_icon.setStyleSheet("background-color: #271A62;")
        self.car_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if item.car_icon:
            pixmap = load_pixmap_cover(item.car_icon, w=96, h=48)
            if pixmap:
                self.car_icon.setPixmap(pixmap)

        self.brand_label = QLabel(item.car_brand)
        self.brand_label.setStyleSheet(f"color: {style.TEXT_MUTED}; font-size: 11px;")
        if not item.car_brand:
            self.brand_label.hide()

        self.car_label = QLabel(item.car_model or item.car_name)
        self.car_label.setWordWrap(True)

        rank_parts = []
        if item.car_favorite:
            rank_parts.append("♥")
        if item.car_class:
            rank_parts.append(ui_lang.t("car_selection.class_x").format(c=item.car_class))
        if item.car_rank:
            rank_parts.append(ui_lang.t("car_selection.rank_label").format(n=item.car_rank))
        self.rank_label = QLabel(" · ".join(rank_parts))
        self.rank_label.setStyleSheet(f"color: {style.TEXT_MUTED}; font-size: 12px;")

        self.time_label = QLabel(format_time(item.avg_time))
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        if has_opponent_time:
            beaten = ui_lang.t("assistant.beaten").format(wins=item.beat_count, n=item.sample_count)
            delta_color = "#4CAF50" if item.delta >= 0 else "#F44336"
            self.vs_label = QLabel(f"{beaten} · <span style='color:{delta_color};'>{format_delta(item.delta)}</span>")
            self.vs_label.setTextFormat(Qt.TextFormat.RichText)
        else:
            self.vs_label = QLabel(ui_lang.t("car_selection.races_count").format(n=item.race_count))
            self.vs_label.setStyleSheet(f"color: {style.TEXT_MUTED};")
        self.vs_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(0)
        left.addWidget(self.brand_label)
        left.addWidget(self.car_label)
        left.addWidget(self.rank_label)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        right.addWidget(self.time_label)
        right.addWidget(self.vs_label)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.setSpacing(4)
        self.layout.addWidget(self.car_icon)
        self.layout.addLayout(left, stretch=1)
        self.layout.addLayout(right)
        self.setLayout(self.layout)

    def set_dimmed(self, dimmed: bool):
        for w in (self.brand_label, self.car_label, self.rank_label,
                  self.time_label, self.vs_label, self.car_icon):
            w.setEnabled(not dimmed)

    def set_assigned_here(self, assigned: bool):
        # виділення закріпленого авто робиться селекцією item-а списку (як у
        # car_selection_tab.update_dimming) — метод лишається для явності виклику
        pass
```

Якщо `set_assigned_here` виявиться справді порожнім у Task 10 — видалити його і виділяти через `item.setSelected(...)`, як у `car_selection_tab.py:232`.

- [ ] **Step 4: Швидка перевірка імпортів**

Run: `python -c "from alu_gauntlet_helper.views.components.race_card import RaceCard; from alu_gauntlet_helper.views.components.vs_suggestion import VsSuggestionWidget, format_delta; print(format_delta(175), format_delta(-1204))"`
Expected: `+0.175s −1.204s` (без ImportError; інстанціювати без QApplication не треба).

---

### Task 10: AssistantTab — збирання, MainWindow, видалення старого CaptureTab

**Files:**
- Create: `alu_gauntlet_helper/views/assistant_tab.py`
- Modify: `alu_gauntlet_helper/views/capture_tab.py` (видалити клас `CaptureTab`, лишити `CaptureRaceRow` і `WARN_ICON`)
- Modify: `alu_gauntlet_helper/views/main_window.py`
- Test: повний прогін тестів + ручний сценарій

**Interfaces:**
- Consumes: все з Task 1–9.
- Produces: `AssistantTab(recognize_file, toggle_overlay, capture, cancel_pending)` з сигналом `save_state_changed = pyqtSignal(bool)` і методами `set_status(str)`, `set_busy(bool)`, `save_selected()` — той самий контракт, що мав `CaptureTab` (MainWindow міняє лише імпорт/клас).

- [ ] **Step 1: SessionView і AssistantTab**

Створити `alu_gauntlet_helper/views/assistant_tab.py`:

```python
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QAbstractItemView, QFileDialog, QHBoxLayout, QLabel,
                             QListWidget, QListWidgetItem, QMessageBox, QPushButton,
                             QStackedWidget, QTabBar, QVBoxLayout, QWidget)

from alu_gauntlet_helper import ui_lang
from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.challenge_session import (RACE_COUNT, ChallengeSessionService,
                                                            EffectiveRace)
from alu_gauntlet_helper.services.races import RaceView
from alu_gauntlet_helper.views.capture_tab import WARN_ICON, CaptureRaceRow
from alu_gauntlet_helper.views import style
from alu_gauntlet_helper.views.components.race_card import RaceCard
from alu_gauntlet_helper.views.components.vs_suggestion import VsSuggestionWidget
from alu_gauntlet_helper.views.overlay import Spinner
from alu_gauntlet_helper.views.races_tab import RaceDialog


class SessionView(QWidget):
    """Одна сесія челенджа: ряд з 5 карток гонок + панель вибраної гонки
    (пропозиції авто проти суперника + мій захоплений результат) + низ
    (шанс перемоги, Авто, Save/Discard)."""

    save_state_changed = pyqtSignal(bool)

    def __init__(self, session: ChallengeSessionService, cancel_pending=None, parent=None):
        super().__init__(parent)
        self.session = session
        self._cancel_pending = cancel_pending
        self.selected_race = 1
        self.manual_checks: dict[int, bool] = {}
        self._busy = False

        # --- ряд карток гонок ---
        self.cards = [RaceCard(n) for n in range(1, RACE_COUNT + 1)]
        cards_row = QHBoxLayout()
        cards_row.setSpacing(6)
        for card in self.cards:
            card.clicked.connect(self.select_race)
            cards_row.addWidget(card, stretch=1)

        # --- панель вибраної гонки ---
        self.suggestions = QListWidget()
        self.suggestions.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.suggestions.itemClicked.connect(self.on_suggestion_clicked)

        self.captured_row = QListWidget()  # 0..1 рядок CaptureRaceRow вибраної гонки
        self.captured_row.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.captured_row.setFixedHeight(64)
        self.captured_row.hide()

        # --- низ ---
        self.win_chance_label = QLabel("")
        self.warning_label = QLabel()
        self.warning_label.setTextFormat(Qt.TextFormat.RichText)
        self.warning_label.setWordWrap(True)
        self.warning_label.setVisible(False)

        self.auto_button = QPushButton(ui_lang.t("assistant.auto_pick"))
        self.auto_button.setObjectName("secondary")
        self.auto_button.clicked.connect(self.auto_pick)
        self.save_button = QPushButton(ui_lang.t("capture.save_selected"))
        self.save_button.clicked.connect(self.save_selected)
        self.discard_button = QPushButton(ui_lang.t("capture.discard_session"))
        self.discard_button.setObjectName("secondary")
        self.discard_button.clicked.connect(self.discard)

        bottom = QHBoxLayout()
        bottom.addWidget(self.warning_label, stretch=1)
        bottom.addWidget(self.win_chance_label)
        bottom.addStretch()
        bottom.addWidget(self.auto_button)
        bottom.addWidget(self.save_button)
        bottom.addWidget(self.discard_button)

        layout = QVBoxLayout(self)
        layout.addLayout(cards_row)
        layout.addWidget(self.suggestions, stretch=1)
        layout.addWidget(self.captured_row)
        layout.addLayout(bottom)

        self.refresh()

    # --- дані ---------------------------------------------------------------

    def _effective_map(self) -> dict[int, EffectiveRace]:
        return {n: e for n in range(1, RACE_COUNT + 1)
                if (e := self.session.effective(n)) is not None}

    def set_busy(self, busy: bool):
        self._busy = busy
        self._update_buttons(self._effective_map())

    def refresh(self):
        effective = self._effective_map()
        if not effective:
            self.manual_checks = {}

        track_ids = {e.track_id for e in effective.values() if e.track_id}
        cars_ids = set(self.session.assigned_cars.values()) | {
            e.car_id for e in effective.values() if e.car_id}
        tracks = APP_CONTEXT.tracks_service.get_by_ids(track_ids)
        cars = APP_CONTEXT.cars_service.get_by_ids(cars_ids)

        for card in self.cards:
            n = card.race_number
            e = effective.get(n)
            track = tracks.get(e.track_id) if e and e.track_id else None
            assigned = self.session.assigned_cars.get(n)
            car = cars.get(assigned) if assigned else None
            beat = None
            if e and e.track_id and assigned and e.opponent_time:
                beat = APP_CONTEXT.assistant.beat_stats(e.track_id, assigned, e.opponent_time)
            card.update_card(e, track, car, beat, selected=(n == self.selected_race))

        self._refresh_suggestions(effective)
        self._refresh_captured_row(effective, tracks, cars)

        chance = APP_CONTEXT.assistant.win_chance(self.session)
        self.win_chance_label.setText(
            ui_lang.t("assistant.win_chance").format(pct=round(chance * 100)) if chance is not None else "")

        has_uncertain = any(e.track_uncertain or e.car_uncertain for e in effective.values())
        self.warning_label.setText(
            (WARN_ICON + ui_lang.t("capture.low_conf_warning")) if has_uncertain else "")
        self.warning_label.setVisible(has_uncertain)
        self._update_buttons(effective)

    def _refresh_suggestions(self, effective):
        self.suggestions.clear()
        e = effective.get(self.selected_race)
        if e is None or e.track_id <= 0:
            self._show_status(ui_lang.t("assistant.no_track_selected"))
            return
        opp = e.opponent_time or None
        items = APP_CONTEXT.assistant.suggestions_vs(e.track_id, opp)
        if not items:
            self._show_status(ui_lang.t("assistant.no_suggestions"))
            return
        assigned = self.session.assigned_cars
        for item in items:
            w = VsSuggestionWidget(item, e.track_id, has_opponent_time=bool(opp))
            w.add_to_list(self.suggestions)
            in_other = item.car_id in assigned.values() and assigned.get(self.selected_race) != item.car_id
            w.set_dimmed(in_other)
        # виділити закріплене за ЦІЄЮ гонкою авто селекцією item-а
        current = assigned.get(self.selected_race)
        for i in range(self.suggestions.count()):
            widget = self.suggestions.itemWidget(self.suggestions.item(i))
            if isinstance(widget, VsSuggestionWidget):
                self.suggestions.item(i).setSelected(widget.car_id == current)

    def _show_status(self, text: str):
        item = QListWidgetItem()
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        label = QLabel(text)
        label.setStyleSheet(f"color: {style.TEXT_MUTED};")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setContentsMargins(8, 16, 8, 16)
        item.setSizeHint(label.sizeHint())
        self.suggestions.addItem(item)
        self.suggestions.setItemWidget(item, label)

    def _refresh_captured_row(self, effective, tracks, cars):
        self.captured_row.clear()
        e = effective.get(self.selected_race)
        if e is None or not (e.time or e.rank or e.car_id):
            self.captured_row.hide()
            return
        track = tracks.get(e.track_id) if e.track_id else None
        car = cars.get(e.car_id) if e.car_id else None
        row = CaptureRaceRow(self.selected_race, e, track, car,
                             self._is_checked(self.selected_race, e),
                             self.on_checkbox_toggled, self.open_edit)
        row.add_to_list(self.captured_row)
        self.captured_row.show()

    # --- дії ----------------------------------------------------------------

    def select_race(self, n: int):
        self.selected_race = n
        self.refresh()

    def on_suggestion_clicked(self, item: QListWidgetItem):
        widget = self.suggestions.itemWidget(item)
        if not isinstance(widget, VsSuggestionWidget):
            return
        current = self.session.assigned_cars.get(self.selected_race)
        # повторний клік — зняти; клік по чужому/вільному — закріпити тут
        self.session.set_assigned(self.selected_race,
                                  None if widget.car_id == current else widget.car_id)

    def auto_pick(self):
        APP_CONTEXT.assistant.auto_pick(self.session, force=True)

    def _is_checked(self, n: int, e: EffectiveRace | None) -> bool:
        if e is None:
            return False
        if n in self.manual_checks:
            return self.manual_checks[n]
        return e.time > 0

    def on_checkbox_toggled(self, n: int, checked: bool):
        self.manual_checks[n] = checked
        self._update_buttons(self._effective_map())

    def _update_buttons(self, effective):
        any_checked = False
        all_checked_complete = True
        for n in range(1, RACE_COUNT + 1):
            e = effective.get(n)
            if self._is_checked(n, e):
                any_checked = True
                if e is None or not e.is_complete:
                    all_checked_complete = False
        self.save_button.setEnabled(any_checked and all_checked_complete)
        self.save_state_changed.emit(self.save_button.isEnabled())
        self.discard_button.setEnabled(bool(effective) or self._busy)

    def open_edit(self, n: int):
        e = self.session.effective(n)
        item = self._to_race_view(e) if e else RaceView()
        dialog = RaceDialog(item=item,
                            action=lambda r: self.session.set_draft(n, r),
                            parent=self, relaxed=True,
                            title=ui_lang.t("capture.edit_race_n").format(n=n))
        if e and e.car_id:
            car = APP_CONTEXT.cars_service.get_by_ids({e.car_id}).get(e.car_id)
            if car:
                dialog.cars_completer.set_selected_item(car)
        dialog.exec()

    @staticmethod
    def _to_race_view(e: EffectiveRace) -> RaceView:
        track = APP_CONTEXT.tracks_service.get_by_ids({e.track_id}).get(e.track_id) if e.track_id else None
        car = APP_CONTEXT.cars_service.get_by_ids({e.car_id}).get(e.car_id) if e.car_id else None
        return RaceView(
            track_id=e.track_id, car_id=e.car_id, rank=e.rank, time=e.time,
            bad_timing=e.bad_timing, note=e.note,
            map_name=track.map_name if track else "",
            map_name_ru=track.map_name_ru if track else "",
            track_name=track.name if track else "",
            track_name_ru=track.name_ru if track else "",
            car_name=car.name if car else e.car_name,
        )

    def save_selected(self):
        effective = self._effective_map()
        races = [
            RaceView(track_id=e.track_id, car_id=e.car_id, car_name=e.car_name,
                     rank=e.rank, time=e.time, bad_timing=e.bad_timing, note=e.note)
            for n, e in effective.items() if self._is_checked(n, e)
        ]
        try:
            for race in races:
                APP_CONTEXT.races_service.save(race)
        except Exception as ex:
            QMessageBox.critical(self, ui_lang.t("capture.save_failed"), str(ex))
            return
        APP_CONTEXT.session_manager.close(self.session)

    def discard(self):
        box = QMessageBox(QMessageBox.Icon.Question, ui_lang.t("capture.discard_session"),
                          ui_lang.t("capture.discard_confirm"),
                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, self)
        for btn in box.buttons():
            btn.setObjectName("secondary")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        if box.exec() == QMessageBox.StandardButton.Yes:
            if self._cancel_pending and self.session is APP_CONTEXT.session_manager.active:
                self._cancel_pending()
            APP_CONTEXT.session_manager.close(self.session)


class AssistantTab(QWidget):
    """Таб асистента: верхні кнопки захоплення + таби сесій (видимі при >1)
    + SessionView активної/вибраної сесії. Контракт для MainWindow — той самий,
    що був у CaptureTab."""

    save_state_changed = pyqtSignal(bool)

    def __init__(self, recognize_file=None, toggle_overlay=None, capture=None,
                 cancel_pending=None):
        super().__init__()
        self.recognize_file = recognize_file
        self._cancel_pending = cancel_pending

        settings = APP_CONTEXT.settings.get()
        self.load_button = QPushButton(ui_lang.t("capture.load_screenshot"))
        self.load_button.setObjectName("secondary")
        self.load_button.clicked.connect(self.load_screenshot)
        self.capture_button = QPushButton(
            ui_lang.t("capture.capture_screen").format(hotkey=settings.capture_hotkey.upper()))
        if capture:
            self.capture_button.clicked.connect(capture)
        self.overlay_button = QPushButton(
            ui_lang.t("capture.toggle_overlay").format(hotkey=settings.overlay_hotkey.upper()))
        self.overlay_button.setObjectName("secondary")
        if toggle_overlay:
            self.overlay_button.clicked.connect(toggle_overlay)

        self.status_spinner = Spinner()
        self.status_label = QLabel()
        self.status_label.setObjectName("captureStatus")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        top = QHBoxLayout()
        top.addWidget(self.load_button)
        top.addWidget(self.capture_button)
        top.addWidget(self.overlay_button)
        top.addStretch()
        top.addWidget(self.status_spinner)
        top.addWidget(self.status_label)

        self.session_bar = QTabBar()
        self.session_bar.setExpanding(False)
        self.session_bar.currentChanged.connect(self._on_session_tab_changed)
        self.session_bar.hide()
        self.stack = QStackedWidget()
        self._views: list[SessionView] = []

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.session_bar)
        layout.addWidget(self.stack, stretch=1)

        APP_CONTEXT.session_manager.add_listener(self.refresh)
        self.refresh()

    # --- синхронізація зі списком сесій -------------------------------------

    def refresh(self):
        manager = APP_CONTEXT.session_manager
        sessions = manager.sessions
        if [v.session for v in self._views] != sessions:
            self._rebuild_views(sessions)
        for view in self._views:
            view.refresh()
        self._refresh_tab_titles()
        self._emit_save_state()

    def _rebuild_views(self, sessions):
        was = self.stack.currentWidget()
        keep = {id(v.session): v for v in self._views}
        self._views = []
        while self.stack.count():
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            if w.session not in sessions:
                w.deleteLater()
        while self.session_bar.count():
            self.session_bar.removeTab(0)
        for session in sessions:
            view = keep.get(id(session)) or SessionView(session, cancel_pending=self._cancel_pending)
            view.save_state_changed.connect(self._emit_save_state)
            self._views.append(view)
            self.stack.addWidget(view)
            self.session_bar.addTab("")
        self.session_bar.setVisible(len(sessions) > 1)
        # нова активна сесія (остання) стає видимою, якщо стара зникла
        current = was if was in self._views else self._views[-1]
        self.stack.setCurrentWidget(current)
        self.session_bar.setCurrentIndex(self._views.index(current))

    def _refresh_tab_titles(self):
        for i, view in enumerate(self._views):
            s = view.session
            if s is APP_CONTEXT.session_manager.active:
                title = ui_lang.t("assistant.session_current")
            else:
                title = ui_lang.t("assistant.session_paused").format(
                    time=s.created_at.strftime("%H:%M"), n=s.timed_count)
            self.session_bar.setTabText(i, title)

    def _on_session_tab_changed(self, idx: int):
        if 0 <= idx < self.stack.count():
            self.stack.setCurrentIndex(idx)
            self._emit_save_state()

    def _current_view(self) -> SessionView | None:
        w = self.stack.currentWidget()
        return w if isinstance(w, SessionView) else None

    def _emit_save_state(self):
        view = self._current_view()
        self.save_state_changed.emit(bool(view) and view.save_button.isEnabled())

    # --- контракт MainWindow (як у старого CaptureTab) -----------------------

    def set_status(self, status: str):
        if status.startswith("Recognizing"):
            self.status_spinner.start()
        else:
            self.status_spinner.stop()
        self.status_label.setText(status)

    def set_busy(self, busy: bool):
        for view in self._views:
            view.set_busy(busy)

    def save_selected(self):
        view = self._current_view()
        if view:
            view.save_selected()

    def load_screenshot(self):
        path, _ = QFileDialog.getOpenFileName(
            self, ui_lang.t("capture.load_screenshot"), "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path and self.recognize_file:
            self.recognize_file(path)
```

Зауваження до `_rebuild_views`: `w.session` доступний, бо в стеку лише `SessionView`. `removeTab(0)` у циклі тимчасово тригерить `currentChanged` — щоб уникнути смикань, обгорнути перебудову в `self.session_bar.blockSignals(True) / False` (додати на початку і в кінці `_rebuild_views`).

- [ ] **Step 2: Почистити capture_tab.py і підключити MainWindow**

1. У `views/capture_tab.py` видалити клас `CaptureTab` цілком (лишити імпорти, потрібні `CaptureRaceRow`, `WARN_ICON`; зайві імпорти прибрати). `CaptureRaceRow` не чіпати.
2. У `views/main_window.py`:
   - `from alu_gauntlet_helper.views.capture_tab import CaptureTab` → `from alu_gauntlet_helper.views.assistant_tab import AssistantTab`;
   - `self.capture_tab = CaptureTab(...)` → `self.capture_tab = AssistantTab(...)` (аргументи ті самі);
   - решта підключень (`status_changed`, `busy_changed`, `save_requested`, `save_state_changed`) працює без змін — контракт збережено;
   - рядок `self.car_selection_tab = CarSelectionTab()` і закоментований addTab можна не чіпати.

- [ ] **Step 3: Повний прогін тестів**

Run: `python -m pytest tests -v`
Expected: PASS (все, що працювало, працює; нові тести зелені).

- [ ] **Step 4: Ручний сценарій (Definition of Done етапу 1)**

Запустити `python main.py` і пройти сценарій фікстурами через «Load screenshot»:

1. `accordion_before_1.png` → картка гонки 1: трек San Francisco · Railroad Bustle, «побити 00:19.152»; якщо в БД є заїзди на цьому треку — список пропозицій з «N/10 побито» і Δ, автопідбір закріпив авто (видно на картці), знизу «Шанс перемоги ~X%».
2. Клік по іншому авто в списку — воно закріплюється (пін); клік по авто, закріпленому за іншою гонкою — перекріплюється сюди; повторний клік — зняти.
3. Кнопка «Авто» — перепризначає все, піни знімаються.
4. `accordion_after_1.png` → у гонки 1 зʼявляється мій результат (рядок з чекбоксом внизу панелі), Save активується при повних даних.
5. Скан before-фікстури З ІНШИМ часом суперника у слоті 1 (наприклад `accordion_race1.png`, час 22797 проти 19152): якщо в сесії немає моїх часів — сесія тихо замінилась; якщо є (після кроку 4) — зʼявився другий таб сесій «▶ поточна / ⏸ HH:MM · N».
6. Save selected у старому табі зберігає заїзди і закриває таб; Discard — закриває без збереження; лишається одна сесія.
7. Оверлей (F9) показує дані активної сесії, 👎 працює.

Знайдені у сценарії проблеми виправляти в рамках цього завдання (це UI-збирання — останній гейт етапу).

---

## Самоперевірка покриття спеки (етап 1)

| Вимога спеки | Завдання |
|---|---|
| §1 Поля opponent_time/opponent_car у RaceCapture/EffectiveRace | Task 1 |
| §1 assigned_cars + pinned | Task 2 |
| §2 SessionManager: мерж, конфлікт за opponent_time, одноразовість, ≥1 сесія | Task 4 |
| §3 Акордеон: регіони лівого боку, обидва варіанти | Task 3 |
| §4 UI: картки 5 гонок, панель гонки, «N/10 побито», Δ, притлумлення, перекріплення | Task 9, 10 |
| §4 Таби сесій (видимі при >1), заголовки «▶/⏸» | Task 10 |
| §5 Лаплас, P(≥3), топ-K=вільні гонки, тай-брейк маржином, піни, гонка без часу суперника | Task 5–7 |
| §5 Автозапуск після скану з даними суперника; кнопка «Авто» force | Task 4 (хук) + 7 + 10 |
| §9 Тести: сесії/менеджер/підбір/акордеон | Task 1–7 |
| Поза етапом 1 (спека §8): оверлей з підбором (етап 2), екрани 2/3, map matching, track_fix, звуження за часом (етап 3) | — |
