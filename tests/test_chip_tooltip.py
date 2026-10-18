from alu_gauntlet_helper import ui_lang
from alu_gauntlet_helper.views import style
from alu_gauntlet_helper.views.components.chip_tooltip import (chip_tooltip_html,
                                                               goal_label, prob_percent,
                                                               win_chance_tooltip)

# Єдиний тултіп чипа треку: з наявних частин — «Збіг ... {p}%», таблиця часів
# (суперник / моя медіана / різниця), превʼю маршруту внизу. Чого немає —
# просто не виводиться; немає нічого — тултіп порожній ("" → не вішати).


def test_prob_percent_never_reaches_100():
    # завжди є інші кандидати з ненульовою вагою (суперник міг проїхати
    # погано) — показуємо щонайбільше 99%
    assert prob_percent(1.0) == 99
    assert prob_percent(0.999) == 99
    assert prob_percent(0.794) == 79


def test_tooltip_full_contains_percent_times_delta_and_icon():
    html = chip_tooltip_html(0.79, stats=(83400, 12), opponent_time=84000,
                             icon_html="<img src='x'>")
    assert "79%" in html
    assert "01:23.400" in html  # моя медіана
    assert "01:24.000" in html  # час суперника
    assert "−0.600" in html     # мій мінус суперника: я швидший
    assert html.rstrip().endswith("<img src='x'>")  # маршрут — у самому низу
    assert "</table><br><br><img" in html  # порожній рядок-відступ перед іконкою


def test_tooltip_caps_displayed_percent():
    html = chip_tooltip_html(0.998, stats=(20000, 3), opponent_time=20000)
    assert "99%" in html and "100%" not in html


def test_tooltip_without_probability_skips_header():
    html = chip_tooltip_html(None, stats=(20000, 3), opponent_time=21000)
    assert "%" not in html
    assert "00:20.000" in html and "00:21.000" in html


def test_tooltip_without_opponent_time_shows_only_median_row():
    html = chip_tooltip_html(None, stats=(20000, 3), opponent_time=0)
    assert "00:20.000" in html
    assert "+" not in html and "−" not in html  # без суперника немає різниці


def test_tooltip_without_stats_shows_opponent_time_without_delta():
    html = chip_tooltip_html(None, stats=None, opponent_time=21000)
    assert "00:21.000" in html
    assert "+" not in html and "−" not in html


def test_tooltip_icon_only():
    assert chip_tooltip_html(None, None, 0, "<img src='x'>") == "<img src='x'>"


def test_tooltip_empty_without_any_info():
    assert chip_tooltip_html(None, None, 0) == ""


# --- Тултіп загального шансу перемоги: P(≥3), P(≥4), P(≥5) -----------------
# за 4 і 5 перемог дають додаткові очки — бонус поверх перемоги (≥3);
# таблиця (відсоток вирівняний праворуч | підпис), кольори відсотків —
# пороги win_chance_color (як велика цифра)


def chance_row(pct: int, label: str) -> str:
    value = f"<span style='color:{style.win_chance_color(pct)}'>{pct}%</span>"
    return (f"<tr><td align='right'>{value}</td>"
            f"<td style='padding-left:8px;white-space:nowrap'>{label}</td></tr>")


def test_win_chance_tooltip_cumulative_table():
    dist = [0.05, 0.1, 0.2, 0.3, 0.25, 0.1]
    assert win_chance_tooltip(dist) == (
        "<table cellspacing='0' cellpadding='1'>"
        + chance_row(65, "chance to win at least 3 races")   # 0.3 + 0.25 + 0.1
        + chance_row(35, "chance to win at least 4 races")   # 0.25 + 0.1
        + chance_row(10, "chance to win all races")
        + "</table>")


def test_win_chance_tooltip_percent_colors():
    # 100 (>75) зелений, 50 (≤50) червоний, 20 — теж червоний
    html = win_chance_tooltip([0.0, 0.0, 0.0, 0.5, 0.3, 0.2])
    assert f"color:{style.WIN_BRIGHT}'>100%" in html
    assert f"color:{style.LOSS_BRIGHT}'>50%" in html
    assert f"color:{style.LOSS_BRIGHT}'>20%" in html


def test_win_chance_tooltip_uk_labels():
    original = ui_lang.current_ui_language()
    ui_lang.set_ui_language(ui_lang.UK)
    try:
        html = win_chance_tooltip([0.0, 0.0, 0.0, 0.5, 0.3, 0.2])
    finally:
        ui_lang.set_ui_language(original)
    assert chance_row(100, "шанс виграти щонайменше 3 гонки") in html
    assert chance_row(50, "шанс виграти щонайменше 4 гонки") in html
    assert chance_row(20, "шанс виграти всі гонки") in html


# --- кнопки режимів підбору 3/5 · 4/5 · 5/5 --------------------------------


def test_goal_label_with_and_without_chance():
    # «3/5» — кольору кнопки, відсоток — порогів win_chance_color
    dist = [0.05, 0.1, 0.2, 0.3, 0.25, 0.1]
    assert goal_label(3, dist) == f"3/5 <span style='color:{style.RANK_DOWN}'>65%</span>"
    assert goal_label(4, dist) == f"4/5 <span style='color:{style.LOSS_BRIGHT}'>35%</span>"
    assert goal_label(5, [0, 0, 0, 0, 0, 1.0]) == (
        f"5/5 <span style='color:{style.WIN_BRIGHT}'>100%</span>")
    assert goal_label(5, None) == "5/5"  # без часів суперника — лише режим


def test_win_chance_tooltip_bolds_goal_row():
    dist = [0.05, 0.1, 0.2, 0.3, 0.25, 0.1]
    html = win_chance_tooltip(dist, goal=4)
    assert html.count("<b>") == 2  # відсоток і підпис лише рядка 4/5
    assert "<b>chance to win at least 4 races</b>" in html
