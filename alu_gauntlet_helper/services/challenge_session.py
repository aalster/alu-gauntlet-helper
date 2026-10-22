from datetime import datetime
from typing import Callable

from pydantic import BaseModel

from alu_gauntlet_helper.models import FieldGuess, RaceCapture, RecognitionResult
from alu_gauntlet_helper.services.races import RaceView

RACE_COUNT = 5
LOW_CONFIDENCE = 0.85
# режими автопідбору «щонайменше k перемог з 5»; нова сесія — завжди 5/5
WIN_GOALS = (3, 4, RACE_COUNT)
DEFAULT_GOAL = RACE_COUNT


def visible_goals(won: int, lost: int, no_data: int) -> tuple[int, ...]:
    """Які кнопки режиму показувати на оверлеї: лише ще досяжні й ще не
    перевищені цілі — k у межах won ≤ k ≤ 5 − lost − no_data. Гонка без
    даних вважається пропущеною (гравець часто їде лише 3 з 5 і треки
    решти не сканує). Коли межі порожні (нова сесія без сканів, 3 програші),
    лишається найнижча ціль — хоч одна кнопка видима завжди."""
    hi = RACE_COUNT - lost - no_data
    goals = tuple(g for g in WIN_GOALS if won <= g <= hi)
    return goals or (WIN_GOALS[0],)


def reachable_goal(goal: int, won: int, lost: int) -> int:
    """Ціль, під яку є сенс підбирати: поточна, якщо її ще можна досягти й вона
    не нижча за вже вигране, інакше найближча така. Гонки без даних тут не
    враховуються: вони ще можуть бути зіграні (гравець зазвичай спершу
    підбирає всі авто й лише потім їде), тож автоперемикання реагує лише
    на факти — програші та перемоги."""
    goals = [g for g in WIN_GOALS if won <= g <= RACE_COUNT - lost]
    if not goals:
        return WIN_GOALS[0]
    return goal if goal in goals else min(goals, key=lambda g: abs(g - goal))


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
    opponent_time: int = 0
    opponent_car_id: int = 0
    # карта гонки, коли трек не визначено сканом/драфтом (джерело: екран 3);
    # разом із track_candidates живить чипи треків і песимістичну оцінку
    map_id: int = 0
    # сирі кандидати OCR-треку (id, score) — заповнені лише при невпевненому треку
    track_candidates: list[tuple[int, float]] = []
    track_inferred: bool = False  # трек узято з виведеного (не ручного) фікса
    # трек узято з фікса (чип користувача або звуження) — оверлей фарбує
    # його cyan на відміну від треку зі скану/драфта
    track_fixed: bool = False
    # рекомендоване авто (клік по списку/автопідбір) — ОКРЕМИЙ шар: ніколи не
    # потрапляє в car_id і не зберігається в БД; ненульове лише коли авто заїзду
    # (car_id/car_name) порожнє
    suggested_car_id: int = 0

    @property
    def has_car(self) -> bool:
        return self.car_id > 0 or bool(self.car_name)

    @property
    def shown_car_id(self) -> int:
        """Авто для показу/оцінок: фактичне (драфт/OCR), інакше — рекомендоване."""
        return self.car_id if self.car_id > 0 else self.suggested_car_id

    @property
    def is_empty(self) -> bool:
        """Жодного значущого поля — гонка по суті нерозпізнана/непочата."""
        return not (self.track_id > 0 or self.has_car or self.rank > 0
                    or self.time > 0 or self.note or self.bad_timing
                    or self.opponent_time > 0 or self.opponent_car_id > 0
                    or self.map_id > 0)

    @property
    def is_complete(self) -> bool:
        return self.track_id > 0 and self.has_car and self.time > 0


def merge_guess(old: FieldGuess | None, new: FieldGuess | None) -> FieldGuess | None:
    """Свіжіший скан завжди затирає попередній: гравець міг змінити вибір у грі,
    і старе впевненіше значення не має його «перекривати». Сміття вже відсіяв
    поріг матчера (нижче нього FieldGuess не створюється), тож score тут не
    порівнюємо. None у новому скані означає «поле не бачив» — старе лишається."""
    return old if new is None else new


class ChallengeSessionService:
    """Стан поточного челенджа (5 гонок) у пам'яті. Викликається тільки з UI-потоку."""

    def __init__(self):
        self.races: dict[int, RaceCapture] = {}
        self.drafts: dict[int, RaceView] = {}
        self.last_event: str = ""
        self._listeners: list[Callable[[], None]] = []
        self.created_at = datetime.now()
        # рекомендації авто на гонки — окремо від авто заїзду (draft/OCR):
        # {race_number: car_id}; у драфт ніколи не пишуться
        self.suggested: dict[int, int] = {}
        # позначка «рекомендацію вибрано вручну» — для автопідбору
        self.pinned_races: set[int] = set()
        # вибір треку при неоднозначності (чип користувача або звуження за
        # часом): {race_number: track_id}; слабший за драфт і впевнений скан
        self.track_fix: dict[int, int] = {}
        self.inferred_tracks: set[int] = set()  # які фікси виведені (бейдж «ймовірно»)
        # режим автопідбору: скільки перемог з 5 максимізувати (WIN_GOALS)
        self.goal: int = DEFAULT_GOAL

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
        # «новий заїзд»: скан приніс час, якого в OCR-шарі гонки ще не було
        is_new_run = new.time is not None and (current is None or new.time != current.time)
        if current is None:
            self.races[new.race_number] = new
        else:
            current.track = merge_guess(current.track, new.track)
            current.car = merge_guess(current.car, new.car)
            # скалярні поля без score: будь-яке нове не-None значення перемагає
            if new.rank is not None:
                current.rank = new.rank
            if new.time is not None:
                current.time = new.time
            if new.opponent_time is not None:
                current.opponent_time = new.opponent_time
            current.opponent_car = merge_guess(current.opponent_car, new.opponent_car)
            current.map = merge_guess(current.map, new.map)
            if new.panel_image:
                current.panel_image = new.panel_image
            current.source_screen = new.source_screen or current.source_screen
        # Фактичний заїзд затирає вибране/вписане авто й ранг: якщо гравець обрав
        # одне авто, а проїхав іншим — правда за скріншотом (свідома зміна старої
        # логіки «дані користувача важливіші за розпізнані»). Повторний скан того
        # САМОГО результату (той самий час) ручні правки не чіпає — інакше
        # виправлення помилки OCR стиралося б рескана.
        if is_new_run and new.car is not None:
            draft = self.drafts.get(new.race_number)
            if draft is not None:
                draft.car_id = 0
                draft.car_name = ""
                draft.rank = 0
            # рекомендація виконала свою роль — заїзд відбувся
            self.suggested.pop(new.race_number, None)
            self.pinned_races.discard(new.race_number)

    def set_draft(self, race_number: int, draft: RaceView):
        """Ручні правки гонки. Непорожні поля драфта перекривають OCR, порожні — «просвічують» його."""
        self.drafts[race_number] = draft
        self._notify()

    def toggle_bad_timing(self, race_number: int):
        """Перемикач 👎 на оверлеї: фліпає прапорець лише в драфті — інші поля
        драфта лишаються порожніми, тож OCR-значення й далі «просвічують»."""
        e = self.effective(race_number)
        if e is None:
            return
        self.drafts.setdefault(race_number, RaceView()).bad_timing = not e.bad_timing
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
                e.track_fixed = True
                e.track_inferred = race_number in self.inferred_tracks
            if capture.map and (e.track_id <= 0 or track_from_fix):
                # карту показуємо, поки трек не визначено сканом/драфтом:
                # після вибору чипом вона лишається — чипи не зникають
                e.map_id = capture.map.value
            if not e.has_car and capture.car:
                e.car_id = capture.car.value
                e.car_uncertain = capture.car.score < LOW_CONFIDENCE
            if e.rank <= 0 and capture.rank:
                e.rank = capture.rank
            if e.time <= 0 and capture.time:
                e.time = capture.time
            if capture.opponent_time:
                e.opponent_time = capture.opponent_time
            if capture.opponent_car:
                e.opponent_car_id = capture.opponent_car.value
        # порожній результат (напр. розпізнано лише номер гонки чи збережено порожню
        # модалку) має виглядати як нерозпізнана гонка, а не порожня картка
        if e.is_empty:
            return None
        # рекомендація видима лише поки авто заїзду невідоме: щойно авто
        # з'явилось (скан вибору авто / модалка) — його правда, рекомендація зайва
        if not e.has_car:
            e.suggested_car_id = self.suggested.get(race_number, 0)
        return e

    def is_complete(self) -> bool:
        return all(
            (e := self.effective(n)) is not None and e.is_complete
            for n in range(1, RACE_COUNT + 1)
        )

    # --- рекомендації авто на гонку (окремий шар suggested, драфт не чіпаємо) ---

    def set_assigned(self, race_number: int, car_id: int | None, pinned: bool = True):
        """Рекомендувати авто для гонки (None — зняти рекомендацію). Авто заїзду
        (draft/OCR) не чіпається; якщо воно вже відоме — рекомендація не потрібна
        і виклик ігнорується. Одне авто — одна гонка: вибір знімає це авто з
        рекомендації іншої гонки."""
        e = self.effective(race_number)
        if e is not None and e.has_car:
            return
        if car_id is None:
            self.suggested.pop(race_number, None)
            self.pinned_races.discard(race_number)
        else:
            for n in [n for n, c in self.suggested.items()
                      if n != race_number and c == car_id]:
                del self.suggested[n]
                self.pinned_races.discard(n)
            self.suggested[race_number] = car_id
            if pinned:
                self.pinned_races.add(race_number)
            else:
                self.pinned_races.discard(race_number)
        self._notify()

    def set_assignments(self, assignment: dict[int, int]):
        """Результат автопідбору: пише рекомендації незапінених гонок без авто;
        запінені (ручний вибір) і гонки з відомим авто заїзду — недоторкані."""
        for n in range(1, RACE_COUNT + 1):
            if n in self.pinned_races:
                continue
            e = self.effective(n)
            if e is not None and (e.has_car or e.time > 0):
                continue
            if n in assignment:
                self.suggested[n] = assignment[n]
            else:
                self.suggested.pop(n, None)
        self._notify()

    def clear_pins(self):
        """Зняти всі піни (для кнопки «Авто»)."""
        self.pinned_races = set()
        self._notify()

    def set_goal(self, goal: int):
        """Режим автопідбору (3/4/5 перемог). Перепідбір робить AssistantService.set_goal."""
        self.goal = goal
        self._notify()

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

    @property
    def is_disposable(self) -> bool:
        """Немає моїх часів і змістовних ручних правок — сесію можна тихо замінити
        новою (скаутинг: кожен скан кандидата затирає попереднього). Драфт, що
        містить лише вибір авто/рангу (закріплення), одноразовість НЕ скасовує."""
        if any(c.time for c in self.races.values()):
            return False
        return not any(d.time or d.note or d.bad_timing for d in self.drafts.values())

    def outcomes(self) -> tuple[int, int, int]:
        """(виграно, програно, без даних) по 5 гонках. Результат відомий лише
        для зіграної гонки з часом суперника; нічия = програш, як в оцінці
        шансів (гра ховає мілісекунди, тож рівні часи — умовність)."""
        won = lost = no_data = 0
        for n in range(1, RACE_COUNT + 1):
            e = self.effective(n)
            if e is None:
                no_data += 1
            elif e.time > 0 and e.opponent_time > 0:
                if e.time < e.opponent_time:
                    won += 1
                else:
                    lost += 1
        return won, lost, no_data

    @property
    def timed_count(self) -> int:
        """Кількість гонок з моїм часом — для заголовка таба відщепленої сесії."""
        return sum(1 for n in range(1, RACE_COUNT + 1)
                   if (e := self.effective(n)) is not None and e.time > 0)

    def clear(self):
        self.races = {}
        self.drafts = {}
        self.last_event = ""
        self.suggested = {}
        self.pinned_races = set()
        self.track_fix = {}
        self.inferred_tracks = set()
        self.goal = DEFAULT_GOAL
        self._notify()
