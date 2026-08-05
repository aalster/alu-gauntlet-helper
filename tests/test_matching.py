from types import SimpleNamespace

from alu_gauntlet_helper.screen_recognition.matching import TrackResolver, VocabularyMatcher, normalize

VOCAB = [
    (1, "Hennessey Venom F5"),
    (2, "Bugatti Chiron"),
    (3, "Bugatti Chiron Pur Sport"),
    (4, "Lamborghini Invencible"),
]


def test_normalize_strips_spaces_and_punctuation():
    assert normalize("W Motors Lykan-Hyper sport!") == "WMOTORSLYKANHYPERSPORT"


def test_exact_match():
    m = VocabularyMatcher(VOCAB)
    guess = m.match("HENNESSEY VENOM F5")
    assert guess.value == 1
    assert guess.score == 1.0


def test_ocr_garbage_missing_spaces_and_swapped_letters():
    m = VocabularyMatcher(VOCAB)
    # типова помилка Tesseract: злиплі пробіли, 5 -> S
    guess = m.match("HENNESSEYVENOM FS")
    assert guess.value == 1


def test_below_threshold_returns_none():
    m = VocabularyMatcher(VOCAB)
    assert m.match("ZZZZZZZZZZ") is None
    assert m.match("") is None


def test_candidates_best_first_and_deduped():
    m = VocabularyMatcher(VOCAB)
    guess = m.match("BUGATTI CHIRON")
    assert guess.value == 2
    candidate_ids = [c[0] for c in guess.candidates]
    assert 3 in candidate_ids          # Pur Sport — близький кандидат
    assert len(candidate_ids) == len(set(candidate_ids))


def test_resolve_track_only_prefers_named_map():
    views = [SimpleNamespace(id=1, name="Hell Vale", name_ru="", map_name="The Caribbean", map_name_ru=""),
             SimpleNamespace(id=2, name="Hell Valley", name_ru="", map_name="Nevada", map_name_ru="")]
    r = TrackResolver(views)
    guess = r.resolve_track_only("HELL VALE", map_name="The Caribbean")
    assert guess is not None and guess.value == 1


def test_resolve_track_only_falls_back_on_map_miss():
    views = [SimpleNamespace(id=1, name="Hell Vale", name_ru="", map_name="The Caribbean", map_name_ru=""),
             SimpleNamespace(id=2, name="Namba Park", name_ru="", map_name="Osaka", map_name_ru="")]
    r = TrackResolver(views)
    # іконка хибно вказала Osaka — трек все одно знаходиться глобальним fallback-ом
    guess = r.resolve_track_only("HELL VALE", map_name="Osaka")
    assert guess is not None and guess.value == 1
