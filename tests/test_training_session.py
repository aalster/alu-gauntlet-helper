from alu_gauntlet_helper.models import FieldGuess, RaceCapture, RecognitionResult
from alu_gauntlet_helper.services.races import RaceView
from alu_gauntlet_helper.services.training_session import TrainingSessionService

TRACK_OSAKA = 42
TRACK_NEVADA = 43
MAP_OSAKA = 5
CAR_BATTISTA = 201
CAR_CHIRON = 202


def lobby_capture(track_id=TRACK_OSAKA, score=0.9, map_id=MAP_OSAKA):
    """Скан лобі: трек/карта відомі, часу немає."""
    return RaceCapture(
        race_number=0,
        track=FieldGuess(value=track_id, score=score),
        map=FieldGuess(value=map_id, score=0.9) if map_id else None,
        source_screen="training_lobby",
    )


def run_capture(time, car_id=CAR_BATTISTA, car_score=0.9):
    """Скан результату заїзду: час (+авто), треку немає."""
    return RaceCapture(
        race_number=0,
        car=FieldGuess(value=car_id, score=car_score) if car_id else None,
        time=time,
        source_screen="training_result",
    )


def result(*captures, screen="training_result"):
    return RecognitionResult(screen=screen, captures=list(captures))


# --- лобі: трек сесії -------------------------------------------------------

def test_lobby_scan_sets_session_track():
    s = TrainingSessionService()
    s.apply(result(lobby_capture(), screen="training_lobby"))
    assert s.track and s.track.value == TRACK_OSAKA
    assert s.map and s.map.value == MAP_OSAKA
    assert s.run_numbers() == []


def test_lobby_rescan_newer_wins():
    s = TrainingSessionService()
    s.apply(result(lobby_capture(score=0.95), screen="training_lobby"))
    s.apply(result(lobby_capture(track_id=TRACK_NEVADA, score=0.6), screen="training_lobby"))
    assert s.track.value == TRACK_NEVADA  # свіжіший скан коригує трек навіть із нижчим score


# --- заїзди: append та дедуплікація -----------------------------------------

def test_run_scans_append_with_sequential_numbers():
    s = TrainingSessionService()
    s.apply(result(run_capture(26499)))
    s.apply(result(run_capture(25533, car_id=CAR_CHIRON)))
    assert s.run_numbers() == [1, 2]
    assert s.runs[1].time == 26499
    assert s.runs[2].car.value == CAR_CHIRON


def test_rescan_of_same_time_merges_into_last_run():
    s = TrainingSessionService()
    s.apply(result(run_capture(26499, car_id=None)))
    s.apply(result(run_capture(26499, car_id=CAR_BATTISTA)))
    assert s.run_numbers() == [1]
    assert s.runs[1].car.value == CAR_BATTISTA


def test_same_time_as_older_run_still_appends():
    # дедуплікація лише проти ОСТАННЬОГО заїзду: рескан завжди йде одразу
    # після оригіналу, а рівний час зі старим заїздом — випадковість
    s = TrainingSessionService()
    s.apply(result(run_capture(26499)))
    s.apply(result(run_capture(25533)))
    s.apply(result(run_capture(26499)))
    assert s.run_numbers() == [1, 2, 3]


# --- effective: трек сесії просвічує в кожен заїзд ---------------------------

def test_effective_combines_session_track_and_run_data():
    s = TrainingSessionService()
    s.apply(result(lobby_capture(), screen="training_lobby"))
    s.apply(result(run_capture(26499)))
    e = s.effective(1)
    assert e.track_id == TRACK_OSAKA
    assert e.car_id == CAR_BATTISTA
    assert e.time == 26499
    assert e.rank == 0
    assert e.is_complete


def test_effective_without_track_is_incomplete():
    s = TrainingSessionService()
    s.apply(result(run_capture(26499)))
    e = s.effective(1)
    assert e.track_id == 0
    assert not e.is_complete


def test_effective_unknown_run_is_none():
    s = TrainingSessionService()
    assert s.effective(1) is None


def test_draft_overrides_run_fields():
    s = TrainingSessionService()
    s.apply(result(lobby_capture(), screen="training_lobby"))
    s.apply(result(run_capture(26499)))
    s.set_draft(1, RaceView(car_id=CAR_CHIRON, note="кращий старт"))
    e = s.effective(1)
    assert e.car_id == CAR_CHIRON
    assert e.note == "кращий старт"
    assert e.time == 26499  # порожній час драфта «просвічує» OCR


def test_draft_track_overrides_session_track():
    s = TrainingSessionService()
    s.apply(result(lobby_capture(), screen="training_lobby"))
    s.apply(result(run_capture(26499)))
    s.set_draft(1, RaceView(track_id=TRACK_NEVADA))
    assert s.effective(1).track_id == TRACK_NEVADA


def test_toggle_bad_timing():
    s = TrainingSessionService()
    s.apply(result(run_capture(26499)))
    s.toggle_bad_timing(1)
    assert s.effective(1).bad_timing
    s.toggle_bad_timing(1)
    assert not s.effective(1).bad_timing


# --- конфлікти: інший трек лобі-скану ---------------------------------------

def test_lobby_scan_with_other_track_conflicts():
    s = TrainingSessionService()
    s.apply(result(lobby_capture(), screen="training_lobby"))
    assert s.conflicts(result(lobby_capture(track_id=TRACK_NEVADA), screen="training_lobby"))


def test_lobby_rescan_same_track_no_conflict():
    s = TrainingSessionService()
    s.apply(result(lobby_capture(), screen="training_lobby"))
    assert not s.conflicts(result(lobby_capture(), screen="training_lobby"))


def test_lobby_scan_into_trackless_session_no_conflict():
    # сесію відкрив скан результату (треку ще немає) — лобі-скан його доповнює
    s = TrainingSessionService()
    s.apply(result(run_capture(26499)))
    assert not s.conflicts(result(lobby_capture(), screen="training_lobby"))


def test_run_scan_never_conflicts():
    s = TrainingSessionService()
    s.apply(result(lobby_capture(), screen="training_lobby"))
    assert not s.conflicts(result(run_capture(26499)))


# --- життєвий цикл: disposable і видалення збережених ------------------------

def test_lobby_only_session_is_disposable():
    s = TrainingSessionService()
    s.apply(result(lobby_capture(), screen="training_lobby"))
    assert s.is_disposable


def test_session_with_run_is_not_disposable():
    s = TrainingSessionService()
    s.apply(result(run_capture(26499)))
    assert not s.is_disposable


def test_meaningful_draft_makes_not_disposable():
    s = TrainingSessionService()
    s.apply(result(lobby_capture(), screen="training_lobby"))
    s.apply(result(run_capture(26499)))
    s.remove_runs([1])
    s.set_draft(2, RaceView())  # порожній драфт — не цінність
    assert s.is_disposable


def test_remove_runs_keeps_track_and_numbering():
    s = TrainingSessionService()
    s.apply(result(lobby_capture(), screen="training_lobby"))
    s.apply(result(run_capture(26499)))
    s.apply(result(run_capture(25533)))
    s.remove_runs([1, 2])
    assert s.run_numbers() == []
    assert s.track.value == TRACK_OSAKA  # інфо треку живе далі
    s.apply(result(run_capture(24000)))
    assert s.run_numbers() == [3]  # нумерація наскрізна, не скидається


def test_remove_runs_drops_their_drafts():
    s = TrainingSessionService()
    s.apply(result(run_capture(26499)))
    s.set_draft(1, RaceView(note="x"))
    s.remove_runs([1])
    assert s.is_disposable  # драфт видалено разом із заїздом
    assert s.effective(1) is None


def test_is_complete_always_false():
    # контракт статусу оверлея (session.is_complete → "Done"): тренування
    # нескінченне, стану «завершено» не має
    s = TrainingSessionService()
    s.apply(result(lobby_capture(), screen="training_lobby"))
    s.apply(result(run_capture(26499)))
    assert not s.is_complete()


def test_listener_notified_on_apply_and_draft():
    s = TrainingSessionService()
    events = []
    s.add_listener(lambda: events.append(1))
    s.apply(result(run_capture(26499)))
    s.set_draft(1, RaceView(note="x"))
    s.remove_runs([1])
    assert len(events) == 3
