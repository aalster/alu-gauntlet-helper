from typing import Callable, Union

from alu_gauntlet_helper.models import RecognitionResult
from alu_gauntlet_helper.services.challenge_session import ChallengeSessionService
from alu_gauntlet_helper.services.training_session import (TRAINING_SCREENS,
                                                           TrainingSessionService)

Session = Union[ChallengeSessionService, TrainingSessionService]


class SessionManager:
    """Список сесій (челенджі + тренування впереміш, у порядку створення).

    Активна сесія — ЯВНИЙ вказівник (не остання в списку): скан, сумісний з
    відщепленою сесією свого типу, РЕАКТИВУЄ її без переміщення таба. Скани
    маршрутизуються за типом екрана: тренувальні (TRAINING_SCREENS) — у
    «смугу» тренувань, решта — у челенджі; ціль — остання сесія свого типу.

    Конфлікт челенджа = розбіжність opponent_time (мс — практично унікальний
    відбиток суперника) або карти зі скаут-іконки у будь-якому слоті;
    розбіжність лише треку/авто — корекція розпізнавання, вирішується мержем
    за score. Конфлікт тренування = лобі-скан з іншим треком (див.
    TrainingSessionService.conflicts).

    При конфлікті/зміні смуги одноразова сесія (без моїх часів і правок) тихо
    зникає, цінна — лишається в списку табом (read-only для сканів, поки
    сумісний скан її не реактивує). Викликається тільки з UI-потоку."""

    def __init__(self, auto_pick: Callable[[ChallengeSessionService], None] | None = None,
                 reconcile_goal: Callable[[ChallengeSessionService], None] | None = None):
        self._auto_pick = auto_pick
        self._reconcile_goal = reconcile_goal
        self.sessions: list[Session] = []
        self._active: Session | None = None
        self._listeners: list[Callable[[], None]] = []
        self._new_session(ChallengeSessionService)

    @property
    def active(self) -> Session:
        return self._active

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

    def _new_session(self, cls) -> Session:
        session = cls()
        session.add_listener(self._notify)  # зміни сесії ретранслюються нагору
        self.sessions.append(session)
        self._active = session
        return session

    def _drop(self, session: Session):
        session.remove_listener(self._notify)
        if session in self.sessions:
            self.sessions.remove(session)

    def close(self, session: Session):
        """Після Save або Discard: сесія зникає зі списку; завжди лишається ≥1."""
        self._drop(session)
        if not self.sessions:
            self._new_session(ChallengeSessionService)
        elif self._active is session:
            self._active = self.sessions[-1]
        self._notify()

    # --- роутинг сканів ----------------------------------------------------

    @staticmethod
    def _challenge_conflicts(session: ChallengeSessionService,
                             result: RecognitionResult) -> bool:
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

    def _conflicts(self, session: Session, result: RecognitionResult) -> bool:
        if isinstance(session, TrainingSessionService):
            return session.conflicts(result)
        return self._challenge_conflicts(session, result)

    def apply(self, result: RecognitionResult):
        if not result.captures:
            return
        is_training = result.screen in TRAINING_SCREENS
        cls = TrainingSessionService if is_training else ChallengeSessionService
        # ціль — остання сесія свого типу (нові завжди додаються в кінець,
        # тож «остання в списку» = найсвіжіша цієї смуги)
        target = next((s for s in reversed(self.sessions) if isinstance(s, cls)), None)
        if target is not None and not self._conflicts(target, result):
            if target is not self._active:
                self._active = target  # реактивація без переміщення таба
                self._notify()
        else:
            # сумісної сесії цього типу немає → нова; одноразові сесії (і
            # конфліктна ціль, і активна іншого типу) тихо зникають — порожній
            # таб, до якого скан «не відноситься», не лишаємо
            if target is not None and target.is_disposable:
                self._drop(target)
            if (self._active is not None and self._active is not target
                    and self._active in self.sessions and self._active.is_disposable):
                self._drop(self._active)
            self._new_session(cls)
            self._notify()  # структурна зміна — UI перемикається на нову активну
        # карта/трек зі скаут-екрана — теж дані суперника: тригерить
        # resolve_tracks (звуження за часом) і підбір одразу після скану;
        # скан лише з треками (іконка карти не зматчилась) теж має запускати
        # підбір, тож track у переліку тригерів так само, як map/opponent_*
        self._active.apply(result)  # сесія сама нотифікує через ретрансляцію
        if is_training:
            return  # автопідбір — суто челенджева механіка
        # мій результат міг зробити ціль недосяжною (програш) або
        # перевищеною — перемикаємо режим до підбору, щоб він рахувався під
        # реальну мету
        if self._reconcile_goal:
            self._reconcile_goal(self._active)
        has_opponent_data = any(c.opponent_time or c.opponent_car or c.map or c.track
                                for c in result.captures)
        if has_opponent_data and self._auto_pick:
            self._auto_pick(self._active)
