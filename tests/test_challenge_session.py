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


def test_effective_has_car_property():
    assert not EffectiveRace().has_car
    assert EffectiveRace(car_id=2).has_car
    assert EffectiveRace(car_name="Custom").has_car
