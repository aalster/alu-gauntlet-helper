from alu_gauntlet_helper.models import FieldGuess, RaceCapture
from alu_gauntlet_helper.views.overlay import build_overlay_lines


def test_empty_session():
    lines = build_overlay_lines({}, {}, {}, status="чекаю")
    assert lines[0] == "Gauntlet capture 0/5"
    assert lines[1] == "1 — немає даних"
    assert lines[-1] == "чекаю"


def test_complete_race_line():
    races = {1: RaceCapture(
        race_number=1,
        track=FieldGuess(value=11, score=0.9),
        car=FieldGuess(value=21, score=0.9),
        time=22797,
    )}
    lines = build_overlay_lines(races, {11: "Notre Dame"}, {21: "Ultima RS"})
    assert lines[0] == "Gauntlet capture 1/5"
    assert lines[1] == "1 ✓ Notre Dame · Ultima RS · 00:22.797"


def test_partial_race_marked():
    races = {2: RaceCapture(race_number=2, time=21000)}
    lines = build_overlay_lines(races, {}, {})
    assert lines[1] == "1 — немає даних"
    assert lines[2].startswith("2 ⚠")
    assert "00:21.000" in lines[2]
    assert "?" in lines[2]
