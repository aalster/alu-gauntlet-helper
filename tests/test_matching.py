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


def test_junk_last_line_does_not_drag_score_down():
    # плашка рангу під назвою авто залазить у кроп і читається сміттєвим
    # останнім рядком ("PEUGEOT\n98\nTSVWH") — матч без нього має перемогти
    m = VocabularyMatcher([(1, "Peugeot 9x8"), (2, "Peugeot 908")])
    guess = m.match("PEUGEOT\n98\nTSVWH")
    assert guess is not None
    assert guess.score >= 0.9


def test_full_text_still_wins_when_better():
    m = VocabularyMatcher(VOCAB)
    guess = m.match("BUGATTI\nCHIRON")
    assert guess.value == 2
    assert guess.score == 1.0


ROME_VIEWS = [
    SimpleNamespace(id=1, name="Roman Byroads", name_ru="Римские Тропы",
                    map_name="Rome", map_name_ru="Рим"),
    SimpleNamespace(id=2, name="Roman Tumble", name_ru="Римские Качели",
                    map_name="Rome", map_name_ru="Рим"),
]


def test_strip_map_keeps_track_prefix_when_map_on_own_line():
    """Карта "РИМ" — префікс назв треків "РИМСКИЕ ...": вирізати її можна лише
    з рядка-назви карти, а не з фрагмента назви треку."""
    r = TrackResolver(ROME_VIEWS)
    guess = r.resolve("РИМ\nРИМСКИЕ ТРО")
    assert guess is not None and guess.value == 1
    assert guess.score >= 0.9


def test_strip_map_common_prefix_fragment_stays_ambiguous():
    """Фрагмент "РИМСКИ" — спільний префікс обох треків Рима: матч є, але скор
    капнутий як неоднозначний (рев'ю підсвітить)."""
    r = TrackResolver(ROME_VIEWS)
    guess = r.resolve("РИМ\nРИМСКИ")
    assert guess is not None
    assert guess.score <= 0.6


def test_clipped_edge_letters_of_marquee_fragment():
    """Крайні літери фрагмента зрізані рамкою попапа й вгадані OCR неправильно
    ("РИМСКИЕ ТРО" → "ЭИМСКИЕ ТРС") — середина фрагмента однозначно вказує трек."""
    r = TrackResolver(ROME_VIEWS)
    guess = r.resolve("РИМ\nЭИМСКИЕ ТРС")
    assert guess is not None and guess.value == 1
    assert guess.score >= 0.9


def test_strip_map_handles_map_split_across_lines():
    """OCR розбиває "SAN FRANCISCO" на два рядки — обидва мають піти як карта,
    не забруднюючи marquee-фрагмент треку ("...USTLE RAILR..." з обрізаними
    крайніми літерами)."""
    views = [SimpleNamespace(id=1, name="Railroad Bustle", name_ru="",
                             map_name="San Francisco", map_name_ru=""),
             SimpleNamespace(id=2, name="Hilly Heights", name_ru="",
                             map_name="San Francisco", map_name_ru="")]
    r = TrackResolver(views)
    guess = r.resolve("SAN\nFRANCISCO\nISTLERAILF")
    assert guess is not None and guess.value == 1
    assert guess.score >= 0.9


def test_strip_map_merged_line_still_stripped():
    """Злитий OCR-рядок "SHANGHAIDOUBLEROUNDABOUT": карту вирізаємо частковим
    збігом, як раніше."""
    views = [SimpleNamespace(id=1, name="Double Roundabout", name_ru="",
                             map_name="Shanghai", map_name_ru="")]
    r = TrackResolver(views)
    guess = r.resolve("SHANGHAIDOUBLEROUNDABOUT")
    assert guess is not None and guess.value == 1
    assert guess.score >= 0.9


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
