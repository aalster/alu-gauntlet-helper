from alu_gauntlet_helper.models import FieldGuess, RaceCapture, RecognitionResult
from alu_gauntlet_helper.services.challenge_session import ChallengeSessionService


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
