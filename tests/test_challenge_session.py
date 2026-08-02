from alu_gauntlet_helper.models import FieldGuess, RaceCapture, RecognitionResult
from alu_gauntlet_helper.services.challenge_session import ChallengeSessionService, EffectiveRace
from alu_gauntlet_helper.services.races import RaceView


def capture(n, track_score=None, car_score=None, rank=None, time=None):
    return RaceCapture(
        race_number=n,
        track=FieldGuess(value=10 + n, score=track_score) if track_score is not None else None,
        car=FieldGuess(value=20 + n, score=car_score) if car_score is not None else None,
        rank=rank,
        time=time,
    )


def result(*captures):
    return RecognitionResult(screen="test", captures=list(captures))


def test_apply_creates_race_entry():
    s = ChallengeSessionService()
    s.apply(result(capture(1, track_score=0.9, time=22797)))
    assert s.races[1].track.value == 11
    assert s.races[1].time == 22797


def test_merge_keeps_higher_confidence_field():
    s = ChallengeSessionService()
    s.apply(result(capture(1, track_score=0.9)))
    low = capture(1, track_score=0.5)
    # інший value, щоб перевірити, що merge справді залишив СТАРЕ значення
    low.track = FieldGuess(value=99, score=0.5)
    s.apply(result(low))
    assert s.races[1].track.value == 11  # стара впевненіша — лишилась


def test_merge_overwrites_with_higher_confidence():
    s = ChallengeSessionService()
    s.apply(result(capture(1, track_score=0.5)))
    high = capture(1)
    high.track = FieldGuess(value=99, score=0.95)
    s.apply(result(high))
    assert s.races[1].track.value == 99


def test_merge_fills_missing_scalar_fields():
    s = ChallengeSessionService()
    s.apply(result(capture(2, time=21000)))
    s.apply(result(capture(2, rank=4045)))
    assert s.races[2].time == 21000
    assert s.races[2].rank == 4045


def test_is_complete_requires_track_car_time_for_all_five():
    s = ChallengeSessionService()
    for n in range(1, 5):
        s.apply(result(capture(n, track_score=0.9, car_score=0.9, time=20000)))
    assert not s.is_complete()
    s.apply(result(capture(5, track_score=0.9, car_score=0.9, time=20000)))
    assert s.is_complete()


def test_apply_empty_result_is_noop():
    s = ChallengeSessionService()
    events = []
    s.add_listener(lambda: events.append(1))
    s.apply(result())
    assert s.races == {} and events == []


def test_clear_and_listeners():
    s = ChallengeSessionService()
    events = []
    s.add_listener(lambda: events.append(1))
    s.apply(result(capture(1, time=1000)))
    s.clear()
    assert s.races == {}
    assert len(events) == 2  # apply + clear


# --- drafts / effective -------------------------------------------------


def draft(track_id=0, car_id=0, car_name="", rank=0, time=0, bad_timing=False, note=""):
    return RaceView(track_id=track_id, car_id=car_id, car_name=car_name,
                    rank=rank, time=time, bad_timing=bad_timing, note=note)


def test_effective_none_without_data():
    s = ChallengeSessionService()
    assert s.effective(1) is None


def test_effective_none_for_capture_with_only_race_number():
    # розпізнавання дало лише номер гонки — без треку/авто/рангу/часу
    s = ChallengeSessionService()
    s.apply(result(capture(1)))
    assert s.races[1] is not None  # capture збережено
    assert s.effective(1) is None  # але рядок має виглядати як нерозпізнаний


def test_effective_none_for_empty_draft():
    # збереження порожньої модалки редагування не має лишати порожню картку
    s = ChallengeSessionService()
    s.set_draft(1, draft())
    assert s.effective(1) is None


def test_effective_from_ocr_with_uncertainty_flags():
    s = ChallengeSessionService()
    s.apply(result(capture(1, track_score=0.5, car_score=0.9, rank=3000, time=22797)))
    e = s.effective(1)
    assert e.track_id == 11 and e.track_uncertain is True
    assert e.car_id == 21 and e.car_uncertain is False
    assert e.rank == 3000 and e.time == 22797
    assert e.bad_timing is False and e.note == ""


def test_effective_draft_overrides_ocr():
    s = ChallengeSessionService()
    s.apply(result(capture(1, track_score=0.5, car_score=0.5, time=22797)))
    s.set_draft(1, draft(track_id=77, car_id=88, time=20000, bad_timing=True, note="crash"))
    e = s.effective(1)
    assert e.track_id == 77 and e.track_uncertain is False
    assert e.car_id == 88 and e.car_uncertain is False
    assert e.time == 20000
    assert e.bad_timing is True and e.note == "crash"


def test_effective_empty_draft_field_falls_back_to_ocr():
    s = ChallengeSessionService()
    s.apply(result(capture(1, track_score=0.9, time=22797)))
    s.set_draft(1, draft(car_id=88))  # трек і час у драфті порожні
    e = s.effective(1)
    assert e.track_id == 11  # просвічує OCR
    assert e.time == 22797
    assert e.car_id == 88


def test_effective_custom_car_name_from_draft():
    s = ChallengeSessionService()
    s.apply(result(capture(1, car_score=0.5)))
    s.set_draft(1, draft(car_name="Custom Car"))
    e = s.effective(1)
    assert e.car_id == 0 and e.car_name == "Custom Car"
    assert e.car_uncertain is False  # авто задане руками, OCR не використовується


def test_effective_draft_without_capture():
    s = ChallengeSessionService()
    s.set_draft(3, draft(track_id=5, car_id=6, time=30000))
    e = s.effective(3)
    assert e.track_id == 5 and e.car_id == 6 and e.time == 30000
    assert e.is_complete


def test_effective_is_complete_property():
    e1 = EffectiveRace(track_id=1, car_id=2, time=1000)
    e2 = EffectiveRace(track_id=1, car_name="Custom", time=1000)
    e3 = EffectiveRace(track_id=1, car_id=2)  # без часу
    assert e1.is_complete and e2.is_complete and not e3.is_complete


def test_set_draft_notifies_listeners():
    s = ChallengeSessionService()
    events = []
    s.add_listener(lambda: events.append(1))
    s.set_draft(1, draft(time=1000))
    assert events == [1]


def test_clear_resets_drafts():
    s = ChallengeSessionService()
    s.set_draft(1, draft(time=1000))
    s.clear()
    assert s.drafts == {}
    assert s.effective(1) is None


def test_is_complete_uses_drafts():
    s = ChallengeSessionService()
    for n in range(1, 5):
        s.apply(result(capture(n, track_score=0.9, car_score=0.9, time=20000)))
    assert not s.is_complete()
    s.set_draft(5, draft(track_id=5, car_id=6, time=30000))
    assert s.is_complete()


# --- toggle_bad_timing (перемикач 👎 на оверлеї) -------------------------


def test_toggle_bad_timing_flips_flag():
    s = ChallengeSessionService()
    s.apply(result(capture(1, track_score=0.9, time=22797)))
    s.toggle_bad_timing(1)
    assert s.effective(1).bad_timing is True
    s.toggle_bad_timing(1)
    assert s.effective(1).bad_timing is False


def test_toggle_bad_timing_keeps_ocr_shining_through():
    # перемикач не має «підтверджувати» OCR-поля, як це робить збереження модалки
    s = ChallengeSessionService()
    s.apply(result(capture(1, track_score=0.5, car_score=0.9, time=22797)))
    s.toggle_bad_timing(1)
    e = s.effective(1)
    assert e.track_id == 11 and e.track_uncertain is True
    assert e.car_id == 21 and e.time == 22797


def test_toggle_bad_timing_on_existing_draft_keeps_fields():
    s = ChallengeSessionService()
    s.set_draft(1, draft(track_id=77, time=20000, note="crash"))
    s.toggle_bad_timing(1)
    e = s.effective(1)
    assert e.bad_timing is True and e.track_id == 77 and e.note == "crash"


def test_toggle_bad_timing_noop_without_data():
    s = ChallengeSessionService()
    events = []
    s.add_listener(lambda: events.append(1))
    s.toggle_bad_timing(1)
    assert s.effective(1) is None and s.drafts == {} and events == []


def test_toggle_bad_timing_notifies_listeners():
    s = ChallengeSessionService()
    s.apply(result(capture(1, time=1000)))
    events = []
    s.add_listener(lambda: events.append(1))
    s.toggle_bad_timing(1)
    assert events == [1]


def test_effective_has_car_property():
    assert not EffectiveRace().has_car
    assert EffectiveRace(car_id=2).has_car
    assert EffectiveRace(car_name="Custom").has_car


def test_effective_is_empty_property():
    assert EffectiveRace().is_empty
    assert not EffectiveRace(track_id=1).is_empty
    assert not EffectiveRace(car_id=2).is_empty
    assert not EffectiveRace(car_name="Custom").is_empty
    assert not EffectiveRace(rank=3000).is_empty
    assert not EffectiveRace(time=20000).is_empty
    assert not EffectiveRace(note="crash").is_empty
    assert not EffectiveRace(bad_timing=True).is_empty


# --- дані суперника (opponent_time / opponent_car) -----------------------


def opp_capture(n, opp_time=None, opp_car_score=None, **kw):
    c = capture(n, **kw)
    c.opponent_time = opp_time
    if opp_car_score is not None:
        c.opponent_car = FieldGuess(value=30 + n, score=opp_car_score)
    return c


def test_opponent_fields_default_none():
    c = capture(1)
    assert c.opponent_time is None and c.opponent_car is None


def test_merge_opponent_fields_independent_of_mine():
    # BEFORE-скан (суперник) і мій результат чергуються — не затирають одне одного
    s = ChallengeSessionService()
    s.apply(result(opp_capture(1, opp_time=19152, opp_car_score=0.9)))
    s.apply(result(capture(1, car_score=0.9, rank=4795, time=19130)))
    r = s.races[1]
    assert r.opponent_time == 19152 and r.opponent_car.value == 31
    assert r.time == 19130 and r.car.value == 21


def test_merge_opponent_car_by_score():
    s = ChallengeSessionService()
    s.apply(result(opp_capture(1, opp_car_score=0.9)))
    low = opp_capture(1)
    low.opponent_car = FieldGuess(value=99, score=0.5)
    s.apply(result(low))
    assert s.races[1].opponent_car.value == 31  # впевненіше лишилось


def test_effective_exposes_opponent_fields():
    s = ChallengeSessionService()
    s.apply(result(opp_capture(2, opp_time=26591, opp_car_score=0.9, track_score=0.9)))
    e = s.effective(2)
    assert e.opponent_time == 26591
    assert e.opponent_car_id == 32


def test_effective_not_none_for_opponent_only_capture():
    # скан дав лише час суперника (без треку) — картка має бути видимою
    s = ChallengeSessionService()
    s.apply(result(opp_capture(3, opp_time=30000)))
    assert s.effective(3) is not None
    assert s.effective(3).opponent_time == 30000


# --- вибір авто (draft.car_id) / одноразовість сесії ------------------------


def assigned_car(s, n):
    e = s.effective(n)
    return e.car_id if e else 0


def test_set_assigned_one_car_one_race():
    s = ChallengeSessionService()
    s.set_assigned(1, 501)
    s.set_assigned(2, 502)
    s.set_assigned(3, 501)  # перевибір: авто 501 переїжджає з гонки 1 на 3
    assert assigned_car(s, 1) == 0
    assert assigned_car(s, 2) == 502
    assert assigned_car(s, 3) == 501
    assert s.pinned_races == {2, 3}


def test_set_assigned_none_unassigns():
    s = ChallengeSessionService()
    s.set_assigned(1, 501)
    s.set_assigned(1, None)
    assert assigned_car(s, 1) == 0 and s.pinned_races == set()


def test_set_assigned_does_not_steal_from_driven_race():
    # фактично проїхане авто (є мій час) не знімається перевибором на іншу гонку
    s = ChallengeSessionService()
    s.apply(result(capture(1, car_score=0.9, time=20000)))  # факт: авто 21
    s.set_assigned(2, 21)
    assert assigned_car(s, 1) == 21  # зіграна гонка недоторкана
    assert assigned_car(s, 2) == 21  # вибір записано (гра не дасть, але UI блокує раніше)


def test_set_assignments_keeps_pins_and_driven():
    s = ChallengeSessionService()
    s.set_assigned(2, 502)                      # ручний пін
    s.set_assigned(4, 504, pinned=False)        # авто-призначення
    s.apply(result(capture(5, car_score=0.9, time=20000)))  # зіграна: факт 25
    s.set_assignments({1: 501, 2: 999, 3: 503, 5: 888})  # автопідбір
    assert assigned_car(s, 1) == 501
    assert assigned_car(s, 2) == 502  # пін не перезаписано
    assert assigned_car(s, 3) == 503
    assert assigned_car(s, 4) == 0    # авто-призначення без нового — знято
    assert assigned_car(s, 5) == 25   # зіграна — фактичне авто, не 888
    assert s.pinned_races == {2}


def test_clear_pins():
    s = ChallengeSessionService()
    s.set_assigned(2, 502)
    s.clear_pins()
    assert s.pinned_races == set()
    assert assigned_car(s, 2) == 502  # вибір лишився, лише статус піна знято


def test_assignment_notifies_listeners():
    s = ChallengeSessionService()
    events = []
    s.add_listener(lambda: events.append(1))
    s.set_assigned(1, 501)
    s.set_assignments({2: 502})
    assert len(events) == 2


def test_clear_resets_assignments():
    s = ChallengeSessionService()
    s.set_assigned(1, 501)
    s.clear()
    assert assigned_car(s, 1) == 0 and s.pinned_races == set()


def test_is_disposable():
    s = ChallengeSessionService()
    assert s.is_disposable  # порожня
    s.apply(result(opp_capture(1, opp_time=19152, track_score=0.9)))
    s.set_assigned(1, 501)
    assert s.is_disposable  # дані суперника і вибір авто — все ще одноразова
    s.apply(result(capture(2, time=20000)))
    assert not s.is_disposable  # з'явився МІЙ час


def test_is_disposable_false_with_draft():
    s = ChallengeSessionService()
    s.set_draft(1, draft(note="x"))
    assert not s.is_disposable


def test_is_disposable_true_with_car_only_draft():
    # драфт лише з авто/рангом (= вибір з рекомендацій чи модалки) —
    # сесія лишається одноразовою
    s = ChallengeSessionService()
    s.set_draft(1, draft(car_id=501, rank=4000))
    assert s.is_disposable


# --- фактичний заїзд затирає вибране авто -----------------------------------


def test_new_run_scan_overwrites_chosen_car():
    s = ChallengeSessionService()
    s.set_assigned(1, 999)  # вибрав одне авто…
    s.apply(result(capture(1, car_score=0.9, rank=4795, time=19130)))  # …проїхав іншим
    e = s.effective(1)
    assert e.car_id == 21      # фактичне авто зі скану, не 999
    assert e.rank == 4795      # і фактичний ранг
    assert 1 not in s.pinned_races


def test_rescan_same_time_keeps_manual_fix():
    # виправлення помилки OCR після заїзду не стирається повторним сканом
    # того САМОГО результату (час не змінився)
    s = ChallengeSessionService()
    s.apply(result(capture(1, car_score=0.9, time=19130)))
    s.set_draft(1, draft(car_id=777, time=19130))
    s.apply(result(capture(1, car_score=0.9, time=19130)))
    assert s.effective(1).car_id == 777


def test_new_time_overwrites_manual_car():
    # а ось справжній НОВИЙ заїзд (інший час) — затирає і ручне авто
    s = ChallengeSessionService()
    s.apply(result(capture(1, car_score=0.9, time=19130)))
    s.set_draft(1, draft(car_id=777))
    s.apply(result(capture(1, car_score=0.9, time=18500)))
    assert s.effective(1).car_id == 21


def test_timed_count():
    s = ChallengeSessionService()
    s.apply(result(capture(1, time=20000)))
    s.apply(result(opp_capture(2, opp_time=19152)))
    s.set_draft(3, draft(time=21000))
    assert s.timed_count == 2  # мій OCR-час + час у драфті; час суперника не рахується
