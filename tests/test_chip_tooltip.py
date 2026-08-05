from alu_gauntlet_helper.views.components.chip_tooltip import (chip_tooltip_html,
                                                               prob_percent)

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
