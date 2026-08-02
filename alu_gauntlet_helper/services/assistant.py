from alu_gauntlet_helper.services.races import CarSuggestion
from alu_gauntlet_helper.services.challenge_session import RACE_COUNT
from alu_gauntlet_helper.services.opponent_picker import Candidate, pick_cars, prob_at_least


def laplace(wins: int, n: int) -> float:
    """Згладжена ймовірність (wins+1)/(n+2): 2/2 (~0.75) не переважає 9/10 (~0.83)."""
    return (wins + 1) / (n + 2)


class VsSuggestion(CarSuggestion):
    """Пропозиція авто проти конкретного часу суперника."""
    beat_count: int = 0    # скільки з вибірки швидші за суперника (сирі числа для UI)
    sample_count: int = 0  # розмір вибірки (останні ≤10 чистих заїздів)
    delta: int = 0         # opponent_time - avg_time, мс; >0 — я в середньому швидший
    p_smoothed: float = 0.5


class AssistantService:
    """Статистика підбору авто проти суперника. Читає БД через RacesService."""

    def __init__(self, races, cars):
        self.races = races
        self.cars = cars

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

    def auto_pick(self, session, force: bool = False):
        """Оптимальне призначення авто на гонки з відомим треком.

        force=False — авто-режим після скану: мовчки виходить, якщо гравець уже
        пінув руками. force=True — кнопка «Авто»: знімає піни й перепризначає все."""
        if session.pinned_races and not force:
            return
        if force:
            session.clear_pins()
        race_candidates: dict[int, list[Candidate]] = {}
        fixed: dict[int, int] = {}  # запінені вручну + зіграні (авто вже витрачене)
        for n in range(1, RACE_COUNT + 1):
            e = session.effective(n)
            if e is None or e.track_id <= 0:
                continue
            opp = e.opponent_time or None
            if e.time > 0 and e.car_id:
                # зіграна гонка: результат відомий точно — p=1/0 проти часу
                # суперника; єдиний «кандидат» фіксує фактичне авто в переборі
                p = (1.0 if e.time < opp else 0.0) if opp else 0.5
                race_candidates[n] = [Candidate(e.car_id, p, (opp - e.time) if opp else 0)]
                fixed[n] = e.car_id
                continue
            suggestions = self.suggestions_vs(e.track_id, opp)
            if not suggestions:
                continue
            # без часу суперника p=0.5 для всіх, margin=-avg: топ-K і тай-брейк
            # природно обирають найкращий avg (спека, розділ 5)
            race_candidates[n] = [
                Candidate(v.car_id, v.p_smoothed, v.delta if opp else -v.avg_time)
                for v in suggestions
            ]
            if n in session.pinned_races and e.car_id:
                fixed[n] = e.car_id
        if not race_candidates:
            return
        session.set_assignments(pick_cars(race_candidates, pinned=fixed))

    def win_chance(self, session) -> float | None:
        """P(виграти ≥3 з 5) за вибраними/фактичними авто. None — немає часів суперника."""
        probs = []
        has_opponent = False
        for n in range(1, RACE_COUNT + 1):
            e = session.effective(n)
            opp = e.opponent_time if e else 0
            car_id = e.car_id if e else 0
            if e and opp and e.time > 0:
                # гонка вже зіграна — результат відомий точно, не оцінка
                has_opponent = True
                probs.append(1.0 if e.time < opp else 0.0)
            elif e and opp and car_id and e.track_id > 0:
                has_opponent = True
                stats = self.beat_stats(e.track_id, car_id, opp)
                probs.append(laplace(*stats) if stats else 0.5)
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
