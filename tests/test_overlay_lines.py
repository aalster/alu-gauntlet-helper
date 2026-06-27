from alu_gauntlet_helper import ui_lang
from alu_gauntlet_helper.services.challenge_session import EffectiveRace
from alu_gauntlet_helper.views.overlay import (UNCERTAIN_COLOR,
                                               build_races_table, header_text)

BRAND_TITLE = ui_lang.t("window.title")  # заголовок оверлея — статичний бренд, без лічильника

# Оверлей розбито на частини: header_text() — текст-заголовок (звичайний QLabel),
# build_races_table() — HTML-таблиця гонок. Статус і підказка з хоткеями — окремі
# QLabel, що заповнюються без форматування, тож власних тестів не мають.


def test_empty_session():
    assert header_text({}) == BRAND_TITLE
    table = build_races_table({}, {}, {})
    assert "no data" in table


def test_complete_race_line():
    races = {1: EffectiveRace(track_id=11, car_id=21, time=22797)}
    assert header_text(races) == BRAND_TITLE  # заголовок не залежить від вмісту гонок
    table = build_races_table(races, {11: "Notre Dame"}, {21: "Ultima RS"})
    assert "Notre Dame" in table
    assert "Ultima RS" in table
    assert "00:22.797" in table


def test_partial_race_marked():
    races = {2: EffectiveRace(time=21000)}
    table = build_races_table(races, {}, {})
    assert "00:21.000" in table
    assert "no data" in table  # гонка 1 без даних


def test_custom_car_name_counts_as_complete():
    races = {1: EffectiveRace(track_id=11, car_name="Custom Car", time=22797)}
    assert header_text(races) == BRAND_TITLE
    table = build_races_table(races, {11: "Notre Dame"}, {})
    assert "Custom Car" in table
    assert "00:22.797" in table


def test_unresolved_names_show_question_marks():
    races = {1: EffectiveRace(track_id=99, car_id=98, time=22797)}
    table = build_races_table(races, {}, {})
    assert "00:22.797" in table
    assert "?" in table


def test_uncertain_fields_highlighted():
    races = {1: EffectiveRace(track_id=11, car_id=21, time=22797,
                              track_uncertain=True, car_uncertain=True)}
    table = build_races_table(races, {11: "Notre Dame"}, {21: "Ultima RS"})
    assert table.count(UNCERTAIN_COLOR) == 2  # підсвічені і трек, і авто


def test_certain_fields_not_highlighted():
    races = {1: EffectiveRace(track_id=11, car_id=21, time=22797)}
    table = build_races_table(races, {11: "Notre Dame"}, {21: "Ultima RS"})
    assert UNCERTAIN_COLOR not in table
