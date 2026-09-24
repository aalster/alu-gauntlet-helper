from datetime import datetime
from typing import Callable

from alu_gauntlet_helper.models import RaceCapture, RecognitionResult
from alu_gauntlet_helper.services.challenge_session import (LOW_CONFIDENCE, EffectiveRace,
                                                            merge_guess)
from alu_gauntlet_helper.services.races import RaceView

# Екрани тренування — маршрутизація сканів у SessionManager іде за цим переліком.
TRAINING_SCREENS = {"training_lobby", "training_result"}


class TrainingSessionService:
    """Стан тренувальної сесії (приватне лобі): один трек + необмежений список
    заїздів. Викликається тільки з UI-потоку (як і ChallengeSessionService).

    Трек/карта — ОДНІ на сесію (зі скану лобі), заїзди — captures ЛИШЕ з часом
    (скан результату). Нумерація заїздів наскрізна: збережені (remove_runs)
    зникають зі списку, але лічильник не скидається — оверлей показує «хвіст»
    із чесними номерами."""

    kind = "training"

    def __init__(self):
        self.track = None  # FieldGuess | None — трек сесії зі скану лобі
        self.map = None    # FieldGuess | None — карта (для показу, поки трек невідомий)
        self.runs: dict[int, RaceCapture] = {}
        self.drafts: dict[int, RaceView] = {}
        self.last_event: str = ""
        self.created_at = datetime.now()
        self._next_number = 1
        self._listeners: list[Callable[[], None]] = []

    # --- listener-и (той самий контракт, що в ChallengeSessionService) ------

    def add_listener(self, listener: Callable[[], None]):
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[], None]):
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify(self):
        for listener in list(self._listeners):
            listener()

    # --- скани --------------------------------------------------------------

    def apply(self, result: RecognitionResult):
        if not result.captures:
            return
        for c in result.captures:
            if c.time is not None:
                self._merge_run(c)
            else:
                # лобі: трек/карта сесії; упевненіший скан коригує попередній
                self.track = merge_guess(self.track, c.track)
                self.map = merge_guess(self.map, c.map)
        self.last_event = result.screen
        self._notify()

    def _merge_run(self, new: RaceCapture):
        """Той самий час, що в останнього заїзду, — рескан того ж результату
        (мерж), інакше — новий заїзд у кінець із наступним номером."""
        last_number = max(self.runs) if self.runs else 0
        last = self.runs.get(last_number)
        if last is not None and last.time == new.time:
            last.car = merge_guess(last.car, new.car)
            if new.panel_image:
                last.panel_image = new.panel_image
            return
        self.runs[self._next_number] = new
        self._next_number += 1

    def conflicts(self, result: RecognitionResult) -> bool:
        """Лобі-скан з ІНШИМ треком — інше тренування; скани результатів і
        лобі-скан у сесію без треку конфліктом не є."""
        if self.track is None:
            return False
        return any(c.time is None and c.track and c.track.value != self.track.value
                   for c in result.captures)

    # --- effective ----------------------------------------------------------

    def effective(self, number: int) -> EffectiveRace | None:
        capture = self.runs.get(number)
        if capture is None:
            return None
        draft = self.drafts.get(number)
        e = EffectiveRace()
        if draft:
            e.track_id = draft.track_id
            e.car_id = draft.car_id
            e.car_name = draft.car_name if draft.car_id <= 0 else ""
            e.rank = draft.rank
            e.time = draft.time
            e.bad_timing = draft.bad_timing
            e.note = draft.note
        if e.track_id <= 0 and self.track:
            e.track_id = self.track.value
            e.track_uncertain = self.track.score < LOW_CONFIDENCE
        if e.track_id <= 0 and self.map:
            e.map_id = self.map.value
        if not e.has_car and capture.car:
            e.car_id = capture.car.value
            e.car_uncertain = capture.car.score < LOW_CONFIDENCE
        if e.time <= 0 and capture.time:
            e.time = capture.time
        return e

    def run_numbers(self) -> list[int]:
        return sorted(self.runs)

    def is_complete(self) -> bool:
        """Контракт статусу оверлея: тренування нескінченне, «Done» не буває."""
        return False

    # --- правки -------------------------------------------------------------

    def set_draft(self, number: int, draft: RaceView):
        """Ручні правки заїзду: непорожні поля драфта перекривають OCR/трек сесії."""
        self.drafts[number] = draft
        self._notify()

    def toggle_bad_timing(self, number: int):
        e = self.effective(number)
        if e is None:
            return
        self.drafts.setdefault(number, RaceView()).bad_timing = not e.bad_timing
        self._notify()

    # --- життєвий цикл ------------------------------------------------------

    def remove_runs(self, numbers: list[int]):
        """Після Save: збережені заїзди зникають зі списку разом із драфтами;
        трек сесії і наскрізна нумерація лишаються."""
        for n in numbers:
            self.runs.pop(n, None)
            self.drafts.pop(n, None)
        self._notify()

    @property
    def is_disposable(self) -> bool:
        """Немає заїздів і змістовних правок — сесію можна тихо замінити
        (лобі-скан без жодного заїзду: інфо треку цінності не має)."""
        if self.runs:
            return False
        return not any(d.time or d.note or d.bad_timing for d in self.drafts.values())
