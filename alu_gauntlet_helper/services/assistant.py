import math
import statistics

from alu_gauntlet_helper.services.races import CarSuggestion
from alu_gauntlet_helper.services.challenge_session import RACE_COUNT
from alu_gauntlet_helper.services.opponent_picker import Candidate, pick_cars, prob_at_least


# вікно скорів, у якому OCR-кандидати треку вважаються нерозрізненними
# (узгоджено з TrackResolver._AMBIGUITY_WINDOW)
CHIP_SCORE_WINDOW = 0.05
CHIP_LIMIT = 3
# запас діапазону моїх часів при звуженні треку за часом суперника (спека §6)
NARROW_MARGIN = 0.10
# масштаб спаду ваги треку з відстанню часу суперника від моєї медіани:
# точний збіг → 1.0, відхилення 10% → ~0.37, 20% → ~0.02 (узгоджено з ±10% narrow)
TRACK_PROB_TAU = 0.10


def laplace(wins: int, n: int) -> float:
    """Згладжена ймовірність (wins+1)/(n+2): 2/2 (~0.75) не переважає 9/10 (~0.83)."""
    return (wins + 1) / (n + 2)


def sort_tracks_by_probability(track_ids: list[int], probs: dict[int, float]) -> list[int]:
    """Чипи за спаданням ймовірності; треки без оцінки — в кінці, в поточному порядку."""
    return sorted(track_ids, key=lambda tid: -probs.get(tid, -1.0))


class VsSuggestion(CarSuggestion):
    """Пропозиція авто проти конкретного часу суперника."""
    beat_count: int = 0    # скільки з вибірки швидші за суперника (сирі числа для UI)
    sample_count: int = 0  # розмір вибірки (останні ≤10 чистих заїздів)
    delta: int = 0         # opponent_time - avg_time, мс; >0 — я в середньому швидший
    p_smoothed: float = 0.5


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
                delta=(opponent_time - avg) if opponent_time else 0,
                p_smoothed=laplace(beat, len(times)) if opponent_time else 0.5,
            ))
        if opponent_time:
            result.sort(key=lambda v: (-v.p_smoothed, -v.delta))
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
                    race_candidates[n] = [Candidate(e.car_id, v.p_smoothed if v else 0.5, margin)]
                    fixed[n] = e.car_id
                    continue
                if not suggestions:
                    continue
                # без часу суперника p=0.5 для всіх, margin=-avg: топ-K і тай-брейк
                # природно обирають найкращий avg (спека, розділ 5)
                race_candidates[n] = [
                    Candidate(v.car_id, v.p_smoothed, v.delta if opp else -v.avg_time)
                    for v in suggestions
                ]
                if n in session.pinned_races and e.suggested_car_id:
                    fixed[n] = e.suggested_car_id
                continue
            # кілька треків-кандидатів — песимістична оцінка min-p̂ (спека §5)
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
        if not race_candidates:
            return
        session.set_assignments(pick_cars(race_candidates, pinned=fixed))

    def win_chance(self, session) -> float | None:
        """P(виграти ≥3 з 5) за фактичними/рекомендованими авто. None — немає часів суперника."""
        probs = []
        has_opponent = False
        for n in range(1, RACE_COUNT + 1):
            e = session.effective(n)
            opp = e.opponent_time if e else 0
            car_id = e.shown_car_id if e else 0
            if e and opp and e.time > 0:
                # гонка вже зіграна — результат відомий точно, не оцінка
                has_opponent = True
                probs.append(1.0 if e.time < opp else 0.0)
            elif e and opp and car_id and (tracks := self._estimate_tracks(e)):
                has_opponent = True
                # невизначений трек: песимістичний min по кандидатах (спека §5)
                probs.append(min(
                    laplace(*stats) if (stats := self.beat_stats(t, car_id, opp))
                    else 0.5
                    for t in tracks))
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
        win_chance і підбір авто не впливає. Порожній dict — оцінювати немає
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
        """Кандидати авто для гонки з невизначеним треком: p̂ і маржин авто —
        МІНІМУМ по треках-кандидатах, але тільки по тих, де В МЕНЕ ВЗАГАЛІ є
        заїзди. Трек без жодних даних (жодним авто) у підборі не бере участі:
        інакше він давав би всім авто однакові 0.5, і вибір ставав би довільним
        замість «авто, що підходить під відомі треки карти». Авто без даних на
        треку, де дані є в інших, штрафується як невідоме (0.5/маржин 0) —
        суперник міг вибрати саме цей трек. Це правило лише для ПІДБОРУ;
        win_chance лишається песимістичним по всіх кандидатах (спека §5)."""
        per_track = {tid: cars
                     for tid in track_ids
                     if (cars := {v.car_id: v for v in self.suggestions_vs(tid, opp)})}
        car_ids = set().union(*per_track.values()) if per_track else set()
        result = []
        for car_id in car_ids:
            ps, margins = [], []
            for cars in per_track.values():
                v = cars.get(car_id)
                ps.append(v.p_smoothed if v else 0.5)
                margins.append((v.delta if opp else -v.avg_time) if v else 0)
            result.append(Candidate(car_id, min(ps), min(margins)))
        result.sort(key=lambda c: (-c.p, -c.margin))
        return result
