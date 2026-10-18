import math
import statistics
from typing import NamedTuple

from alu_gauntlet_helper.services.races import CarSuggestion
from alu_gauntlet_helper.services.challenge_session import RACE_COUNT, WIN_GOALS
from alu_gauntlet_helper.services.opponent_picker import Candidate, pick_cars, win_distribution


# вікно скорів, у якому OCR-кандидати треку вважаються нерозрізненними
# (узгоджено з TrackResolver._AMBIGUITY_WINDOW)
CHIP_SCORE_WINDOW = 0.05
CHIP_LIMIT = 3
# запас діапазону моїх часів при звуженні треку за часом суперника (спека §6)
NARROW_MARGIN = 0.10
# масштаб спаду ваги треку з відстанню часу суперника від моєї медіани:
# точний збіг → 1.0, відхилення 10% → ~0.37, 20% → ~0.02 (узгоджено з ±10% narrow)
TRACK_PROB_TAU = 0.10
# розкид моїх часів на треку одним авто, мс: шанс гонки = Φ(Δ / σ). Константа
# для всіх пар трек+авто (власна σ авто і «типова σ треку» — docs/ideas.md):
# Δ = +1 с → 84%, +2 с → 98%, −1 с → 16%
SIGMA_MS = 1000


def win_prob(delta_ms: int | float) -> float:
    """Шанс побити час суперника за перевагою Δ = opponent − avg (мс):
    нормальна CDF Φ(Δ/σ). Враховує ВЕЛИЧИНУ переваги (пів секунди ≠ десять)
    і не залежить від розміру вибірки — авто з 1 заїздом нічого не виграє."""
    return 0.5 * (1.0 + math.erf(delta_ms / (SIGMA_MS * math.sqrt(2.0))))


# Оцінка заїзду «як проїхав» проти власного середнього (останні ≤10 чистих
# заїздів того ж авто на треку): |d| ≤ 0.2 с — «≈», ≤ 0.5 с — одинарний шеврон,
# далі — подвійний. На треках із широким розкидом моїх часів пороги
# розтягуються до 0.5σ / 1.5σ (робастна σ з MAD, лише при n ≥ 3), щоб
# звичайний «шум» довгого треку не світився як «набагато гірше».
RUN_EQUAL_MS = 200
RUN_STRONG_MS = 500
RUN_EQUAL_SIGMA = 0.5
RUN_STRONG_SIGMA = 1.5
_MAD_TO_SIGMA = 1.4826  # MAD → σ для нормального розподілу


def grade_run(time_ms: int, history: list[int]) -> int | None:
    """−2…+2: наскільки заїзд кращий (+) чи гірший (−) за середнє history;
    0 — приблизно так само. None — немає з чим порівнювати."""
    if not history:
        return None
    d = sum(history) / len(history) - time_ms  # >0 — швидше за середнє
    equal_ms, strong_ms = RUN_EQUAL_MS, RUN_STRONG_MS
    if len(history) >= 3:
        med = statistics.median(history)
        sigma = _MAD_TO_SIGMA * statistics.median(abs(t - med) for t in history)
        equal_ms = max(equal_ms, RUN_EQUAL_SIGMA * sigma)
        strong_ms = max(strong_ms, RUN_STRONG_SIGMA * sigma)
    if abs(d) <= equal_ms:
        return 0
    grade = 1 if abs(d) <= strong_ms else 2
    return grade if d > 0 else -grade


class BeatStats(NamedTuple):
    """Статистика показаного авто проти часу суперника для бейджа «−1.300 7/10»."""
    wins: int   # скільки з вибірки швидші за суперника
    n: int      # розмір вибірки (останні ≤10 чистих заїздів)
    delta: int  # opponent_time − avg, мс; >0 — я в середньому швидший

    @property
    def p(self) -> float:
        return win_prob(self.delta)


def sort_tracks_by_probability(track_ids: list[int], probs: dict[int, float]) -> list[int]:
    """Чипи за спаданням ймовірності; треки без оцінки — в кінці, в поточному порядку."""
    return sorted(track_ids, key=lambda tid: -probs.get(tid, -1.0))


class VsSuggestion(CarSuggestion):
    """Пропозиція авто проти конкретного часу суперника."""
    beat_count: int = 0    # скільки з вибірки швидші за суперника (сирі числа для UI)
    sample_count: int = 0  # розмір вибірки (останні ≤10 чистих заїздів)
    opponent_time: int = 0 # час суперника, мс; 0 — час невідомий
    delta: int = 0         # opponent_time - avg_time, мс; >0 — я в середньому швидший
    p: float = 0.5         # win_prob(delta); 0.5 — час суперника невідомий


def _planned_cars(session, assignment: dict[int, int]) -> dict[int, int]:
    """Авто гонок, якби підбір assignment застосували через set_assignments:
    запінені гонки й гонки з відомим авто/часом лишаються як є."""
    cars = {}
    for n in range(1, RACE_COUNT + 1):
        e = session.effective(n)
        if e is None:
            continue
        if n in session.pinned_races or e.has_car or e.time > 0:
            cars[n] = e.shown_car_id
        else:
            cars[n] = assignment.get(n, 0)
    return cars


class AssistantService:
    """Статистика підбору авто проти суперника. Читає БД через RacesService."""

    def __init__(self, races, cars, tracks=None):
        self.races = races
        self.cars = cars
        self.tracks = tracks

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
                opponent_time=opponent_time or 0,
                delta=(opponent_time - avg) if opponent_time else 0,
                p=win_prob(opponent_time - avg) if opponent_time else 0.5,
            ))
        if opponent_time:
            result.sort(key=lambda v: -v.delta)
        else:
            result.sort(key=lambda v: (not v.car_favorite, v.avg_time))
        return result

    def aggregates_vs(self, track_id: int, opponent_time: int | None):
        """Пари (RaceAggregate, VsSuggestion) у порядку рекомендацій — для UI,
        що показує повну статистику пари трек+авто разом із «N/10 побито»."""
        aggregates = {a.car_id: a for a in self.races.get_aggregates_for_track(track_id)}
        return [(aggregates[v.car_id], v)
                for v in self.suggestions_vs(track_id, opponent_time)
                if v.car_id in aggregates]

    def _estimate_tracks(self, e) -> list[int]:
        """Треки для оцінки шансів гонки: визначений трек (упевнений скан,
        драфт або фікс користувача/звуження) — він сам; невпевнений OCR-трек
        чи трек лише з карти — кандидати для песимістичного min (спека §5)."""
        if e.track_id > 0 and not e.track_uncertain:
            return [e.track_id]
        tracks = self.chip_tracks(e)
        if tracks:
            return tracks
        return [e.track_id] if e.track_id > 0 else []

    def auto_pick(self, session, force: bool = False):
        """Оптимальне призначення авто на гонки з відомим треком.

        force=False — авто-режим після скану: мовчки виходить, якщо гравець уже
        пінув руками. force=True — кнопка «Авто»: знімає піни й перепризначає все."""
        self.resolve_tracks(session)
        if session.pinned_races and not force:
            return
        if force:
            session.clear_pins()
        self._apply_plan(session)

    def set_goal(self, session, goal: int):
        """Перемикач режиму 3/5 · 4/5 · 5/5: перепідбирає авто під нову ціль.
        Ручні піни лишаються — перепідбираються лише незакріплені гонки."""
        session.set_goal(goal)
        self.resolve_tracks(session)
        self._apply_plan(session)

    def _apply_plan(self, session):
        assignment = self._plan(session, session.goal)
        if assignment is not None:
            session.set_assignments(assignment)

    def _plan(self, session, goal: int) -> dict[int, int] | None:
        """Оптимальне призначення під ціль «≥goal перемог»; сесію не змінює.
        None — немає жодної гонки, де є що обирати."""
        race_candidates, fixed = self._pick_inputs(session)
        if not race_candidates:
            return None
        return pick_cars(race_candidates, pinned=fixed, wins_needed=goal)

    def _pick_inputs(self, session) -> tuple[dict[int, list[Candidate]], dict[int, int]]:
        """Кандидати авто по гонках + зафіксовані авто (піни, зіграні, відомі)."""
        race_candidates: dict[int, list[Candidate]] = {}
        fixed: dict[int, int] = {}  # запінені вручну + зіграні (авто вже витрачене)
        for n in range(1, RACE_COUNT + 1):
            e = session.effective(n)
            if e is None:
                continue
            opp = e.opponent_time or None
            if e.time > 0 and e.car_id:
                # зіграна гонка: результат відомий точно — p=1/0 проти часу
                # суперника; єдиний «кандидат» фіксує фактичне авто в переборі
                p = (1.0 if e.time < opp else 0.0) if opp else 0.5
                race_candidates[n] = [Candidate(e.car_id, p, (opp - e.time) if opp else 0)]
                fixed[n] = e.car_id
                continue
            tracks = self._estimate_tracks(e)
            if not tracks:
                continue
            if len(tracks) == 1:
                track_id = tracks[0]
                suggestions = self.suggestions_vs(track_id, opp)
                if e.car_id:
                    # авто заїзду вже відоме (скан вибору авто / модалка), але ще не
                    # зіграно: фіксуємо його, щоб інші гонки його не забрали
                    v = next((x for x in suggestions if x.car_id == e.car_id), None)
                    margin = (v.delta if opp else -v.avg_time) if v else 0
                    race_candidates[n] = [Candidate(e.car_id, v.p if v else 0.5, margin)]
                    fixed[n] = e.car_id
                    continue
                if not suggestions:
                    continue
                # без часу суперника p=0.5 для всіх, margin=-avg: топ-K і тай-брейк
                # природно обирають найкращий avg (спека, розділ 5)
                race_candidates[n] = [
                    Candidate(v.car_id, v.p, v.delta if opp else -v.avg_time)
                    for v in suggestions
                ]
                if n in session.pinned_races and e.suggested_car_id:
                    fixed[n] = e.suggested_car_id
                continue
            # кілька треків-кандидатів — песимістична оцінка min-p (спека §5)
            cands = self._pessimistic_candidates(tracks, opp)
            if e.car_id:
                # відоме авто на невизначеному треку: резервуємо його в переборі
                v = next((c for c in cands if c.car_id == e.car_id), None)
                race_candidates[n] = [v if v is not None else Candidate(e.car_id, 0.5, 0)]
                fixed[n] = e.car_id
                continue
            if cands:
                race_candidates[n] = cands
                if n in session.pinned_races and e.suggested_car_id:
                    fixed[n] = e.suggested_car_id
        return race_candidates, fixed

    def goal_distributions(self, session) -> dict[int, list[float]] | None:
        """{режим k: P(рівно j перемог)} для кнопок 3/5 · 4/5 · 5/5. Активний
        режим — за показаними авто; інші — за підбором, який дав би перемикач
        (з тими самими пінами). None — немає часів суперника."""
        current = self.win_distribution(session)
        if current is None:
            return None
        race_candidates, fixed = self._pick_inputs(session)
        result = {}
        for goal in WIN_GOALS:
            if goal == session.goal or not race_candidates:
                result[goal] = current
                continue
            assignment = pick_cars(race_candidates, pinned=fixed, wins_needed=goal)
            result[goal] = self.win_distribution(session, _planned_cars(session, assignment))
        return result

    def win_distribution(self, session,
                         cars: dict[int, int] | None = None) -> list[float] | None:
        """P(рівно j перемог), j=0..5, за фактичними/рекомендованими авто
        (або за cars {гонка: авто} — гіпотетичний підбір іншого режиму).
        None — немає часів суперника."""
        probs = []
        has_opponent = False
        for n in range(1, RACE_COUNT + 1):
            e = session.effective(n)
            opp = e.opponent_time if e else 0
            car_id = 0 if not e else e.shown_car_id if cars is None else cars.get(n, 0)
            if e and opp and e.time > 0:
                # гонка вже зіграна — результат відомий точно, не оцінка
                has_opponent = True
                probs.append(1.0 if e.time < opp else 0.0)
            elif e and opp and car_id and (tracks := self._estimate_tracks(e)):
                has_opponent = True
                # невизначений трек: песимістичний min по кандидатах (спека §5)
                probs.append(min(
                    stats.p if (stats := self.beat_stats(t, car_id, opp)) else 0.5
                    for t in tracks))
            else:
                if opp:
                    has_opponent = True
                probs.append(0.5)  # невідома гонка — монетка
        return win_distribution(probs) if has_opponent else None

    def beat_stats(self, track_id: int, car_id: int, opponent_time: int) -> BeatStats | None:
        """Δ і «скільки побито з n» показаного авто проти суперника. None — немає заїздів."""
        times = self.races.get_recent_clean_times_by_car(track_id).get(car_id)
        if not times:
            return None
        avg = round(sum(times) / len(times))
        return BeatStats(sum(1 for t in times if t < opponent_time), len(times),
                         opponent_time - avg)

    def run_grade(self, track_id: int, car_id: int, time_ms: int) -> int | None:
        """Оцінка зіграного заїзду проти власної історії авто на треку (grade_run).
        Заїзди сесії ще не в БД (пишуться при «Зберегти»), тож сам себе не бачить."""
        history = self.races.get_recent_clean_times_by_car(track_id).get(car_id)
        return grade_run(time_ms, history or [])

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
                   if top - s <= CHIP_SCORE_WINDOW]
            if e.track_id > 0 and e.track_id not in ids:
                ids.insert(0, e.track_id)  # вибраний фіксом трек — теж чип
            ids = ids[:CHIP_LIMIT]
            return ids if len(ids) > 1 else []
        if e.track_id <= 0 or e.map_id > 0:
            ids = self._map_tracks(e.map_id)
            return ids if len(ids) > 1 else []
        return []

    def track_probabilities(self, track_ids: list[int],
                            opponent_time: int | None) -> dict[int, float]:
        """Частки «наскільки час суперника схожий на трек» для чипів map-гонки.

        Вага треку — exp(−(d/τ)²) від відносної відстані часу суперника до
        медіани моїх останніх 50 чистих часів на треку (будь-яким авто);
        частки нормовані до 1. СУТО візуальний сигнал: на narrow_track,
        win_distribution і підбір авто не впливає. Порожній dict — оцінювати немає
        сенсу: немає часу суперника або дані є менш ніж у двох кандидатів
        (єдиний трек з даними завжди отримував би оманливі 100%)."""
        if not opponent_time:
            return {}
        weights = {}
        for tid in track_ids:
            times = self.races.get_recent_clean_times(tid)
            if not times:
                continue
            median = statistics.median(times)
            d = abs(opponent_time - median) / median
            weights[tid] = math.exp(-(d / TRACK_PROB_TAU) ** 2)
        if len(weights) < 2:
            return {}
        total = sum(weights.values())
        return {tid: w / total for tid, w in weights.items()}

    def track_time_stats(self, track_id: int) -> tuple[int, int] | None:
        """(медіана, кількість) моїх останніх 50 чистих часів трека — для
        тултіпа чипа з ймовірністю. None — заїздів немає."""
        times = self.races.get_recent_clean_times(track_id)
        if not times:
            return None
        return round(statistics.median(times)), len(times)

    def narrow_track(self, track_ids: list[int], opponent_time: int) -> int | None:
        """Звуження: час суперника влучає в діапазон моїх часів (±10%) рівно
        одного кандидата → це він. 0 чи ≥2 влучань, або хоч один кандидат без
        моїх заїздів (його неможливо виключити) → None (спека §6)."""
        ranges = [self.races.get_time_range_for_track(tid) for tid in track_ids]
        if any(rng is None for rng in ranges):
            return None
        hits = [tid for tid, rng in zip(track_ids, ranges)
                if rng[0] * (1 - NARROW_MARGIN) <= opponent_time <= rng[1] * (1 + NARROW_MARGIN)]
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

    def _pessimistic_candidates(self, track_ids: list[int],
                                opp: int | None) -> list["Candidate"]:
        """Кандидати авто для гонки з невизначеним треком: p і маржин авто —
        МІНІМУМ по треках-кандидатах, але тільки по тих, де В МЕНЕ ВЗАГАЛІ є
        заїзди. Трек без жодних даних (жодним авто) у підборі не бере участі:
        інакше він давав би всім авто однакові 0.5, і вибір ставав би довільним
        замість «авто, що підходить під відомі треки карти». Авто без даних на
        треку, де дані є в інших, штрафується як невідоме (0.5/маржин 0) —
        суперник міг вибрати саме цей трек. Це правило лише для ПІДБОРУ;
        win_distribution лишається песимістичним по всіх кандидатах (спека §5)."""
        per_track = {tid: cars
                     for tid in track_ids
                     if (cars := {v.car_id: v for v in self.suggestions_vs(tid, opp)})}
        car_ids = set().union(*per_track.values()) if per_track else set()
        result = []
        for car_id in car_ids:
            ps, margins = [], []
            for cars in per_track.values():
                v = cars.get(car_id)
                ps.append(v.p if v else 0.5)
                margins.append((v.delta if opp else -v.avg_time) if v else 0)
            result.append(Candidate(car_id, min(ps), min(margins)))
        result.sort(key=lambda c: (-c.p, -c.margin))
        return result
