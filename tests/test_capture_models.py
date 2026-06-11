from alu_gauntlet_helper.models import FieldGuess, RaceCapture, RecognitionResult


def test_race_capture_defaults():
    c = RaceCapture(race_number=3)
    assert c.race_number == 3
    assert c.track is None and c.car is None
    assert c.rank is None and c.time is None
    assert c.panel_image is None


def test_field_guess_candidates():
    g = FieldGuess(value=7, score=0.92, candidates=[(7, 0.92), (3, 0.8)])
    assert g.value == 7
    assert g.candidates[0] == (7, 0.92)


def test_recognition_result():
    r = RecognitionResult(screen="challenge_accordion", captures=[RaceCapture(race_number=1)])
    assert r.screen == "challenge_accordion"
    assert len(r.captures) == 1
