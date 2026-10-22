"""Логіка бейджа рангу: текст і службова іконка (overclock / evo)."""
from alu_gauntlet_helper.views.components.common import EVO_ICON, OC_ICON, rank_badge_parts


def test_rank_below_max_shows_fraction_without_icon():
    assert rank_badge_parts(3000, 4000) == ("3,000 / 4,000", "")


def test_rank_equal_max_shows_rank_only():
    assert rank_badge_parts(4000, 4000) == ("4,000", "")


def test_rank_above_max_is_overclock():
    assert rank_badge_parts(4100, 4000) == ("4,100 / 4,000", OC_ICON)


def test_only_max_rank_shows_max():
    assert rank_badge_parts(0, 4000) == ("4,000", "")


def test_only_rank_shows_rank():
    assert rank_badge_parts(3000, 0) == ("3,000", "")


def test_nothing():
    assert rank_badge_parts(0, 0) == ("", "")


def test_evo_below_max_behaves_like_regular_car():
    assert rank_badge_parts(3000, 4000, evo=True) == ("3,000 / 4,000", "")


def test_evo_at_max_hides_max_and_shows_evo_icon():
    assert rank_badge_parts(4000, 4000, evo=True) == ("4,000", EVO_ICON)


def test_evo_above_max_is_not_overclock():
    assert rank_badge_parts(4300, 4000, evo=True) == ("4,300", EVO_ICON)


def test_evo_without_max_rank_has_no_icon():
    assert rank_badge_parts(3000, 0, evo=True) == ("3,000", "")
