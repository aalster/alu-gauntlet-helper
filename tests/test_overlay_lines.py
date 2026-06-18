from alu_gauntlet_helper.services.challenge_session import EffectiveRace
from alu_gauntlet_helper.views.overlay import build_overlay_html


def test_empty_session():
    html = build_overlay_html({}, {}, {}, status="waiting")
    assert "Gauntlet capture 0/5" in html
    assert "no data" in html
    assert "waiting" in html


def test_complete_race_line():
    races = {1: EffectiveRace(track_id=11, car_id=21, time=22797)}
    html = build_overlay_html(races, {11: "Notre Dame"}, {21: "Ultima RS"})
    assert "Gauntlet capture 1/5" in html
    assert "Notre Dame" in html
    assert "Ultima RS" in html
    assert "00:22.797" in html


def test_partial_race_marked():
    races = {2: EffectiveRace(time=21000)}
    html = build_overlay_html(races, {}, {})
    assert "00:21.000" in html
    assert "no data" in html  # гонка 1 без даних


def test_custom_car_name_counts_as_complete():
    races = {1: EffectiveRace(track_id=11, car_name="Custom Car", time=22797)}
    html = build_overlay_html(races, {11: "Notre Dame"}, {})
    assert "Gauntlet capture 1/5" in html
    assert "Custom Car" in html
    assert "00:22.797" in html


def test_unresolved_names_show_question_marks():
    races = {1: EffectiveRace(track_id=99, car_id=98, time=22797)}
    html = build_overlay_html(races, {}, {})
    assert "00:22.797" in html
    assert "?" in html


def test_status_and_hotkey_hint_present():
    html = build_overlay_html({}, {}, {}, status="waiting", hotkey_hint="F9 capture · F10 hide")
    assert "F9 capture · F10 hide" in html
    assert "waiting" in html
