from alu_gauntlet_helper.screen_recognition.matching import VocabularyMatcher, normalize

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
