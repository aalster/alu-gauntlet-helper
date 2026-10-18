from alu_gauntlet_helper import ui_lang
from alu_gauntlet_helper.services.challenge_session import EffectiveRace
from alu_gauntlet_helper.services.assistant import BeatStats
from alu_gauntlet_helper.views.overlay import (COMPLETE_COLOR, CYAN, LOSS_BRIGHT,
                                               WIN_BRIGHT,
                                               build_races_table,
                                               build_training_table, header_text)

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
    assert "#e6c34a" not in table       # жовтого номера більше немає
    assert "color:white;font-weight:bold'>2</span>" in table  # частковий — білий
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


def test_uncertain_fields_not_highlighted():
    # оверлей більше не фарбує непевні поля — вони виглядають як звичайні
    sure = {1: EffectiveRace(track_id=11, car_id=21, time=22797)}
    unsure = {1: EffectiveRace(track_id=11, car_id=21, time=22797,
                               track_uncertain=True, car_uncertain=True)}
    names = ({11: "Notre Dame"}, {21: "Ultima RS"})
    assert build_races_table(unsure, *names) == build_races_table(sure, *names)


def test_suggested_car_shown_in_cyan():
    # рекомендоване авто (без фактичного) показується і фарбується блакитним
    races = {1: EffectiveRace(track_id=11, suggested_car_id=21, opponent_time=25000)}
    table = build_races_table(races, {11: "Notre Dame"}, {21: "Ultima RS"})
    assert "Ultima RS" in table
    assert CYAN in table


def test_unplayed_race_with_car_shows_delta_without_dislike():
    # незіграна гонка з авто: замість часу — Δ «мій мінус суперника» і «7/10»,
    # перемикач 👎 схований; відсотка шансу в рядку більше немає
    races = {1: EffectiveRace(track_id=11, suggested_car_id=21, opponent_time=25000),
             2: EffectiveRace(track_id=12, car_id=22, opponent_time=25000)}
    table = build_races_table(races, {11: "Notre Dame", 12: "Founders"},
                              {21: "Ultima RS", 22: "Huracan"},
                              beat_stats={1: BeatStats(7, 10, 1300),
                                          2: BeatStats(1, 10, -2000)})
    assert "7/10" in table and "1/10" in table
    # Δ=+1300 (я швидший) → «−1.300» зеленим; Δ=−2000 → «+2.000» червоним
    # Δ і лічильник — окремі колонки: Δ притиснута праворуч, «7/10» — у
    # колонці 👎 (для незіграної гонки вона порожня)
    assert (f"<td align='right' style='vertical-align:middle'><span style='color:{WIN_BRIGHT};"
            f"font-weight:bold'>−1.300</span></td>"
            f"<td style='padding-left:8px;vertical-align:middle'>7/10</td>") in table
    assert (f"<td align='right' style='vertical-align:middle'><span style='color:{LOSS_BRIGHT};"
            f"font-weight:bold'>+2.000</span></td>"
            f"<td style='padding-left:8px;vertical-align:middle'>1/10</td>") in table
    assert "%" not in table
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
                              beat_stats={1: BeatStats(7, 10, 1300)})
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


# --- карта на оверлеї; трек, вибраний чипом, — cyan (етап 3) ----------------


def test_map_only_race_shows_map_name():
    # трек невідомий, карта є (скаут-екран) — замість «?» назва карти
    races = {1: EffectiveRace(map_id=5, opponent_time=25000)}
    table = build_races_table(races, {}, {}, map_names={5: "The Caribbean"})
    assert "The Caribbean" in table


def test_fixed_track_cyan_with_white_map_and_dash():
    # трек вибрано чипом: «Карта - » звичайним кольором (з тире), трек — cyan
    races = {1: EffectiveRace(track_id=26, map_id=5, track_fixed=True,
                              opponent_time=25000)}
    table = build_races_table(races, {26: "Hell Vale"}, {},
                              track_maps={26: "The Caribbean"},
                              map_names={5: "The Caribbean"})
    assert f"The Caribbean - <span style='color:{CYAN}'>Hell Vale</span>" in table
    assert "The Caribbean - Hell Vale" not in table  # карта не в cyan-спані


def test_inferred_track_has_no_question_suffix():
    # трек виведено звуженням за часом — без позначки «?» (прибрано на прохання)
    races = {1: EffectiveRace(track_id=26, map_id=5, track_fixed=True,
                              track_inferred=True, opponent_time=25000)}
    table = build_races_table(races, {26: "Hell Vale"}, {},
                              map_names={5: "The Caribbean"})
    assert "Hell Vale ?" not in table
    assert f"<span style='color:{CYAN}'>Hell Vale</span>" in table


def test_scanned_track_composes_map_dash_track():
    # звичайний (не чип) трек: «Карта - Трек» одним кольором, як раніше
    races = {1: EffectiveRace(track_id=11, car_id=21, time=22797)}
    table = build_races_table(races, {11: "Notre Dame"}, {21: "Ultima RS"},
                              track_maps={11: "Paris"})
    assert "Paris - Notre Dame" in table
    assert CYAN not in table


# --- колір номера гонки: програш проти суперника — червоний ----------------


def test_lost_race_number_red():
    # мій час гірший (або рівний) за час суперника — номер червоний
    races = {1: EffectiveRace(track_id=11, car_id=21, time=25000, opponent_time=24000)}
    table = build_races_table(races, {11: "Notre Dame"}, {21: "Ultima RS"})
    assert f"color:{LOSS_BRIGHT};font-weight:bold'>1</span>" in table
    assert COMPLETE_COLOR not in table


def test_won_race_number_green():
    races = {1: EffectiveRace(track_id=11, car_id=21, time=23000, opponent_time=24000)}
    table = build_races_table(races, {11: "Notre Dame"}, {21: "Ultima RS"})
    assert f"color:{COMPLETE_COLOR};font-weight:bold'>1</span>" in table
    assert LOSS_BRIGHT not in table


def test_played_race_without_opponent_time_not_red():
    # без часу суперника програшу немає — номер за заповненістю, як раніше
    races = {1: EffectiveRace(track_id=11, car_id=21, time=25000)}
    table = build_races_table(races, {11: "Notre Dame"}, {21: "Ultima RS"})
    assert LOSS_BRIGHT not in table
    assert COMPLETE_COLOR in table


# --- win_chance_color: спільні пороги таба асистента й оверлея -------------


def test_win_chance_color_thresholds():
    from alu_gauntlet_helper.views.style import RANK_DOWN, win_chance_color
    assert win_chance_color(76) == WIN_BRIGHT
    assert win_chance_color(75) == RANK_DOWN   # рівно 75 — ще помаранчевий
    assert win_chance_color(51) == RANK_DOWN
    assert win_chance_color(50) == LOSS_BRIGHT  # рівно 50 — вже червоний


# --- тренування: таблиця останніх заїздів ------------------------------------


def _training_runs(n: int) -> dict[int, EffectiveRace]:
    return {i: EffectiveRace(track_id=11, car_id=21, time=20000 + i)
            for i in range(1, n + 1)}


def test_training_table_shows_last_ten_with_global_numbers():
    table = build_training_table(_training_runs(15), {11: "Meiji Rush"}, {21: "Chiron"},
                                 track_maps={11: "Osaka"})
    assert "'>6</span>" in table       # перший видимий рядок — №6
    assert "'>15</span>" in table
    assert "'>5</span>" not in table   # №1–5 за межами останніх 10
    assert table.count("Meiji Rush") == 10
    assert "Osaka - Meiji Rush" in table
    assert "Chiron" in table
    assert "00:20.015" in table


def test_training_table_row_parts():
    runs = {1: EffectiveRace(track_id=11, car_id=21, time=26499)}
    table = build_training_table(runs, {11: "Meiji Rush"}, {21: "Battista"})
    assert COMPLETE_COLOR in table     # повний рядок — зелений номер
    assert "dislike:1" in table        # перемикач 👎 на зіграному заїзді
    assert "00:26.499" in table


def test_training_table_incomplete_run_white_number():
    # авто не розпізналось (REWARDS/чужий рядок) — номер білий, авто «?»
    runs = {1: EffectiveRace(track_id=11, time=26499)}
    table = build_training_table(runs, {11: "Meiji Rush"}, {})
    assert COMPLETE_COLOR not in table
    assert "color:white;font-weight:bold'>1</span>" in table
    assert "?" in table


def test_training_table_empty_says_no_data():
    assert "no data" in build_training_table({}, {}, {})


def test_training_table_map_only_track():
    # трек ще не відомий (сесію відкрив скан результату) — показуємо карту
    runs = {1: EffectiveRace(map_id=5, car_id=21, time=26499)}
    table = build_training_table(runs, {}, {21: "Battista"}, map_names={5: "Osaka"})
    assert "Osaka" in table


def test_played_race_shows_run_grade_chevron_after_time():
    # оцінка «як проїхав» — іконка одразу після мого часу: +2 подвійний
    # шеврон угору, 0 — «≈», −1 — одинарний униз; без оцінки іконки немає
    races = {1: EffectiveRace(track_id=11, car_id=21, time=22797),
             2: EffectiveRace(track_id=11, car_id=21, time=23000),
             3: EffectiveRace(track_id=11, car_id=21, time=23100),
             4: EffectiveRace(track_id=11, car_id=21, time=23200)}
    table = build_races_table(races, {11: "Notre Dame"}, {21: "Ultima RS"},
                              run_grades={1: 2, 2: 0, 3: -1})
    assert "00:22.797</span>" not in table
    assert table.index("00:22.797") < table.index("grade-up2.svg")
    assert "grade-eq.svg" in table
    assert "grade-down.svg" in table
    assert "grade-down2.svg" not in table
    assert table.count("grade-") == 3


def test_unplayed_race_ignores_run_grade():
    races = {1: EffectiveRace(track_id=11, car_id=21, opponent_time=25000)}
    table = build_races_table(races, {11: "Notre Dame"}, {21: "Ultima RS"},
                              run_grades={1: 2})
    assert "grade-" not in table


def test_training_table_shows_run_grade_chevron_after_time():
    # тренування: той самий шеврон «як проїхав» після часу, проти історії з БД
    runs = {1: EffectiveRace(track_id=11, car_id=21, time=26499),
            2: EffectiveRace(track_id=11, car_id=21, time=26600)}
    table = build_training_table(runs, {11: "Meiji Rush"}, {21: "Battista"},
                                 run_grades={1: -2})
    assert table.index("00:26.499") < table.index("grade-down2.svg")
    assert table.count("grade-") == 1


def test_icon_uri_provides_hidpi_variant_sized_to_screen(tmp_path):
    # на HiDPI Qt бере «name@2x.svg» поруч з базовою іконкою; підкладаємо
    # копію з intrinsic size = 12·dpr, щоб піксмап ліг 1:1 без розмиття
    from alu_gauntlet_helper.views import overlay
    uri = overlay._icon_uri("grade-up.svg", 12, dpr=1.5, cache_dir=tmp_path)
    assert uri.endswith("/grade-up.svg")
    base = (tmp_path / "grade-up.svg").read_text(encoding="utf-8")
    hidpi = (tmp_path / "grade-up@2x.svg").read_text(encoding="utf-8")
    assert 'width="12" height="12"' in base
    assert 'width="18" height="18"' in hidpi
    assert 'viewBox="0 0 12 12"' in hidpi   # геометрія та сама, лише розмір растра


def test_icon_uri_without_hidpi_points_to_resource(tmp_path):
    from alu_gauntlet_helper.views import overlay
    uri = overlay._icon_uri("grade-up.svg", 12, dpr=1.0, cache_dir=tmp_path)
    assert uri.endswith("/resources/icons/grade-up.svg")
    assert not (tmp_path / "grade-up@2x.svg").exists()
