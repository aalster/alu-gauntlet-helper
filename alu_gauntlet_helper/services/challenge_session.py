from datetime import datetime
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
    opponent_time: int = 0
    opponent_car_id: int = 0

    @property
    def has_car(self) -> bool:
        return self.car_id > 0 or bool(self.car_name)

    @property
    def is_empty(self) -> bool:
        """Жодного значущого поля — гонка по суті нерозпізнана/непочата."""
        return not (self.track_id > 0 or self.has_car or self.rank > 0
                    or self.time > 0 or self.note or self.bad_timing
                    or self.opponent_time > 0 or self.opponent_car_id > 0)

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
        self.created_at = datetime.now()
        # вибір авто зберігається прямо в draft.car_id (те саме поле, що й ручний
        # ввід у модалці); тут — лише позначка «вибрано вручну» для автопідбору
        self.pinned_races: set[int] = set()

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
            if capture.opponent_time:
                e.opponent_time = capture.opponent_time
            if capture.opponent_car:
                e.opponent_car_id = capture.opponent_car.value
        # порожній результат (напр. розпізнано лише номер гонки чи збережено порожню
        # модалку) має виглядати як нерозпізнана гонка, а не порожня картка
        return e if not e.is_empty else None

    def is_complete(self) -> bool:
        return all(
            (e := self.effective(n)) is not None and e.is_complete
            for n in range(1, RACE_COUNT + 1)
        )

    # --- вибір авто на гонку (пишеться в draft.car_id, як і ручний ввід) ---

    def set_assigned(self, race_number: int, car_id: int | None, pinned: bool = True):
        """Вибрати авто для гонки (None — зняти вибір). Одне авто — одна гонка:
        вибір знімає це авто з іншої НЕзіграної гонки (фактичне авто зіграної
        не чіпаємо — воно вже витрачене)."""
        if car_id is None:
            self._clear_draft_car(race_number)
            self.pinned_races.discard(race_number)
        else:
            for n in range(1, RACE_COUNT + 1):
                if n == race_number:
                    continue
                e = self.effective(n)
                if e is not None and e.car_id == car_id and e.time <= 0:
                    self._clear_draft_car(n)
                    self.pinned_races.discard(n)
            draft = self.drafts.setdefault(race_number, RaceView())
            draft.car_id = car_id
            draft.car_name = ""
            if pinned:
                self.pinned_races.add(race_number)
            else:
                self.pinned_races.discard(race_number)
        self._notify()

    def _clear_draft_car(self, race_number: int):
        draft = self.drafts.get(race_number)
        if draft is not None:
            draft.car_id = 0
            draft.car_name = ""

    def set_assignments(self, assignment: dict[int, int]):
        """Результат автопідбору: пише draft.car_id незапінених і незіграних гонок;
        запінені (ручний вибір) і зіграні (фактичне авто) — недоторкані."""
        for n in range(1, RACE_COUNT + 1):
            if n in self.pinned_races:
                continue
            e = self.effective(n)
            if e is not None and e.time > 0:
                continue
            if n in assignment:
                draft = self.drafts.setdefault(n, RaceView())
                draft.car_id = assignment[n]
                draft.car_name = ""
            else:
                self._clear_draft_car(n)
        self._notify()

    def clear_pins(self):
        """Зняти всі піни (для кнопки «Авто»)."""
        self.pinned_races = set()
        self._notify()

    @property
    def is_disposable(self) -> bool:
        """Немає моїх часів і змістовних ручних правок — сесію можна тихо замінити
        новою (скаутинг: кожен скан кандидата затирає попереднього). Драфт, що
        містить лише вибір авто/рангу (закріплення), одноразовість НЕ скасовує."""
        if any(c.time for c in self.races.values()):
            return False
        return not any(d.time or d.note or d.bad_timing for d in self.drafts.values())

    @property
    def timed_count(self) -> int:
        """Кількість гонок з моїм часом — для заголовка таба відщепленої сесії."""
        return sum(1 for n in range(1, RACE_COUNT + 1)
                   if (e := self.effective(n)) is not None and e.time > 0)

    def clear(self):
        self.races = {}
        self.drafts = {}
        self.last_event = ""
        self.pinned_races = set()
        self._notify()
