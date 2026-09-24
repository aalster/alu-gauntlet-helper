from alu_gauntlet_helper.models import FieldGuess, RaceCapture, RecognitionResult
from alu_gauntlet_helper.services.session_manager import SessionManager
from alu_gauntlet_helper.services.training_session import TrainingSessionService


def capture(n, opp_time=None, time=None, track_score=None):
    return RaceCapture(
        race_number=n,
        track=FieldGuess(value=10 + n, score=track_score) if track_score is not None else None,
        time=time,
        opponent_time=opp_time,
    )


def result(*captures):
    return RecognitionResult(screen="test", captures=list(captures))


def test_starts_with_one_empty_active_session():
    m = SessionManager()
    assert len(m.sessions) == 1
    assert m.active is m.sessions[0]


def test_apply_routes_to_active():
    m = SessionManager()
    m.apply(result(capture(1, opp_time=19152)))
    assert m.active.races[1].opponent_time == 19152


def test_same_opponent_time_merges_no_new_session():
    m = SessionManager()
    m.apply(result(capture(1, opp_time=19152)))
    m.apply(result(capture(1, opp_time=19152, track_score=0.9)))
    assert len(m.sessions) == 1
    assert m.active.races[1].track.value == 11


def test_track_mismatch_is_not_conflict():
    # розбіжність лише треку — корекція розпізнавання, НЕ новий суперник
    m = SessionManager()
    first = capture(1, opp_time=19152, track_score=0.6)
    m.apply(result(first))
    better = capture(1, opp_time=19152)
    better.track = FieldGuess(value=99, score=0.95)
    m.apply(result(better))
    assert len(m.sessions) == 1
    assert m.active.races[1].track.value == 99


def test_conflict_replaces_disposable_session():
    # скаутинг: новий кандидат затирає попереднього (немає моїх часів)
    m = SessionManager()
    m.apply(result(capture(1, opp_time=19152)))
    old = m.active
    m.apply(result(capture(1, opp_time=25000)))
    assert len(m.sessions) == 1
    assert m.active is not old
    assert m.active.races[1].opponent_time == 25000


def test_conflict_detaches_valuable_session():
    # у сесії мій час → вона відщеплюється табом, нова стає активною
    m = SessionManager()
    m.apply(result(capture(1, opp_time=19152), capture(2, time=20000)))
    old = m.active
    m.apply(result(capture(1, opp_time=25000)))
    assert len(m.sessions) == 2
    assert m.sessions[0] is old            # стара збережена
    assert m.active.races[1].opponent_time == 25000
    assert old.races[1].opponent_time == 19152  # стара недоторкана


def test_close_removes_and_keeps_at_least_one():
    m = SessionManager()
    m.apply(result(capture(1, opp_time=19152), capture(2, time=20000)))
    old = m.active
    m.apply(result(capture(1, opp_time=25000)))
    m.close(old)
    assert old not in m.sessions and len(m.sessions) == 1
    m.close(m.active)
    assert len(m.sessions) == 1  # нова порожня створена
    assert m.active.races == {}


def test_listener_fires_on_session_changes_and_structure():
    m = SessionManager()
    events = []
    m.add_listener(lambda: events.append(1))
    m.apply(result(capture(1, opp_time=19152)))          # 1 подія (apply сесії)
    m.apply(result(capture(1, opp_time=25000)))          # заміна (структурна) + apply
    assert len(events) >= 3
    n = len(events)
    m.close(m.active)                                     # структурна
    assert len(events) > n


def test_closed_session_stops_notifying():
    m = SessionManager()
    # мій час + час суперника: сесія цінна, і конфлікт буде детектовано
    m.apply(result(capture(2, time=20000, opp_time=30000)))
    old = m.active
    m.apply(result(capture(2, opp_time=1)))  # конфлікт → old відщеплюється
    assert len(m.sessions) == 2
    m.close(old)
    events = []
    m.add_listener(lambda: events.append(1))
    old.clear()  # зміни в закритій сесії — менеджер мовчить
    assert events == []


def test_auto_pick_called_after_opponent_scan():
    picked = []
    m = SessionManager(auto_pick=lambda s: picked.append(s))
    m.apply(result(capture(1, time=20000)))     # мій результат — без автопідбору
    assert picked == []
    m.apply(result(capture(1, opp_time=19152)))  # дані суперника — автопідбір
    assert picked == [m.active]


def test_empty_result_is_noop():
    m = SessionManager()
    events = []
    m.add_listener(lambda: events.append(1))
    m.apply(result())
    assert events == [] and len(m.sessions) == 1


def test_auto_pick_called_after_map_scan():
    # скан скаут-екрана (є лише карта) теж має запускати автопідбір:
    # він тягне resolve_tracks → звуження треку за часом (спека §6)
    from alu_gauntlet_helper.models import FieldGuess
    picked = []
    m = SessionManager(auto_pick=lambda s: picked.append(s))
    c = capture(1)
    c.map = FieldGuess(value=5, score=0.9)
    m.apply(result(c))
    assert picked == [m.active]


def test_map_mismatch_is_conflict_replaces_disposable():
    # скани скаут-екранів РІЗНИХ суперників не зливаються (спека, «Ігровий контекст»)
    from alu_gauntlet_helper.models import FieldGuess
    m = SessionManager()
    a = capture(1)
    a.map = FieldGuess(value=5, score=0.9)
    m.apply(result(a))
    old = m.active
    b = capture(1)
    b.map = FieldGuess(value=7, score=0.9)
    m.apply(result(b))
    assert len(m.sessions) == 1 and m.active is not old
    assert m.active.races[1].map.value == 7


def test_same_map_rescan_merges():
    from alu_gauntlet_helper.models import FieldGuess
    m = SessionManager()
    a = capture(1)
    a.map = FieldGuess(value=5, score=0.9)
    m.apply(result(a))
    b = capture(1, opp_time=20000)
    b.map = FieldGuess(value=5, score=0.9)
    m.apply(result(b))
    assert len(m.sessions) == 1
    assert m.active.races[1].opponent_time == 20000


def test_auto_pick_called_after_track_only_scan():
    # екран 2 з нерозпізнаною іконкою: лише трек — підбір все одно запускається
    picked = []
    m = SessionManager(auto_pick=lambda s: picked.append(s))
    m.apply(result(capture(1, track_score=0.9)))
    assert picked == [m.active]


# --- тренувальні сесії: окрема «смуга» сканів --------------------------------

def lobby_result(track_id=100):
    return RecognitionResult(screen="training_lobby", captures=[RaceCapture(
        race_number=0, track=FieldGuess(value=track_id, score=0.9))])


def run_result(time):
    return RecognitionResult(screen="training_result", captures=[RaceCapture(
        race_number=0, time=time, car=FieldGuess(value=200, score=0.9))])


def test_training_scan_replaces_empty_start_session():
    m = SessionManager()
    m.apply(lobby_result())
    assert len(m.sessions) == 1
    assert isinstance(m.active, TrainingSessionService)
    assert m.active.track.value == 100


def test_training_scan_detaches_valuable_challenge():
    m = SessionManager()
    m.apply(result(capture(1, opp_time=19152), capture(2, time=20000)))
    challenge = m.active
    m.apply(lobby_result())
    assert len(m.sessions) == 2
    assert m.sessions[0] is challenge  # стара лишилась табом, без переміщень
    assert isinstance(m.active, TrainingSessionService)


def test_challenge_scan_reactivates_paused_challenge():
    # кейс «повернувся дограти»: сумісний челендж-скан повертає стару сесію
    # в актив БЕЗ нової сесії і БЕЗ зміни порядку табів
    m = SessionManager()
    m.apply(result(capture(1, opp_time=19152), capture(2, time=20000)))
    challenge = m.active
    m.apply(lobby_result())
    events = []
    m.add_listener(lambda: events.append(1))
    m.apply(result(capture(3, opp_time=21000)))
    assert len(m.sessions) == 2
    assert m.active is challenge
    assert m.sessions[0] is challenge  # порядок не змінився
    assert challenge.races[3].opponent_time == 21000
    assert events  # реактивація — структурна зміна, UI нотифіковано


def test_training_result_scan_reactivates_training_session():
    m = SessionManager()
    m.apply(lobby_result())
    m.apply(run_result(26499))  # тренування цінне (є заїзд)
    training = m.active
    m.apply(result(capture(1, opp_time=19152), capture(2, time=20000)))  # челендж
    assert m.active is not training
    m.apply(run_result(25533))
    assert m.active is training
    assert training.run_numbers() == [1, 2]


def test_conflicting_lobby_scan_replaces_disposable_training():
    m = SessionManager()
    m.apply(lobby_result(track_id=100))
    m.apply(lobby_result(track_id=101))  # інший трек, заїздів не було
    assert len(m.sessions) == 1
    assert m.active.track.value == 101


def test_conflicting_lobby_scan_detaches_valuable_training():
    m = SessionManager()
    m.apply(lobby_result(track_id=100))
    m.apply(run_result(26499))
    old = m.active
    m.apply(lobby_result(track_id=101))
    assert len(m.sessions) == 2
    assert m.sessions[0] is old
    assert m.active is not old and m.active.track.value == 101


def test_close_active_falls_back_to_remaining():
    m = SessionManager()
    m.apply(result(capture(1, opp_time=19152), capture(2, time=20000)))
    challenge = m.active
    m.apply(lobby_result())
    m.apply(run_result(26499))
    m.close(m.active)
    assert m.active is challenge


def test_auto_pick_not_called_for_training_scans():
    picked = []
    m = SessionManager(auto_pick=lambda s: picked.append(s))
    m.apply(lobby_result())
    m.apply(run_result(26499))
    assert picked == []
