"""Бейджі «Δ · 7/10» проти суперника: картка гонки і колонка підбору авто
показують різницю часу, а не відсоток шансу."""
from PyQt6.QtWidgets import QApplication

from alu_gauntlet_helper.services.assistant import BeatStats, VsSuggestion, win_prob
from alu_gauntlet_helper.services.challenge_session import EffectiveRace
from alu_gauntlet_helper.services.races import RaceAggregate
from alu_gauntlet_helper.views import style
from alu_gauntlet_helper.views.components.race_card import RaceCard
from alu_gauntlet_helper.views.components.vs_suggestion import VsStatsWidget, VsSuggestionWidget

app = QApplication.instance() or QApplication([])


def _card_with(beat):
    card = RaceCard(1, on_toggle=lambda *a: None, on_edit=lambda *a: None)
    e = EffectiveRace(track_id=11, suggested_car_id=21, opponent_time=25000)
    card.update_card(e, None, None, beat, checked=False, selected=False)
    return card


def test_race_card_badge_shows_delta_not_percent():
    card = _card_with(BeatStats(7, 10, 1300))
    # Δ=+1300 (я швидший) → «−1.300» зеленим, лічильник поруч
    assert card.prob_label.text() == "−1.300"
    assert style.WIN_BRIGHT in card.prob_label.styleSheet()
    assert card.beat_label.text().startswith("7/10")


def test_race_card_badge_red_when_slower():
    card = _card_with(BeatStats(1, 10, -2000))
    assert card.prob_label.text() == "+2.000"
    assert style.LOSS_BRIGHT in card.prob_label.styleSheet()


def _vs(delta, wins=7, n=10):
    return VsSuggestion(car_id=21, car_name="Ultima RS", avg_time=25000 - delta,
                        race_count=n, beat_count=wins, sample_count=n,
                        opponent_time=25000, delta=delta, p=win_prob(delta))


def test_vs_stats_widget_headline_is_delta():
    w = VsStatsWidget(_vs(1300))
    assert w.delta_label.text() == "−1.300"
    assert style.WIN_BRIGHT in w.delta_label.styleSheet()
    assert w.beaten_label.text().startswith("7/10")
    # відсоток — лише в тултіпі, як модельна оцінка гонки
    assert "90%" in w.toolTip()  # Φ(1.3)


def test_vs_stats_widget_red_when_slower():
    w = VsStatsWidget(_vs(-2000, wins=1))
    assert w.delta_label.text() == "+2.000"
    assert style.LOSS_BRIGHT in w.delta_label.styleSheet()


def test_vs_suggestion_widget_builds_with_and_without_opponent():
    agg = RaceAggregate(track_id=11, car_id=21, car_name="Ultima RS")
    VsSuggestionWidget(agg, _vs(1300), has_opponent_time=True)
    VsSuggestionWidget(agg, _vs(0, wins=0), has_opponent_time=False)
