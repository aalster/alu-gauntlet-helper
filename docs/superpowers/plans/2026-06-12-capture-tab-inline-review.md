# Capture: інлайн-рев'ю в табі — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Прибрати `CaptureReviewDialog`; рев'ю, редагування (через `RaceDialog`) і збереження захоплених гонок — прямо в `CaptureTab`, з чекбоксами вибору й одним сабмітом.

**Architecture:** `ChallengeSessionService` отримує другий шар `drafts` (ручні правки як `RaceView`) поверх OCR-шару `races`; метод `effective()` зливає їх у `EffectiveRace` — єдине джерело для таба, оверлея і збереження. `RaceDialog` отримує relaxed-режим (порожні поля дозволені), щоб юзер міг стерти значення й «відкрити» поле назад для OCR.

**Tech Stack:** Python 3.9+, PyQt6, Pydantic, pytest.

**Spec:** `docs/superpowers/specs/2026-06-12-capture-tab-inline-review-design.md`

**Git:** Юзер комітить сам — НЕ виконувати git commit/push. Кроки комітів у плані відсутні навмисно.

---

## File Structure

- Modify: `alu_gauntlet_helper/services/challenge_session.py` — `EffectiveRace`, `drafts`, `set_draft()`, `effective()`, оновлені `is_complete()`/`clear()`
- Modify: `alu_gauntlet_helper/views/overlay.py` — `build_overlay_lines` приймає `dict[int, EffectiveRace]`
- Modify: `alu_gauntlet_helper/capture/capture_controller.py` — `_refresh_overlay` через `effective()`
- Modify: `alu_gauntlet_helper/views/races_tab.py` — `RaceDialog`: параметри `relaxed`, `title`
- Rewrite: `alu_gauntlet_helper/views/capture_tab.py` — рядки з чекбоксами/Edit, Save selected
- Delete: `alu_gauntlet_helper/views/capture_review_dialog.py`
- Modify: `tests/test_challenge_session.py` — тести на drafts/effective
- Modify: `tests/test_overlay_lines.py` — переписати під `EffectiveRace`

---

### Task 1: `ChallengeSessionService` — шар драфтів і `effective()`

**Files:**
- Modify: `alu_gauntlet_helper/services/challenge_session.py`
- Test: `tests/test_challenge_session.py`

- [ ] **Step 1.1: Дописати failing-тести**

Додати в кінець `tests/test_challenge_session.py` (хелпери `capture`/`result` вже є у файлі):

```python
# --- drafts / effective -------------------------------------------------

from alu_gauntlet_helper.services.races import RaceView


def draft(track_id=0, car_id=0, car_name="", rank=0, time=0, bad_timing=False, note=""):
    return RaceView(track_id=track_id, car_id=car_id, car_name=car_name,
                    rank=rank, time=time, bad_timing=bad_timing, note=note)


def test_effective_none_without_data():
    s = ChallengeSessionService()
    assert s.effective(1) is None


def test_effective_from_ocr_with_uncertainty_flags():
    s = ChallengeSessionService()
    s.apply(result(capture(1, track_score=0.5, car_score=0.9, rank=3000, time=22797)))
    e = s.effective(1)
    assert e.track_id == 11 and e.track_uncertain is True
    assert e.car_id == 21 and e.car_uncertain is False
    assert e.rank == 3000 and e.time == 22797
    assert e.bad_timing is False and e.note == ""


def test_effective_draft_overrides_ocr():
    s = ChallengeSessionService()
    s.apply(result(capture(1, track_score=0.5, car_score=0.5, time=22797)))
    s.set_draft(1, draft(track_id=77, car_id=88, time=20000, bad_timing=True, note="crash"))
    e = s.effective(1)
    assert e.track_id == 77 and e.track_uncertain is False
    assert e.car_id == 88 and e.car_uncertain is False
    assert e.time == 20000
    assert e.bad_timing is True and e.note == "crash"


def test_effective_empty_draft_field_falls_back_to_ocr():
    s = ChallengeSessionService()
    s.apply(result(capture(1, track_score=0.9, time=22797)))
    s.set_draft(1, draft(car_id=88))  # трек і час у драфті порожні
    e = s.effective(1)
    assert e.track_id == 11  # просвічує OCR
    assert e.time == 22797
    assert e.car_id == 88


def test_effective_custom_car_name_from_draft():
    s = ChallengeSessionService()
    s.apply(result(capture(1, car_score=0.5)))
    s.set_draft(1, draft(car_name="Custom Car"))
    e = s.effective(1)
    assert e.car_id == 0 and e.car_name == "Custom Car"
    assert e.car_uncertain is False  # авто задане руками, OCR не використовується


def test_effective_draft_without_capture():
    s = ChallengeSessionService()
    s.set_draft(3, draft(track_id=5, car_id=6, time=30000))
    e = s.effective(3)
    assert e.track_id == 5 and e.car_id == 6 and e.time == 30000
    assert e.is_complete


def test_effective_is_complete_property():
    e1 = EffectiveRace(track_id=1, car_id=2, time=1000)
    e2 = EffectiveRace(track_id=1, car_name="Custom", time=1000)
    e3 = EffectiveRace(track_id=1, car_id=2)  # без часу
    assert e1.is_complete and e2.is_complete and not e3.is_complete


def test_set_draft_notifies_listeners():
    s = ChallengeSessionService()
    events = []
    s.add_listener(lambda: events.append(1))
    s.set_draft(1, draft(time=1000))
    assert events == [1]


def test_clear_resets_drafts():
    s = ChallengeSessionService()
    s.set_draft(1, draft(time=1000))
    s.clear()
    assert s.drafts == {}
    assert s.effective(1) is None


def test_is_complete_uses_drafts():
    s = ChallengeSessionService()
    for n in range(1, 5):
        s.apply(result(capture(n, track_score=0.9, car_score=0.9, time=20000)))
    assert not s.is_complete()
    s.set_draft(5, draft(track_id=5, car_id=6, time=30000))
    assert s.is_complete()
```

І додати `EffectiveRace` до імпорту вгорі файлу:

```python
from alu_gauntlet_helper.services.challenge_session import ChallengeSessionService, EffectiveRace
```

- [ ] **Step 1.2: Переконатися, що тести падають**

Run: `python -m pytest tests/test_challenge_session.py -v`
Expected: FAIL/ERROR — `ImportError: cannot import name 'EffectiveRace'`.

- [ ] **Step 1.3: Імплементація в `challenge_session.py`**

Додати імпорти й модель угорі файлу (після наявних імпортів):

```python
from pydantic import BaseModel

from alu_gauntlet_helper.services.races import RaceView

LOW_CONFIDENCE = 0.85


class EffectiveRace(BaseModel):
    """Злиті дані гонки: драфт юзера поверх OCR. Єдине джерело для таба/оверлея/збереження."""
    track_id: int = 0
    car_id: int = 0
    car_name: str = ""  # кастомне авто з драфта, коли car_id == 0
    rank: int = 0
    time: int = 0
    bad_timing: bool = False
    note: str = ""
    track_uncertain: bool = False
    car_uncertain: bool = False

    @property
    def has_car(self) -> bool:
        return self.car_id > 0 or bool(self.car_name)

    @property
    def is_complete(self) -> bool:
        return self.track_id > 0 and self.has_car and self.time > 0
```

У `ChallengeSessionService.__init__` додати:

```python
        self.drafts: dict[int, RaceView] = {}
```

Додати методи (після `_merge`):

```python
    def set_draft(self, race_number: int, draft: RaceView):
        """Ручні правки гонки. Непорожні поля драфта перекривають OCR, порожні — «просвічують» його."""
        self.drafts[race_number] = draft
        self._notify()

    def effective(self, race_number: int) -> EffectiveRace | None:
        capture = self.races.get(race_number)
        draft = self.drafts.get(race_number)
        if capture is None and draft is None:
            return None
        e = EffectiveRace()
        if draft:
            e.track_id = draft.track_id
            e.car_id = draft.car_id
            e.car_name = draft.car_name if draft.car_id <= 0 else ""
            e.rank = draft.rank
            e.time = draft.time
            e.bad_timing = draft.bad_timing
            e.note = draft.note
        if capture:
            if e.track_id <= 0 and capture.track:
                e.track_id = capture.track.value
                e.track_uncertain = capture.track.score < LOW_CONFIDENCE
            if not e.has_car and capture.car:
                e.car_id = capture.car.value
                e.car_uncertain = capture.car.score < LOW_CONFIDENCE
            if e.rank <= 0 and capture.rank:
                e.rank = capture.rank
            if e.time <= 0 and capture.time:
                e.time = capture.time
        return e
```

Замінити `is_complete` (тепер враховує драфти):

```python
    def is_complete(self) -> bool:
        return all(
            (e := self.effective(n)) is not None and e.is_complete
            for n in range(1, RACE_COUNT + 1)
        )
```

У `clear()` додати скидання драфтів:

```python
    def clear(self):
        self.races = {}
        self.drafts = {}
        self.last_event = ""
        self._notify()
```

- [ ] **Step 1.4: Тести зелені**

Run: `python -m pytest tests/test_challenge_session.py -v`
Expected: усі PASS (старі + нові).

---

### Task 2: Оверлей на `EffectiveRace`

**Files:**
- Modify: `alu_gauntlet_helper/views/overlay.py`
- Modify: `alu_gauntlet_helper/capture/capture_controller.py:121-133` (`_refresh_overlay`)
- Test: `tests/test_overlay_lines.py`

- [ ] **Step 2.1: Переписати тести під `EffectiveRace`**

Повний новий вміст `tests/test_overlay_lines.py`:

```python
from alu_gauntlet_helper.services.challenge_session import EffectiveRace
from alu_gauntlet_helper.views.overlay import build_overlay_lines


def test_empty_session():
    lines = build_overlay_lines({}, {}, {}, status="чекаю")
    assert lines[0] == "Gauntlet capture 0/5"
    assert lines[1] == "1 — немає даних"
    assert lines[-1] == "чекаю"


def test_complete_race_line():
    races = {1: EffectiveRace(track_id=11, car_id=21, time=22797)}
    lines = build_overlay_lines(races, {11: "Notre Dame"}, {21: "Ultima RS"})
    assert lines[0] == "Gauntlet capture 1/5"
    assert lines[1] == "1 ✓ Notre Dame · Ultima RS · 00:22.797"


def test_partial_race_marked():
    races = {2: EffectiveRace(time=21000)}
    lines = build_overlay_lines(races, {}, {})
    assert lines[1] == "1 — немає даних"
    assert lines[2].startswith("2 ⚠")
    assert "00:21.000" in lines[2]
    assert "?" in lines[2]


def test_custom_car_name_counts_as_complete():
    races = {1: EffectiveRace(track_id=11, car_name="Custom Car", time=22797)}
    lines = build_overlay_lines(races, {11: "Notre Dame"}, {})
    assert lines[0] == "Gauntlet capture 1/5"
    assert lines[1] == "1 ✓ Notre Dame · Custom Car · 00:22.797"
```

- [ ] **Step 2.2: Переконатися, що тести падають**

Run: `python -m pytest tests/test_overlay_lines.py -v`
Expected: FAIL — старий `build_overlay_lines` працює з `RaceCapture` (`AttributeError` на `track`/`car` тощо).

- [ ] **Step 2.3: Імплементація `build_overlay_lines`**

В `overlay.py` замінити імпорти й функцію:

```python
from alu_gauntlet_helper.services.challenge_session import EffectiveRace
from alu_gauntlet_helper.utils.utils import format_time
```

(прибрати імпорт `RaceCapture` з `models`)

```python
def build_overlay_lines(races: dict[int, EffectiveRace],
                        track_names: dict[int, str],
                        car_names: dict[int, str],
                        status: str = "") -> list[str]:
    complete = sum(1 for e in races.values() if e.is_complete)
    lines = [f"Gauntlet capture {complete}/5"]
    for n in range(1, RACE_COUNT + 1):
        e = races.get(n)
        if e is None:
            lines.append(f"{n} — немає даних")
            continue
        track = track_names.get(e.track_id, "?") if e.track_id else "?"
        car = car_names.get(e.car_id, "?") if e.car_id else (e.car_name or "?")
        time_str = format_time(e.time) if e.time else "?"
        mark = "✓" if e.is_complete else "⚠"
        lines.append(f"{n} {mark} {track} · {car} · {time_str}")
    if status:
        lines.append(status)
    return lines
```

- [ ] **Step 2.4: Тести зелені**

Run: `python -m pytest tests/test_overlay_lines.py -v`
Expected: усі PASS.

- [ ] **Step 2.5: `CaptureController._refresh_overlay` через `effective()`**

У `capture_controller.py` замінити метод `_refresh_overlay`:

```python
    def _refresh_overlay(self):
        session = APP_CONTEXT.challenge_session
        effective = {n: e for n in range(1, 6) if (e := session.effective(n)) is not None}
        track_ids = {e.track_id for e in effective.values() if e.track_id}
        car_ids = {e.car_id for e in effective.values() if e.car_id}
        track_names = {t.id: t.name for t in APP_CONTEXT.tracks_service.get_by_ids(track_ids).values()}
        car_names = {c.id: c.name for c in APP_CONTEXT.cars_service.get_by_ids(car_ids).values()}

        status = self._status
        if not status and session.is_complete():
            status = "Готово — відкрий рев'ю у застосунку"
        self.overlay.set_lines(build_overlay_lines(effective, track_names, car_names, status))
        if not self.overlay.isVisible():
            self.overlay.show()
```

- [ ] **Step 2.6: Повний прогін тестів**

Run: `python -m pytest tests/ -q`
Expected: усі PASS.

---

### Task 3: `RaceDialog` — relaxed-режим і кастомний заголовок

**Files:**
- Modify: `alu_gauntlet_helper/views/races_tab.py:19-89` (`RaceDialog`)

UI-діалог без юніт-тестів (у проєкті немає Qt-тестів) — перевірка вручну в Task 5.

- [ ] **Step 3.1: Конструктор**

Замінити сигнатуру й кінець `__init__`:

```python
class RaceDialog(EditDialog):
    def __init__(self, item: RaceView, action, parent=None, relaxed=False, title=""):
        self.item = item
        self.relaxed = relaxed  # порожні трек/авто/час дозволені (capture-драфти)
```

(решта `__init__` без змін, окрім останнього рядка):

```python
        super().__init__(action, parent)
        self.setWindowTitle(title or ("Edit Race" if item.id else "Add Race"))
```

- [ ] **Step 3.2: Послаблена валідація у `prepare_item`**

Замінити блок валідації:

```python
        error = False
        if track_id <= 0 and not self.relaxed:
            self.track_edit.set_error()
            error = True

        if not car_name and not self.relaxed:
            self.car_edit.set_error()
            error = True

        if not time and not self.relaxed:
            self.time_edit.set_error()
            error = True
```

- [ ] **Step 3.3: Smoke-перевірка, що races-таб не зламався**

Run: `python -m pytest tests/ -q` (регресій немає)
Expected: усі PASS. Поведінка races-таба не змінюється (`relaxed=False` за замовчуванням).

---

### Task 4: `CaptureTab` — інлайн-рев'ю; видалити `CaptureReviewDialog`

**Files:**
- Rewrite: `alu_gauntlet_helper/views/capture_tab.py`
- Delete: `alu_gauntlet_helper/views/capture_review_dialog.py`

- [ ] **Step 4.1: Повний новий вміст `capture_tab.py`**

```python
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QHBoxLayout, QLabel, QMessageBox,
                             QPushButton, QVBoxLayout, QWidget)

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.challenge_session import RACE_COUNT, EffectiveRace
from alu_gauntlet_helper.services.races import RaceView
from alu_gauntlet_helper.utils.utils import format_time
from alu_gauntlet_helper.views import style
from alu_gauntlet_helper.views.components.common import res_to_pixmap
from alu_gauntlet_helper.views.races_tab import RaceDialog

WARN_ICON = '<span style="color: #FFC107;">⚠</span> '


class CaptureRaceRow(QWidget):
    """Рядок гонки: чекбокс вибору + ефективні значення + іконки bad_timing/note + Edit."""

    def __init__(self, race_number: int, on_toggle, on_edit):
        super().__init__()
        self.race_number = race_number

        self.checkbox = QCheckBox()
        # clicked — тільки від кліку юзера; програмний setChecked його не емітить
        self.checkbox.clicked.connect(lambda checked: on_toggle(race_number, checked))

        self.label = QLabel()
        self.label.setTextFormat(Qt.TextFormat.RichText)

        self.bad_timing_icon = QLabel()
        self.bad_timing_icon.setPixmap(res_to_pixmap("icons/dislike.png", 18))
        self.note_icon = QLabel()
        self.note_icon.setPixmap(res_to_pixmap("icons/info.png", 18))

        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(lambda: on_edit(race_number))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.checkbox)
        layout.addWidget(self.label, stretch=1)
        layout.addWidget(self.bad_timing_icon)
        layout.addWidget(self.note_icon)
        layout.addWidget(self.edit_button)

    def update_row(self, e: EffectiveRace | None, track_name: str, car_name: str, checked: bool):
        self.checkbox.setEnabled(e is not None)
        self.checkbox.setChecked(checked)
        self.bad_timing_icon.setVisible(bool(e and e.bad_timing))
        self.note_icon.setVisible(bool(e and e.note))
        self.note_icon.setToolTip(e.note if e else "")
        if e is None:
            self.label.setText(f"Race {self.race_number}: —")
            self.label.setStyleSheet(f"color: {style.TEXT_MUTED};")
            return
        parts = [
            (WARN_ICON if e.track_uncertain else "") + (track_name or "трек?"),
            (WARN_ICON if e.car_uncertain else "") + (car_name or "авто?"),
            f"rank {e.rank}" if e.rank else "ранг?",
            format_time(e.time) if e.time else "час?",
        ]
        self.label.setText(f"Race {self.race_number}: " + " · ".join(parts))
        self.label.setStyleSheet("")


class CaptureTab(QWidget):
    """Стан сесії захоплення: рев'ю, редагування і збереження прямо в табі."""

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

        # ручні стани чекбоксів {race_number: bool}; немає ключа — авторежим (чекнуто, коли є час)
        self.manual_checks: dict[int, bool] = {}

        self.rows = [CaptureRaceRow(n, self.on_checkbox_toggled, self.open_edit)
                     for n in range(1, RACE_COUNT + 1)]

        self.save_button = QPushButton("Save selected")
        self.save_button.clicked.connect(self.save_selected)
        self.discard_button = QPushButton("Discard session")
        self.discard_button.clicked.connect(self.discard)

        buttons = QHBoxLayout()
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.discard_button)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        for row in self.rows:
            layout.addWidget(row)
        layout.addLayout(buttons)
        layout.addStretch()

        APP_CONTEXT.challenge_session.add_listener(self.refresh)
        self.refresh()

    def _effective_map(self) -> dict[int, EffectiveRace]:
        session = APP_CONTEXT.challenge_session
        return {n: e for n in range(1, RACE_COUNT + 1) if (e := session.effective(n)) is not None}

    def _is_checked(self, n: int, e: EffectiveRace | None) -> bool:
        if e is None:
            return False
        if n in self.manual_checks:
            return self.manual_checks[n]
        return e.time > 0

    def refresh(self):
        effective = self._effective_map()
        if not effective:
            self.manual_checks = {}  # сесію скинуто — чекбокси назад в авторежим

        track_ids = {e.track_id for e in effective.values() if e.track_id}
        car_ids = {e.car_id for e in effective.values() if e.car_id}
        tracks = APP_CONTEXT.tracks_service.get_by_ids(track_ids)
        cars = APP_CONTEXT.cars_service.get_by_ids(car_ids)

        any_checked = False
        all_checked_complete = True
        for row in self.rows:
            n = row.race_number
            e = effective.get(n)
            track = tracks.get(e.track_id) if e and e.track_id else None
            car = cars.get(e.car_id) if e and e.car_id else None
            track_name = f"{track.map_name} - {track.name}" if track else ""
            car_name = car.name if car else (e.car_name if e else "")
            checked = self._is_checked(n, e)
            row.update_row(e, track_name, car_name, checked)
            if checked:
                any_checked = True
                if e is None or not e.is_complete:
                    all_checked_complete = False

        self.save_button.setEnabled(any_checked and all_checked_complete)
        self.discard_button.setEnabled(bool(effective))

    def on_checkbox_toggled(self, n: int, checked: bool):
        self.manual_checks[n] = checked  # після ручного кліку автологіка для гонки вимикається
        self.refresh()

    def open_edit(self, n: int):
        e = APP_CONTEXT.challenge_session.effective(n)
        item = self._to_race_view(e) if e else RaceView()
        dialog = RaceDialog(item=item,
                            action=lambda r: APP_CONTEXT.challenge_session.set_draft(n, r),
                            parent=self, relaxed=True, title=f"Edit Race {n}")
        if e and e.car_id:
            car = APP_CONTEXT.cars_service.get_by_ids({e.car_id}).get(e.car_id)
            if car:
                dialog.cars_completer.set_selected_item(car)
        dialog.exec()  # set_draft → _notify → refresh

    @staticmethod
    def _to_race_view(e: EffectiveRace) -> RaceView:
        track = APP_CONTEXT.tracks_service.get_by_ids({e.track_id}).get(e.track_id) if e.track_id else None
        car = APP_CONTEXT.cars_service.get_by_ids({e.car_id}).get(e.car_id) if e.car_id else None
        return RaceView(
            track_id=e.track_id, car_id=e.car_id, rank=e.rank, time=e.time,
            bad_timing=e.bad_timing, note=e.note,
            map_name=track.map_name if track else "",
            track_name=track.name if track else "",
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
            QMessageBox.critical(self, "Save failed", str(ex))
            return  # сесію не чистимо — можна виправити й повторити
        APP_CONTEXT.challenge_session.clear()
        QMessageBox.information(self, "Saved", f"{len(races)} race(s) saved.")

    def discard(self):
        APP_CONTEXT.challenge_session.clear()
```

- [ ] **Step 4.2: Видалити `alu_gauntlet_helper/views/capture_review_dialog.py`**

Перед видаленням перевірити, що посилань більше немає:

Run: `grep -rn "capture_review_dialog\|CaptureReviewDialog" alu_gauntlet_helper/ tests/ main.py`
Expected: порожньо (після Step 4.1).

Потім видалити файл.

- [ ] **Step 4.3: Повний прогін тестів**

Run: `python -m pytest tests/ -q`
Expected: усі PASS.

- [ ] **Step 4.4: Перевірка, що застосунок стартує**

Run: `python -c "import alu_gauntlet_helper.views.capture_tab, alu_gauntlet_helper.views.main_window"`
Expected: без помилок імпорту (циклів немає: capture_tab → races_tab → services).

---

### Task 5: Ручна верифікація (чекліст для юзера/виконавця з GUI)

Автотестів на PyQt-віджети у проєкті немає — фінальна перевірка вручну, запустивши `python main.py`:

- [ ] Захоплення хоткеєм заповнює рядки таба; непевні значення мають жовтий «⚠»
- [ ] Чекбокс автоматично вмикається в гонок із часом; ручний клік «закріплює» стан
- [ ] Edit відкриває «Edit Race N» з передзаповненими значеннями; правки видно в рядку і в оверлеї
- [ ] Стерте в діалозі поле знову заповнюється наступним OCR-захопленням
- [ ] `Save selected` дизейблиться, поки серед чекнутих є неповна гонка
- [ ] Збереження пише чекнуті гонки в Races-таб і чистить сесію (чекбокси скинуто)
- [ ] `bad_timing`/`note` з діалога показуються іконками в рядку і зберігаються в гонку
- [ ] Оверлей показує ті ж трек/авто/час, що й таб (без bad_timing/note)
- [ ] Races-таб: Add/Edit працюють як раніше (обов'язкові трек/авто/час)
