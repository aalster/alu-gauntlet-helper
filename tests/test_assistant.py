from types import SimpleNamespace

from alu_gauntlet_helper.models import FieldGuess, RaceCapture, RecognitionResult
from alu_gauntlet_helper.services.assistant import AssistantService, VsSuggestion
from alu_gauntlet_helper.services.challenge_session import ChallengeSessionService


def fake_car(car_id, name="Car", favorite=False):
    return SimpleNamespace(id=car_id, name=name, brand="B", model=name, car_class="S",
                           rank=4000, favorite=favorite, icon="")


class FakeRaces:
    def __init__(self, times_by_car):
        self.times_by_car = times_by_car

    def get_recent_clean_times_by_car(self, track_id, limit=10):
        return self.times_by_car


class FakeCars:
    def __init__(self, cars):
        self.cars = {c.id: c for c in cars}

    def get_by_ids(self, ids):
        return {i: self.cars[i] for i in ids if i in self.cars}


def service(times_by_car, cars=None):
    ids = list(times_by_car)
    return AssistantService(FakeRaces(times_by_car),
                            FakeCars(cars or [fake_car(i) for i in ids]))


def test_beat_count_and_delta_vs_opponent():
    s = service({501: [19000, 19100, 20000, 21000]})  # avg 19775
    [v] = s.suggestions_vs(track_id=1, opponent_time=19950)
    assert v.beat_count == 2      # 19000 і 19100 швидші за 19950
    assert v.sample_count == 4
    assert v.avg_time == 19775
    assert v.delta == 175          # 19950 - 19775 > 0: я в середньому швидший
    assert abs(v.p_smoothed - (2 + 1) / (4 + 2)) < 1e-9


def test_sorted_by_p_then_delta():
    s = service({
        501: [19000] * 10,   # 10/10 швидші, p̂ = 11/12
        502: [19000] * 2,    # 2/2 швидші, p̂ = 3/4 — менше за 9/10 попри "100%"
        503: [30000] * 10,   # 0/10
    })
    result = s.suggestions_vs(1, opponent_time=20000)
    assert [v.car_id for v in result] == [501, 502, 503]


def test_no_opponent_time_sorted_by_favorite_then_avg():
    cars = [fake_car(501), fake_car(502, favorite=True), fake_car(503)]
    s = service({501: [19000], 502: [25000], 503: [18000]}, cars)
    result = s.suggestions_vs(1, opponent_time=None)
    assert [v.car_id for v in result] == [502, 503, 501]  # favorite перший, далі avg
    assert all(v.p_smoothed == 0.5 and v.delta == 0 and v.beat_count == 0 for v in result)


def test_empty_track_gives_empty_list():
    assert service({}).suggestions_vs(1, 20000) == []


# --- Тести для Task 7: auto_pick, win_chance, beat_stats ---


def session_with(*captures):
    s = ChallengeSessionService()
    s.apply(RecognitionResult(screen="test", captures=list(captures)))
    return s


def race(n, track_id, opp_time=None):
    return RaceCapture(race_number=n,
                       track=FieldGuess(value=track_id, score=0.9),
                       opponent_time=opp_time)


class TrackAwareFakeRaces:
    """Різні треки — різні вибірки: {track_id: {car_id: [times]}}."""
    def __init__(self, by_track):
        self.by_track = by_track

    def get_recent_clean_times_by_car(self, track_id, limit=10):
        return self.by_track.get(track_id, {})


def track_service(by_track):
    ids = {c for cars in by_track.values() for c in cars}
    return AssistantService(TrackAwareFakeRaces(by_track),
                            FakeCars([fake_car(i) for i in ids]))


def assigned_car(s, n):
    e = s.effective(n)
    return e.car_id if e else 0


def test_auto_pick_assigns_unpinned():
    svc = track_service({
        7: {501: [19000] * 10, 502: [30000] * 10},
        8: {501: [19000] * 10, 502: [20000] * 10},
    })
    s = session_with(race(1, 7, opp_time=25000), race(2, 8, opp_time=25000))
    svc.auto_pick(s)
    # обидва авто мають призначення, різні; жодне не запінене
    assert {assigned_car(s, 1), assigned_car(s, 2)} == {501, 502}
    assert s.pinned_races == set()


def test_auto_pick_skips_when_pinned_and_not_forced():
    svc = track_service({7: {501: [19000] * 10}})
    s = session_with(race(1, 7, opp_time=25000))
    s.set_assigned(1, 999)  # ручний вибір
    svc.auto_pick(s)
    assert assigned_car(s, 1) == 999  # нічого не змінилось


def test_auto_pick_force_overrides_pins():
    svc = track_service({7: {501: [19000] * 10}})
    s = session_with(race(1, 7, opp_time=25000))
    s.set_assigned(1, 999)
    svc.auto_pick(s, force=True)
    assert assigned_car(s, 1) == 501
    assert s.pinned_races == set()


def test_auto_pick_without_opponent_time_uses_best_avg():
    svc = track_service({7: {501: [21000] * 5, 502: [19000] * 5}})
    s = session_with(race(1, 7))  # трек є, часу суперника немає
    svc.auto_pick(s)
    assert assigned_car(s, 1) == 502  # найкращий avg


def test_auto_pick_excludes_car_driven_in_other_race():
    # авто, фактично проїхане в гонці 1, не пропонується гонці 2, хоч воно й
    # найкраще на її треку — в грі кожне авто їде лише раз
    svc = track_service({
        7: {501: [19000] * 10},
        8: {501: [19000] * 10, 502: [20000] * 10},
    })
    s = session_with(race(1, 7, opp_time=25000), race(2, 8, opp_time=25000))
    s.apply(RecognitionResult(screen="test", captures=[RaceCapture(
        race_number=1, car=FieldGuess(value=501, score=0.9), time=19100)]))
    svc.auto_pick(s)
    assert assigned_car(s, 1) == 501  # фактичне лишилось
    assert assigned_car(s, 2) == 502  # 501 зайняте зіграною гонкою


def test_win_chance_none_without_opponent_times():
    svc = track_service({7: {501: [19000] * 10}})
    s = session_with(race(1, 7))
    assert svc.win_chance(s) is None


def test_win_chance_uses_assigned_cars():
    svc = track_service({7: {501: [19000] * 10}})
    s = session_with(race(1, 7, opp_time=25000))
    svc.auto_pick(s)
    chance = svc.win_chance(s)
    # гонка 1: p̂ = 11/12; гонки 2-5 невідомі (0.5 кожна)
    from alu_gauntlet_helper.services.opponent_picker import prob_at_least
    assert abs(chance - prob_at_least([11 / 12, 0.5, 0.5, 0.5, 0.5], 3)) < 1e-9


def test_win_chance_driven_race_is_exact():
    # зіграна гонка враховується як факт (1.0/0.0), а не як оцінка по вибірці
    svc = track_service({7: {501: [19000] * 10}})
    s = session_with(race(1, 7, opp_time=25000))
    s.apply(RecognitionResult(screen="test", captures=[RaceCapture(
        race_number=1, car=FieldGuess(value=501, score=0.9), time=19100)]))
    from alu_gauntlet_helper.services.opponent_picker import prob_at_least
    assert abs(svc.win_chance(s) - prob_at_least([1.0, 0.5, 0.5, 0.5, 0.5], 3)) < 1e-9


def test_beat_stats():
    svc = track_service({7: {501: [19000, 19100, 21000]}})
    assert svc.beat_stats(7, 501, 20000) == (2, 3)
    assert svc.beat_stats(7, 999, 20000) is None
