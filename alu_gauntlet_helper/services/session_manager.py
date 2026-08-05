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
            if current is None:
                continue
            if (current.opponent_time and c.opponent_time
                    and current.opponent_time != c.opponent_time):
                return True
            # Карта з іконки — детермінований матч: рескан того самого екрана дає
            # ту саму карту, тож розбіжність = інший суперник/челендж (скаут-екрани
            # різних суперників не мають зливатись — спека, «Ігровий контекст»)
            if (current.map and c.map and current.map.value != c.map.value):
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
        # карта/трек зі скаут-екрана — теж дані суперника: тригерить
        # resolve_tracks (звуження за часом) і підбір одразу після скану;
        # скан лише з треками (іконка карти не зматчилась) теж має запускати
        # підбір, тож track у переліку тригерів так само, як map/opponent_*
        has_opponent_data = any(c.opponent_time or c.opponent_car or c.map or c.track
                                for c in result.captures)
        self.active.apply(result)  # сесія сама нотифікує через ретрансляцію
        if has_opponent_data and self._auto_pick:
            self._auto_pick(self.active)
