from alu_gauntlet_helper.services.challenge_session import EffectiveRace
from alu_gauntlet_helper.views.overlay import build_overlay_lines


def test_empty_session():
    lines = build_overlay_lines({}, {}, {}, status="waiting")
    assert lines[0] == "Gauntlet capture 0/5"
    assert lines[1] == "1 — no data"
    assert lines[-1] == "waiting"


def test_complete_race_line():
    races = {1: EffectiveRace(track_id=11, car_id=21, time=22797)}
    lines = build_overlay_lines(races, {11: "Notre Dame"}, {21: "Ultima RS"})
    assert lines[0] == "Gauntlet capture 1/5"
    assert lines[1] == "1 ✓ Notre Dame · Ultima RS · 00:22.797"


def test_partial_race_marked():
    races = {2: EffectiveRace(time=21000)}
    lines = build_overlay_lines(races, {}, {})
    assert lines[1] == "1 — no data"
    assert lines[2].startswith("2 ⚠")
    assert "00:21.000" in lines[2]
    assert "?" in lines[2]


def test_custom_car_name_counts_as_complete():
    races = {1: EffectiveRace(track_id=11, car_name="Custom Car", time=22797)}
    lines = build_overlay_lines(races, {11: "Notre Dame"}, {})
    assert lines[0] == "Gauntlet capture 1/5"
    assert lines[1] == "1 ✓ Notre Dame · Custom Car · 00:22.797"


def test_unresolved_names_show_question_marks_but_race_stays_complete():
    races = {1: EffectiveRace(track_id=99, car_id=98, time=22797)}
    lines = build_overlay_lines(races, {}, {})
    assert lines[1] == "1 ✓ ? · ? · 00:22.797"
