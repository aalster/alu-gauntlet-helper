from types import SimpleNamespace

from alu_gauntlet_helper.models import FieldGuess, RaceCapture, RecognitionResult
from alu_gauntlet_helper.services.assistant import (SIGMA_MS, AssistantService,
                                                    VsSuggestion, win_prob)
from alu_gauntlet_helper.services.opponent_picker import prob_at_least
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


def chance3(svc, session):
    """P(≥3 з 5) за показаними авто; None — немає часів суперника."""
    dist = svc.win_distribution(session)
    return sum(dist[3:]) if dist else None


def service(times_by_car, cars=None):
    ids = list(times_by_car)
    return AssistantService(FakeRaces(times_by_car),
                            FakeCars(cars or [fake_car(i) for i in ids]))


def test_win_prob_is_normal_cdf_of_delta_over_sigma():
    assert SIGMA_MS == 1000
    assert abs(win_prob(0) - 0.5) < 1e-9
    assert abs(win_prob(SIGMA_MS) - 0.8413) < 1e-3     # Φ(1)
    assert abs(win_prob(-SIGMA_MS) - 0.1587) < 1e-3    # Φ(−1)
    assert abs(win_prob(2 * SIGMA_MS) - 0.9772) < 1e-3  # Φ(2)
    assert win_prob(10 * SIGMA_MS) > 0.9999


def test_beat_count_and_delta_vs_opponent():
    s = service({501: [19000, 19100, 20000, 21000]})  # avg 19775
    [v] = s.suggestions_vs(track_id=1, opponent_time=19950)
    assert v.beat_count == 2      # 19000 і 19100 швидші за 19950
    assert v.sample_count == 4
    assert v.avg_time == 19775
    assert v.delta == 175          # 19950 - 19775 > 0: я в середньому швидший
    # шанс гонки — з Δ, а не з лічильника 2/4
    assert abs(v.p - win_prob(175)) < 1e-9


def test_sorted_by_delta_only():
    s = service({
        501: [19000] * 10,   # Δ = +1000
        502: [18500] * 2,    # Δ = +1500 — найбільша перевага, попри 2 заїзди
        503: [30000] * 10,   # Δ = −10000
    })
    result = s.suggestions_vs(1, opponent_time=20000)
    assert [v.car_id for v in result] == [502, 501, 503]


def test_slow_car_with_one_run_does_not_beat_slow_car_with_ten():
    # стара лапласова оцінка тягнула 0/1 до 50% і ставила таке авто вище за
    # 0/10; тепер обидва оцінюються лише за Δ
    s = service({
        501: [21000] * 10,   # Δ = −1000, 0/10
        502: [25000],        # Δ = −5000, 0/1
    })
    result = s.suggestions_vs(1, opponent_time=20000)
    assert [v.car_id for v in result] == [501, 502]
    assert result[0].p > result[1].p


def test_same_delta_same_p_regardless_of_sample_size():
    s = service({501: [19000] * 10, 502: [19000]})
    a, b = s.suggestions_vs(1, opponent_time=20000)
    assert abs(a.p - b.p) < 1e-9


def test_no_opponent_time_sorted_by_favorite_then_avg():
    cars = [fake_car(501), fake_car(502, favorite=True), fake_car(503)]
    s = service({501: [19000], 502: [25000], 503: [18000]}, cars)
    result = s.suggestions_vs(1, opponent_time=None)
    assert [v.car_id for v in result] == [502, 503, 501]  # favorite перший, далі avg
    assert all(v.p == 0.5 and v.delta == 0 and v.beat_count == 0 for v in result)


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
    # показане авто: фактичне (car_id) або рекомендоване (suggested_car_id)
    e = s.effective(n)
    return e.shown_car_id if e else 0


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
    # призначення — рекомендації: модель заїзду лишається без авто
    assert s.effective(1).car_id == 0 and s.effective(2).car_id == 0


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


def test_auto_pick_fixes_scanned_car_without_time():
    # незіграна гонка з відомим авто (скан вибору авто): авто фіксується, не
    # пропонується іншим гонкам, а рекомендація для цієї гонки не пишеться
    svc = track_service({
        7: {501: [19000] * 10},
        8: {501: [19000] * 10, 502: [20000] * 10},
    })
    s = session_with(race(1, 7, opp_time=25000), race(2, 8, opp_time=25000))
    s.apply(RecognitionResult(screen="test", captures=[RaceCapture(
        race_number=1, car=FieldGuess(value=501, score=0.9))]))  # авто без часу
    svc.auto_pick(s)
    e1 = s.effective(1)
    assert e1.car_id == 501 and e1.suggested_car_id == 0
    assert assigned_car(s, 2) == 502  # 501 зайняте гонкою 1


def test_win_chance_none_without_opponent_times():
    svc = track_service({7: {501: [19000] * 10}})
    s = session_with(race(1, 7))
    assert chance3(svc, s) is None


def test_win_chance_uses_assigned_cars():
    svc = track_service({7: {501: [19000] * 10}})
    s = session_with(race(1, 7, opp_time=25000))
    svc.auto_pick(s)
    chance = chance3(svc, s)
    # гонка 1: Δ = 25000 − 19000 = +6000 → Φ(6) ≈ 1; гонки 2-5 невідомі (0.5)
    assert abs(chance - prob_at_least([win_prob(6000), 0.5, 0.5, 0.5, 0.5], 3)) < 1e-9


def test_win_chance_reflects_delta_magnitude():
    # головна претензія до старої оцінки: пів секунди і десять секунд
    # переваги давали однакові 92% при 10/10
    small = track_service({7: {501: [24500] * 10}})   # Δ = +500
    big = track_service({7: {501: [15000] * 10}})     # Δ = +10000
    s1 = session_with(race(1, 7, opp_time=25000))
    s2 = session_with(race(1, 7, opp_time=25000))
    small.auto_pick(s1)
    big.auto_pick(s2)
    assert chance3(big, s2) > chance3(small, s1) + 0.05


def test_win_distribution_none_without_opponent_times():
    svc = track_service({7: {501: [19000] * 10}})
    s = session_with(race(1, 7))
    assert svc.win_distribution(s) is None


def test_win_distribution_exact_for_assigned_cars():
    svc = track_service({7: {501: [19000] * 10}})
    s = session_with(race(1, 7, opp_time=25000))
    svc.auto_pick(s)
    dist = svc.win_distribution(s)
    from alu_gauntlet_helper.services.opponent_picker import win_distribution
    expected = win_distribution([win_prob(6000), 0.5, 0.5, 0.5, 0.5])
    assert all(abs(a - b) < 1e-9 for a, b in zip(dist, expected, strict=True))


def test_win_chance_driven_race_is_exact():
    # зіграна гонка враховується як факт (1.0/0.0), а не як оцінка по вибірці
    svc = track_service({7: {501: [19000] * 10}})
    s = session_with(race(1, 7, opp_time=25000))
    s.apply(RecognitionResult(screen="test", captures=[RaceCapture(
        race_number=1, car=FieldGuess(value=501, score=0.9), time=19100)]))
    assert abs(chance3(svc, s) - prob_at_least([1.0, 0.5, 0.5, 0.5, 0.5], 3)) < 1e-9


def test_beat_stats_with_delta():
    svc = track_service({7: {501: [19000, 19100, 21000]}})  # avg 19700
    stats = svc.beat_stats(7, 501, 20000)
    assert (stats.wins, stats.n) == (2, 3)
    assert stats.delta == 300  # 20000 − 19700
    assert abs(stats.p - win_prob(300)) < 1e-9
    assert svc.beat_stats(7, 999, 20000) is None


# --- Етап 3: chip_tracks / narrow_track / resolve_tracks -------------------


class FakeTracks:
    """{map_id: [track_id, ...]} — сигнатура TracksService.autocomplete."""
    def __init__(self, by_map):
        self.by_map = by_map

    def autocomplete(self, query, map_id=None):
        return [SimpleNamespace(id=t) for t in self.by_map.get(map_id, [])]


class RangeFakeRaces(TrackAwareFakeRaces):
    """+ діапазони часів треків: {track_id: (lo, hi)};
    + чисті часи трека всіма авто: {track_id: [times]}."""
    def __init__(self, by_track, ranges=None, clean_times=None):
        super().__init__(by_track)
        self.ranges = ranges or {}
        self.clean_times = clean_times or {}

    def get_time_range_for_track(self, track_id):
        return self.ranges.get(track_id)

    def get_recent_clean_times(self, track_id, limit=50):
        return self.clean_times.get(track_id, [])[:limit]


def stage3_service(by_track=None, ranges=None, by_map=None, clean_times=None):
    by_track = by_track or {}
    ids = {c for cars in by_track.values() for c in cars}
    return AssistantService(RangeFakeRaces(by_track, ranges, clean_times),
                            FakeCars([fake_car(i) for i in ids]),
                            FakeTracks(by_map or {}))


def map_race(n, map_id, opp_time=None):
    return RaceCapture(race_number=n,
                       map=FieldGuess(value=map_id, score=0.9),
                       opponent_time=opp_time)


def test_chip_tracks_from_map():
    svc = stage3_service(by_map={5: [21, 22]})
    s = session_with(map_race(1, 5))
    assert svc.chip_tracks(s.effective(1)) == [21, 22]


def test_chip_tracks_from_ocr_candidates_window():
    svc = stage3_service()
    s = ChallengeSessionService()
    c = RaceCapture(race_number=1,
                    track=FieldGuess(value=41, score=0.6,
                                     candidates=[(41, 0.93), (42, 0.91), (43, 0.70)]))
    s.apply(RecognitionResult(screen="test", captures=[c]))
    # 43 відпадає: далі за вікно 0.05 від топового 0.93
    assert svc.chip_tracks(s.effective(1)) == [41, 42]


def test_chip_tracks_empty_when_confident():
    svc = stage3_service(by_map={5: [21, 22]})
    s = session_with(race(1, 7))  # упевнений трек — без чипів
    assert svc.chip_tracks(s.effective(1)) == []


def test_narrow_track_unique_hit():
    svc = stage3_service(ranges={21: (19000, 21000), 22: (30000, 33000)})
    assert svc.narrow_track([21, 22], 20000) == 21
    assert svc.narrow_track([21, 22], 31000) == 22


def test_narrow_track_margin_10_percent():
    svc = stage3_service(ranges={21: (20000, 21000)})
    assert svc.narrow_track([21], 18000) == 21   # 18000 == 20000*0.9 — на межі
    assert svc.narrow_track([21], 17999) is None


def test_narrow_track_ambiguous_or_missed():
    svc = stage3_service(ranges={21: (19000, 25000), 22: (20000, 26000)})
    assert svc.narrow_track([21, 22], 21000) is None  # в обидва — невизначено
    assert svc.narrow_track([21, 22], 50000) is None  # в жоден
    # кандидат без моїх заїздів: виключити його неможливо → невизначено (спека §6)
    svc2 = stage3_service(ranges={21: (19000, 25000)})
    assert svc2.narrow_track([21, 22], 21000) is None


def test_resolve_tracks_sets_inferred_fix():
    svc = stage3_service(ranges={21: (19000, 21000), 22: (30000, 33000)},
                         by_map={5: [21, 22]})
    s = session_with(map_race(1, 5, opp_time=20000))
    svc.resolve_tracks(s)
    e = s.effective(1)
    assert e.track_id == 21 and e.track_inferred


def test_resolve_tracks_single_track_map():
    svc = stage3_service(by_map={5: [21]})
    s = session_with(map_race(1, 5))
    svc.resolve_tracks(s)
    assert s.effective(1).track_id == 21


def test_resolve_tracks_keeps_manual_fix():
    svc = stage3_service(ranges={21: (19000, 21000), 22: (30000, 33000)},
                         by_map={5: [21, 22]})
    s = session_with(map_race(1, 5, opp_time=20000))
    s.set_track_fix(1, 22)  # ручний вибір користувача
    svc.resolve_tracks(s)
    assert s.effective(1).track_id == 22 and not s.effective(1).track_inferred


def test_auto_pick_runs_resolve_tracks():
    svc = stage3_service(by_track={21: {501: [19000] * 10}},
                         ranges={21: (19000, 21000), 22: (30000, 33000)},
                         by_map={5: [21, 22]})
    s = session_with(map_race(1, 5, opp_time=20000))
    svc.auto_pick(s)
    e = s.effective(1)
    assert e.track_id == 21 and e.suggested_car_id == 501


# --- Етап 3: песимістична оцінка min-p̂ по треках-кандидатах ----------------


def test_auto_pick_pessimistic_min_over_candidates():
    # авто 501 сильне лише на треку 21 (на 22 даних немає → 0.5);
    # авто 502 стабільне на обох → песимістично краще, його і беремо
    svc = stage3_service(
        by_track={21: {501: [19000] * 10, 502: [21000] * 10},
                  22: {502: [21500] * 10}},
        ranges={21: (19000, 25000), 22: (20000, 26000)},  # звуження не спрацює
        by_map={5: [21, 22]})
    s = session_with(map_race(1, 5, opp_time=24000))
    svc.auto_pick(s)
    assert s.effective(1).suggested_car_id == 502


def test_auto_pick_pessimistic_without_opponent_time():
    # без часу суперника: p=0.5 всюди, margin = min(-avg) — найкращий гірший avg
    svc = stage3_service(
        by_track={21: {501: [19000] * 5, 502: [20000] * 5},
                  22: {501: [30000] * 5, 502: [20500] * 5}},
        by_map={5: [21, 22]})
    s = session_with(map_race(1, 5))
    svc.auto_pick(s)
    assert s.effective(1).suggested_car_id == 502  # min(-avg): 502 стабільніше


def test_win_chance_pessimistic_min():
    svc = stage3_service(
        by_track={21: {501: [19000] * 10}},  # на 22 даних немає
        ranges={21: (19000, 25000), 22: (20000, 26000)},
        by_map={5: [21, 22]})
    s = session_with(map_race(1, 5, opp_time=24000))
    svc.auto_pick(s)
    assert s.effective(1).suggested_car_id == 501
    # p гонки 1 = min(Φ(5) на треку 21, 0.5 на 22) = 0.5; решта — монетки
    expected = prob_at_least([0.5, 0.5, 0.5, 0.5, 0.5], 3)
    assert abs(chance3(svc, s) - expected) < 1e-9


# --- фікси фінального ревʼю: песимізм для невпевненого OCR-треку та ін. ----


def uncertain_race(n, opp_time=None, best=41, second=42):
    return RaceCapture(
        race_number=n,
        track=FieldGuess(value=best, score=0.6, candidates=[(best, 0.93), (second, 0.91)]),
        opponent_time=opp_time,
    )


def test_auto_pick_pessimistic_for_uncertain_ocr_track():
    # UI каже «не впевнені, обери трек» — оцінка теж має бути песимістичною
    svc = stage3_service(by_track={41: {501: [19000] * 10, 502: [21000] * 10},
                                   42: {502: [21500] * 10}})
    s = session_with(uncertain_race(1, opp_time=24000))
    svc.auto_pick(s)
    assert s.effective(1).suggested_car_id == 502  # стабільний на обох кандидатах


def test_manual_chip_fix_returns_optimistic_estimate():
    # ручний вибір треку чипом — довіряємо йому, оцінка по вибраному треку
    svc = stage3_service(by_track={41: {501: [19000] * 10, 502: [21000] * 10},
                                   42: {502: [21500] * 10}})
    s = session_with(uncertain_race(1, opp_time=24000))
    s.set_track_fix(1, 41)
    svc.auto_pick(s)
    assert s.effective(1).suggested_car_id == 501  # найкращий саме на 41


def test_win_chance_pessimistic_for_uncertain_ocr_track():
    svc = stage3_service(by_track={41: {501: [19000] * 10}})  # на 42 даних немає
    s = session_with(uncertain_race(1, opp_time=24000))
    svc.auto_pick(s)
    assert s.effective(1).suggested_car_id == 501
    expected = prob_at_least([0.5, 0.5, 0.5, 0.5, 0.5], 3)  # min(Φ(5), 0.5) = 0.5
    assert abs(chance3(svc, s) - expected) < 1e-9


def test_chip_limit_holds_after_fix_insert():
    svc = stage3_service()
    s = ChallengeSessionService()
    c = RaceCapture(race_number=1,
                    track=FieldGuess(value=41, score=0.6,
                                     candidates=[(41, 0.93), (42, 0.91), (43, 0.90)]))
    s.apply(RecognitionResult(screen="test", captures=[c]))
    s.set_track_fix(1, 44)  # трек поза кандидатами (наприклад, з Edit-діалогу раніше)
    assert len(svc.chip_tracks(s.effective(1))) <= 3


def test_auto_pick_reserves_known_car_on_unknown_track():
    # авто вже вибране (драфт) на map-гонці без треку — інші гонки його не беруть
    from alu_gauntlet_helper.services.races import RaceView
    svc = stage3_service(by_track={21: {501: [19000] * 10, 502: [25000] * 10}},
                         by_map={5: [21, 22]})
    s = session_with(map_race(1, 5, opp_time=24000), race(2, 21, opp_time=24000))
    s.set_draft(1, RaceView(car_id=501))
    svc.auto_pick(s)
    assert s.effective(2).suggested_car_id == 502  # 501 зарезервоване гонкою 1


# --- трек-кандидат без жодних даних не «зрівнює» всі авто --------------------


def test_track_without_any_data_ignored_in_selection():
    # трек 22 без жодного заїзду: у підборі не бере участі — інакше всі авто
    # мали б p=0.5/margin=0 і вибір був би довільним; перемагає авто, що
    # найкраще на відомому треку карти
    svc = stage3_service(by_track={21: {501: [26000] * 10, 502: [19000] * 10}},
                         by_map={5: [21, 22]})
    s = session_with(map_race(1, 5, opp_time=27000))
    svc.auto_pick(s)
    # 502 має Δ = 8000 проти 1000 у 501 (порядок id навмисне протилежний
    # «першому» в set)
    assert s.effective(1).suggested_car_id == 502


# --- ймовірність треку за часом суперника (map-кейс, лише чипи) -------------


def test_track_probabilities_closer_median_dominates():
    svc = stage3_service(clean_times={21: [19800, 20000, 20200],
                                      22: [29800, 30000, 30200]})
    probs = svc.track_probabilities([21, 22], 20500)
    assert abs(sum(probs.values()) - 1.0) < 1e-9
    assert probs[21] > 0.99


def test_track_probabilities_exact_match_beats_near_track():
    svc = stage3_service(clean_times={21: [20000] * 3, 22: [22000] * 3})
    probs = svc.track_probabilities([21, 22], 20000)
    assert probs[21] > probs[22]
    assert probs[21] > 0.6


def test_track_probabilities_empty_without_opponent_time():
    svc = stage3_service(clean_times={21: [20000], 22: [21000]})
    assert svc.track_probabilities([21, 22], 0) == {}


def test_track_probabilities_empty_when_less_than_two_tracks_have_data():
    # єдиний трек з даними показував би оманливі «100%»
    svc = stage3_service(clean_times={21: [20000] * 5})
    assert svc.track_probabilities([21, 22], 20000) == {}
    assert stage3_service().track_probabilities([21, 22], 20000) == {}


def test_track_probabilities_median_ignores_outlier():
    # викид 99999 зіпсував би середнє (і трек 22 виграв би), медіану — ні
    svc = stage3_service(clean_times={21: [19900, 20000, 20100, 20200, 99999],
                                      22: [20600] * 5})
    probs = svc.track_probabilities([21, 22], 20050)
    assert probs[21] > probs[22]


def test_track_time_stats_median_and_count():
    svc = stage3_service(clean_times={21: [19900, 20000, 99999]})
    assert svc.track_time_stats(21) == (20000, 3)   # медіана, не середнє
    assert svc.track_time_stats(22) is None         # немає заїздів


def test_sort_tracks_by_probability_keeps_no_data_last():
    from alu_gauntlet_helper.services.assistant import sort_tracks_by_probability
    ids = [21, 22, 23, 24]
    probs = {22: 0.7, 24: 0.3}
    assert sort_tracks_by_probability(ids, probs) == [22, 24, 21, 23]
    assert sort_tracks_by_probability(ids, {}) == ids


def test_unknown_car_on_data_track_still_penalized():
    # авто, відоме лише на одному з треків З ДАНИМИ, штрафується: суперник міг
    # вибрати другий трек, де про це авто нічого не відомо
    svc = stage3_service(
        by_track={21: {501: [20000] * 10, 502: [21000] * 10},
                  22: {502: [21500] * 10}},  # 501 на треку 22 невідоме
        by_map={5: [21, 22, 23]})            # 23 — без даних узагалі, ігнорується
    s = session_with(map_race(1, 5, opp_time=27000))
    svc.auto_pick(s)
    assert s.effective(1).suggested_car_id == 502  # стабільний на обох треках з даними


# --- режими підбору 3/5 · 4/5 · 5/5 -----------------------------------------
# гонки 3–5 зіграні (2 перемоги, програш), вирішують гонки 1–2. Авто 501
# надійне на треку 7 (p≈0.99) і посереднє на 8 (≈0.6); 502 — ≈0.9 і ≈0.1.


def goal_scenario():
    svc = track_service({7: {501: [22674] * 10, 502: [23718] * 10},
                         8: {501: [24747] * 10, 502: [26282] * 10}})
    s = session_with(race(1, 7, 25000), race(2, 8, 25000), race(3, 9, 25000),
                     race(4, 9, 25000), race(5, 9, 25000))
    s.apply(RecognitionResult(screen="test", captures=[
        RaceCapture(race_number=3, car=FieldGuess(value=601, score=0.9), time=20000),
        RaceCapture(race_number=4, car=FieldGuess(value=602, score=0.9), time=20000),
        RaceCapture(race_number=5, car=FieldGuess(value=603, score=0.9), time=30000)]))
    return svc, s


def test_new_session_goal_is_5_and_spreads_cars():
    svc, s = goal_scenario()
    assert s.goal == 5
    svc.auto_pick(s)
    # 5/5 недосяжне → максимум очікуваних перемог: 0.9 + 0.6 > 0.99 + 0.1
    assert (assigned_car(s, 1), assigned_car(s, 2)) == (502, 501)


def test_set_goal_repicks_for_new_target():
    svc, s = goal_scenario()
    svc.auto_pick(s)
    svc.set_goal(s, 3)
    assert s.goal == 3
    # 3/5 = ще ≥1 перемога: надійна гонка 1 вигідніша
    assert (assigned_car(s, 1), assigned_car(s, 2)) == (501, 502)
    assert s.pinned_races == set()


def test_set_goal_keeps_pins():
    svc, s = goal_scenario()
    s.set_assigned(2, 999)  # ручний вибір
    svc.set_goal(s, 3)
    assert assigned_car(s, 2) == 999
    assert s.pinned_races == {2}
    assert assigned_car(s, 1) == 501  # незапінена гонка перепідібрана


def test_goal_distributions_show_tradeoff():
    svc, s = goal_scenario()
    svc.auto_pick(s)  # режим 5/5
    dists = svc.goal_distributions(s)
    assert set(dists) == {3, 4, 5}
    # активний режим — за показаними авто
    assert dists[5] == svc.win_distribution(s)
    # підбір під 3/5 надійніший для ≥3, але програє в ≥4
    assert sum(dists[3][3:]) > sum(dists[5][3:])
    assert sum(dists[3][4:]) < sum(dists[5][4:])


def test_goal_distributions_none_without_opponent_times():
    svc = track_service({7: {501: [19000] * 10}})
    s = session_with(race(1, 7))
    assert svc.goal_distributions(s) is None


def test_clear_resets_goal():
    s = ChallengeSessionService()
    s.set_goal(3)
    s.clear()
    assert s.goal == 5


# --- автоперемикання цілі, коли вона стала недосяжною ----------------------

def test_reconcile_goal_switches_after_loss_and_repicks():
    svc = track_service({1: {1: [19000]}, 2: {2: [19000]}, 3: {3: [19000]}})
    s = session_with(race(1, 1, 20000), race(2, 2, 20000), race(3, 3, 20000))
    svc.auto_pick(s)
    assert s.goal == 5
    s.apply(RecognitionResult(screen="test", captures=[
        RaceCapture(race_number=1, time=21000, car=FieldGuess(value=1, score=0.9))]))
    svc.reconcile_goal(s)
    assert s.goal == 4
    assert assigned_car(s, 2) and assigned_car(s, 3)  # підбір перерахований


def test_reconcile_goal_keeps_reachable_goal():
    svc = track_service({1: {1: [19000]}})
    s = session_with(race(1, 1, 20000))
    s.set_goal(4)
    svc.reconcile_goal(s)
    assert s.goal == 4
