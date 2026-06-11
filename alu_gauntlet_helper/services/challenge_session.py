from typing import Callable

from alu_gauntlet_helper.models import FieldGuess, RaceCapture, RecognitionResult

RACE_COUNT = 5


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

    def is_complete(self) -> bool:
        return all(
            (c := self.races.get(n)) is not None
            and c.track is not None
            and c.car is not None
            and c.time is not None
            for n in range(1, RACE_COUNT + 1)
        )

    def clear(self):
        self.races = {}
        self.last_event = ""
        self._notify()
