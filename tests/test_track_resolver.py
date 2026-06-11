from types import SimpleNamespace

import pytest

from alu_gauntlet_helper.screen_recognition.matching import TrackResolver


def tv(track_id: int, name: str, map_name: str):
    return SimpleNamespace(id=track_id, name=name, map_name=map_name)


TRACKS = [
    tv(1, "Railroad Bustle", "San Francisco"),
    tv(2, "Out of the Center", "San Francisco"),
    tv(3, "Notre Dame", "Paris"),            # єдиний трек карти
    tv(4, "Future Fusion", "Norway"),
    tv(5, "Hell Vale", "Norway"),
    # дві майже однакові назви на одній карті — перевірка неоднозначності
    tv(6, "Speed Way A", "Tokyo"),
    tv(7, "Speed Way B", "Tokyo"),
]


@pytest.fixture
def resolver():
    return TrackResolver(TRACKS)


def test_full_text_resolves_with_high_score(resolver):
    guess = resolver.resolve("SAN\nFRANCISCO\nRAILROAD BUSTLE")
    assert guess and guess.value == 1
    assert guess.score >= 0.9


def test_mid_scroll_marquee_fragment(resolver):
    # "3USTLERAI" — фаза прокрутки "RAILROAD BUSTLE": підрядок подвоєної назви
    guess = resolver.resolve("SAN\nFRANCISCO\n3USTLERAI")
    assert guess and guess.value == 1
    assert guess.score >= 0.75


def test_mid_scroll_other_track_same_map(resolver):
    guess = resolver.resolve("FRANCISCO\nCENTEROUTOF")
    assert guess and guess.value == 2


def test_single_track_map_without_fragment(resolver):
    guess = resolver.resolve("PARIS")
    assert guess and guess.value == 3
    assert guess.score == pytest.approx(0.85)


def test_multi_track_map_without_fragment_returns_none(resolver):
    assert resolver.resolve("NORWAY") is None


def test_ambiguous_tracks_low_score_with_both_candidates(resolver):
    guess = resolver.resolve("TOKYO\nSPEED WAY")
    assert guess and guess.value in (6, 7)
    assert guess.score <= 0.6
    assert {c[0] for c in guess.candidates} >= {6, 7}


def test_no_map_falls_back_to_global_matching(resolver):
    guess = resolver.resolve("NOTRE DAME")
    assert guess and guess.value == 3


def test_garbage_returns_none(resolver):
    assert resolver.resolve("@#$%") is None
    assert resolver.resolve("") is None
    assert resolver.resolve("XQZWVKJY PLMNB") is None


def test_map_plus_track_on_single_line(resolver):
    # OCR може віддати все одним рядком — карта вирізається, а не губиться трек
    guess = resolver.resolve("SAN FRANCISCO RAILROAD BUSTLE")
    assert guess and guess.value == 1
    assert guess.score >= 0.75


def test_empty_vocabulary_returns_none():
    resolver = TrackResolver([])
    assert resolver.resolve("SAN FRANCISCO RAILROAD BUSTLE") is None


def test_track_with_empty_map_name_resolves_via_fallback():
    # TrackResolver skips tracks with empty map_name in the map index,
    # but build_track_matcher includes them in the fallback matcher.
    local_tracks = [
        tv(10, "Ghost Circuit", ""),
    ]
    resolver = TrackResolver(local_tracks)
    guess = resolver.resolve("Ghost Circuit")
    assert guess and guess.value == 10
