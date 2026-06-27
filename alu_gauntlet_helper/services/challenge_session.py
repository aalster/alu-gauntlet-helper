from typing import Callable

from pydantic import BaseModel

from alu_gauntlet_helper.models import FieldGuess, RaceCapture, RecognitionResult
from alu_gauntlet_helper.services.races import RaceView

RACE_COUNT = 5
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
    def is_empty(self) -> bool:
        """Жодного значущого поля — гонка по суті нерозпізнана/непочата."""
        return not (self.track_id > 0 or self.has_car or self.rank > 0
                    or self.time > 0 or self.note or self.bad_timing)

    @property
    def is_complete(self) -> bool:
        return self.track_id > 0 and self.has_car and self.time > 0


def merge_guess(old: FieldGuess | None, new: FieldGuess | None) -> FieldGuess | None:
    if new is None:
        return old
    # >= — за рівної впевненості перемагає свіжіше захоплення
    if old is None or new.score >= old.score:
        return new
    return old


class ChallengeSessionService:
    """Стан поточного челенджа (5 гонок) у пам'яті. Викликається тільки з UI-потоку."""

    def __init__(self):
        self.races: dict[int, RaceCapture] = {}
        self.drafts: dict[int, RaceView] = {}
        self.last_event: str = ""
        self._listeners: list[Callable[[], None]] = []

    def add_listener(self, listener: Callable[[], None]):
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[], None]):
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify(self):
        for listener in list(self._listeners):
            listener()

    def apply(self, result: RecognitionResult):
        if not result.captures:
            return
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
        # скалярні поля без score: будь-яке нове не-None значення перемагає
        if new.rank is not None:
            current.rank = new.rank
        if new.time is not None:
            current.time = new.time
        if new.panel_image:
            current.panel_image = new.panel_image
        current.source_screen = new.source_screen or current.source_screen

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
        # порожній результат (напр. розпізнано лише номер гонки чи збережено порожню
        # модалку) має виглядати як нерозпізнана гонка, а не порожня картка
        return e if not e.is_empty else None

    def is_complete(self) -> bool:
        return all(
            (e := self.effective(n)) is not None and e.is_complete
            for n in range(1, RACE_COUNT + 1)
        )

    def clear(self):
        self.races = {}
        self.drafts = {}
        self.last_event = ""
        self._notify()
