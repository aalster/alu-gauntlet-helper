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


def test_track_name_contains_other_map_name():
    # Трек "Paris of the East" на карті Shanghai містить підрядок з назвою ІНШОЇ
    # карти — "Paris". У БД карти йдуть алфавітно (Paris ПЕРЕД Shanghai), тож на
    # рівному partial_ratio=100 ("PARIS" і "SHANGHAI" обидва присутні в тексті)
    # не можна віддавати перемогу першій-ліпшій короткій назві: реальна карта —
    # довша SHANGHAI, що присутня повністю.
    local_tracks = [
        tv(10, "Along the Seine", "Paris"),
        tv(11, "Metro", "Paris"),
        tv(12, "Notre Dame", "Paris"),
        tv(13, "Double Roundabout", "Shanghai"),
        tv(14, "Paris of the East", "Shanghai"),
    ]
    resolver = TrackResolver(local_tracks)
    # типовий OCR-вивід цього екрана: назва треку на двох рядках
    guess = resolver.resolve("SHANGHAI\nPARISOF\nHN THEEAST")
    assert guess and guess.value == 14


def test_track_with_empty_map_name_resolves_via_fallback():
    # TrackResolver skips tracks with empty map_name in the map index,
    # but build_track_matcher includes them in the fallback matcher.
    local_tracks = [
        tv(10, "Ghost Circuit", ""),
    ]
    resolver = TrackResolver(local_tracks)
    guess = resolver.resolve("Ghost Circuit")
    assert guess and guess.value == 10


def tv_ru(track_id: int, name: str, map_name: str, name_ru: str, map_name_ru: str):
    return SimpleNamespace(id=track_id, name=name, map_name=map_name, name_ru=name_ru, map_name_ru=map_name_ru)


RU_TRACKS = [
    # карта з перекладом: на RU-екрані і карта, і трек російською
    tv_ru(20, "Echo Drift", "Chicago", "Эходрифт", "Чикаго"),
    tv_ru(21, "Ironclad Descent", "Chicago", "Жесткая Посадка", "Чикаго"),
    # карта без перекладу (Mt. Fuji): на RU-екрані англ. карта + рос. назва треку
    tv_ru(22, "Countryside Sprint", "Mt. Fuji", "Деревенский Спринт", ""),
    tv_ru(23, "Bullet Train Sprint", "Mt. Fuji", "Молниеносный Спринт", ""),
]


def test_ru_screen_translated_map_and_track():
    resolver = TrackResolver(RU_TRACKS)
    guess = resolver.resolve("ЧИКАГО\nЖЕСТКАЯ ПОСАДКА")
    assert guess and guess.value == 21


def test_ru_screen_untranslated_map_with_ru_track_name():
    resolver = TrackResolver(RU_TRACKS)
    guess = resolver.resolve("MT. FUJI\nМОЛНИЕНОСНЫЙ СПРИНТ")
    assert guess and guess.value == 23
    guess = resolver.resolve("MT. FUJI\nДЕРЕВЕНСКИЙ СПРИНТ")
    assert guess and guess.value == 22


def test_en_screen_untranslated_map_still_resolves_english_track():
    resolver = TrackResolver(RU_TRACKS)
    guess = resolver.resolve("MT. FUJI\nBULLET TRAIN SPRINT")
    assert guess and guess.value == 23
