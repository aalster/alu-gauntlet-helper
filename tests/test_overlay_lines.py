from alu_gauntlet_helper import ui_lang
from alu_gauntlet_helper.services.challenge_session import EffectiveRace
from alu_gauntlet_helper.views.overlay import (COMPLETE_COLOR, CYAN, LOSS_BRIGHT,
                                               PARTIAL_COLOR, UNCERTAIN_COLOR,
                                               WIN_BRIGHT, build_races_table,
                                               header_text)

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
    assert COMPLETE_COLOR in table  # повний рядок — зелений номер


def test_partial_race_marked():
    races = {2: EffectiveRace(time=21000)}
    table = build_races_table(races, {}, {})
    assert "00:21.000" in table
    assert "no data" in table  # гонка 1 без даних
    assert PARTIAL_COLOR in table       # частковий рядок — амбер-номер
    assert COMPLETE_COLOR not in table  # повних рядків немає


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


def test_suggested_car_shown_in_cyan():
    # рекомендоване авто (без фактичного) показується і фарбується блакитним
    races = {1: EffectiveRace(track_id=11, suggested_car_id=21, opponent_time=25000)}
    table = build_races_table(races, {11: "Notre Dame"}, {21: "Ultima RS"})
    assert "Ultima RS" in table
    assert CYAN in table


def test_unplayed_race_with_car_shows_chance_without_dislike():
    # незіграна гонка з авто: замість часу — шанс і «7/10», перемикач 👎 схований
    races = {1: EffectiveRace(track_id=11, suggested_car_id=21, opponent_time=25000),
             2: EffectiveRace(track_id=12, car_id=22, opponent_time=25000)}
    table = build_races_table(races, {11: "Notre Dame", 12: "Founders"},
                              {21: "Ultima RS", 22: "Huracan"},
                              beat_stats={1: (7, 10), 2: (1, 10)})
    assert "7/10" in table and "1/10" in table
    # laplace(7,10)=8/12≈67% зеленим, laplace(1,10)=2/12≈17% червоним
    assert f"color:{WIN_BRIGHT};font-weight:bold'>67%" in table
    assert f"color:{LOSS_BRIGHT};font-weight:bold'>17%" in table
    assert "побито" not in table and "beaten" not in table
    assert "dislike:1" not in table and "dislike:2" not in table


def test_unplayed_race_with_car_but_no_stats_hides_dislike():
    # авто є, статистики немає — часу теж немає, тож 👎 все одно схований
    races = {1: EffectiveRace(track_id=11, car_id=21, opponent_time=25000)}
    table = build_races_table(races, {11: "Notre Dame"}, {21: "Ultima RS"})
    assert "dislike:1" not in table
    assert "?" in table  # у колонці часу — заглушка


def test_played_race_keeps_time_and_dislike_over_chance():
    # зіграна гонка показує час і 👎, навіть якщо статистика передана
    races = {1: EffectiveRace(track_id=11, car_id=21, time=22797, opponent_time=25000)}
    table = build_races_table(races, {11: "Notre Dame"}, {21: "Ultima RS"},
                              beat_stats={1: (7, 10)})
    assert "00:22.797" in table
    assert "dislike:1" in table
    assert "7/10" not in table


def test_actual_car_not_cyan():
    races = {1: EffectiveRace(track_id=11, car_id=21, time=22797)}
    table = build_races_table(races, {11: "Notre Dame"}, {21: "Ultima RS"})
    assert CYAN not in table


def test_dislike_toggle_links_per_race():
    races = {1: EffectiveRace(track_id=11, car_id=21, time=22797),
             2: EffectiveRace(time=21000, bad_timing=True)}
    table = build_races_table(races, {11: "Notre Dame"}, {21: "Ultima RS"})
    assert "dislike:1" in table and "dislike:2" in table
    assert "dislike:3" not in table  # рядки без даних — без перемикача
    assert "thumbs-down-dim.svg" in table  # гонка 1 — прапорець вимкнено
    assert "thumbs-down.svg" in table      # гонка 2 — увімкнено


# --- win_chance_color: спільні пороги таба асистента й оверлея -------------


def test_win_chance_color_thresholds():
    from alu_gauntlet_helper.views.style import RANK_DOWN, win_chance_color
    assert win_chance_color(76) == WIN_BRIGHT
    assert win_chance_color(75) == RANK_DOWN   # рівно 75 — ще помаранчевий
    assert win_chance_color(51) == RANK_DOWN
    assert win_chance_color(50) == LOSS_BRIGHT  # рівно 50 — вже червоний


# --- заголовок з шансом перемоги «72%» (спека §7, Етап 2) -------------------


def test_header_with_win_chance_appends_colored_percent():
    from alu_gauntlet_helper.views.style import RANK_DOWN
    h = header_text({}, win_chance=0.72)
    assert BRAND_TITLE in h
    assert "72%" in h
    assert "~" not in h    # без тильди — як внизу таба асистента
    assert RANK_DOWN in h  # 72% — помаранчева зона (>50, ≤75)


def test_header_win_chance_color_zones():
    assert WIN_BRIGHT in header_text({}, 0.80)
    assert LOSS_BRIGHT in header_text({}, 0.30)


def test_header_without_win_chance_stays_plain():
    assert header_text({}) == BRAND_TITLE
    assert header_text({}, None) == BRAND_TITLE
