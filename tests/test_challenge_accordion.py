from pathlib import Path
from types import SimpleNamespace

import cv2
import pytest

from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.matching import TrackResolver, VocabularyMatcher
from alu_gauntlet_helper.screen_recognition.screens.challenge_accordion import ChallengeAccordionExtractor

FIXTURES = Path(__file__).parent / "fixtures"
TESSERACT_OK = ocr.configure_tesseract() and ocr.is_available()

# Словники-стаби: реальні назви з гри, які видно на фікстурних скріншотах.
# TrackResolver будується з TrackView-подібних об'єктів (id, name, map_name).
TRACK_SF_RAILROAD = 101
TRACK_NORWAY_FUSION = 102
TRACK_SHANGHAI_ROUNDABOUT = 103
TRACK_US_TWISTER = 104
TRACK_CAIRO_GEZIRA = 105
TRACK_PARIS_NOTRE_DAME = 106
TRACK_SF_CENTER = 107  # другий трек Сан-Франциско: дизамбігуація реально працює


def track_view(track_id: int, name: str, map_name: str):
    return SimpleNamespace(id=track_id, name=name, map_name=map_name)


TRACK_VIEWS = [
    track_view(TRACK_SF_RAILROAD, "Railroad Bustle", "San Francisco"),
    track_view(TRACK_SF_CENTER, "Out of the Center", "San Francisco"),
    track_view(TRACK_NORWAY_FUSION, "Future Fusion", "Norway"),
    track_view(TRACK_SHANGHAI_ROUNDABOUT, "Double Roundabout", "Shanghai"),
    track_view(TRACK_US_TWISTER, "It's a Twister", "US Midwest"),
    track_view(TRACK_CAIRO_GEZIRA, "Gezira Island", "Cairo"),
    track_view(TRACK_PARIS_NOTRE_DAME, "Notre Dame", "Paris"),
]

# У словнику авто НАВМИСНО є й суперники з лівого боку панелей (Bugatti Chiron
# на after_1, W Motors Lykan на after_4, Ultima RS на before_5/race1 тощо):
# читання не того боку дало б ХИБНИЙ id і завалило тест.
CAR_ULTIMA_RS = 201
CAR_BUGATTI_CHIRON = 202
CAR_FERRARI_SF90 = 203
CAR_KOENIGSEGG_CCXR = 204
CAR_LYKAN_HYPERSPORT = 205
CAR_RIMAC_NEVERA_TA = 206
CAR_VOCAB = [
    (CAR_ULTIMA_RS, "Ultima RS"),
    (CAR_BUGATTI_CHIRON, "Bugatti Chiron"),
    (CAR_FERRARI_SF90, "Ferrari SF90 Stradale"),
    (CAR_KOENIGSEGG_CCXR, "Koenigsegg CCXR"),
    (CAR_LYKAN_HYPERSPORT, "W Motors Lykan Hypersport"),
    (CAR_RIMAC_NEVERA_TA, "Rimac Nevera Time Attack"),
]


def make_extractor():
    return ChallengeAccordionExtractor(TrackResolver(TRACK_VIEWS), VocabularyMatcher(CAR_VOCAB))


def extract_one(fixture: str):
    img = cv2.imread(str(FIXTURES / fixture))
    captures = make_extractor().extract(img)
    assert len(captures) == 1
    return captures[0]


def fixture_guard(fixture: str):
    return pytest.mark.skipif(not (FIXTURES / fixture).exists(), reason="немає фікстури")


# --- AFTER: гонку їхали — дані ГРАВЦЯ з правого боку панелі ------------------

@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@fixture_guard("accordion_after_1.png")
def test_after_1_player_data():
    """Скріншот: RACE 1, WON; зліва суперник BUGATTI CHIRON 5,105, справа гравець
    FERRARI SF90 STRADALE 4,795; TIME TO BEAT 00:19.152, YOUR TIME 00:19.130."""
    c = extract_one("accordion_after_1.png")
    assert c.race_number == 1
    assert c.track and c.track.value == TRACK_SF_RAILROAD
    # Має бути авто ГРАВЦЯ (правий бік), а не суперника (лівий бік)
    assert c.car and c.car.value == CAR_FERRARI_SF90
    assert c.car.value != CAR_BUGATTI_CHIRON
    assert c.rank == 4795  # ранг гравця, не 5105 суперника
    assert c.time == 19130  # YOUR TIME, не 19152 (TIME TO BEAT)
    assert c.panel_image


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@fixture_guard("accordion_after_2.png")
def test_after_2_player_data():
    """Скріншот: RACE 2, WON; обидва боки KOENIGSEGG CCXR 4,998; трек U.S. MIDWEST
    IT'S A TWISTER; TIME TO BEAT 00:26.591, YOUR TIME 00:25.782."""
    c = extract_one("accordion_after_2.png")
    assert c.race_number == 2
    assert c.track and c.track.value == TRACK_US_TWISTER
    assert c.car and c.car.value == CAR_KOENIGSEGG_CCXR
    assert c.rank == 4998
    assert c.time == 25782  # YOUR TIME, не 26591 (TIME TO BEAT)


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@fixture_guard("accordion_after_4.png")
def test_after_4_lost_race_red_time():
    """Скріншот: RACE 4, LOST; зліва суперник W MOTORS LYKAN HYPERSPORT 4,683,
    справа гравець BUGATTI CHIRON 5,130; трек CAIRO GEZIRA ISLAND;
    TIME TO BEAT 00:24.164, YOUR TIME 00:24.182 ЧЕРВОНИМ (програна гонка)."""
    c = extract_one("accordion_after_4.png")
    assert c.race_number == 4
    assert c.track and c.track.value == TRACK_CAIRO_GEZIRA
    assert c.car and c.car.value == CAR_BUGATTI_CHIRON
    assert c.car.value != CAR_LYKAN_HYPERSPORT
    assert c.rank == 5130
    assert c.time == 24182  # червоний час читається через max-канальний фолбек OCR


# --- BEFORE: гонку ще не їхали — лише номер гонки і трек ---------------------
# Дані суперника (його авто і TIME TO BEAT) НЕ повертаються: саме їх раніше
# помилково зберігали як результат гравця.

@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@fixture_guard("accordion_before_1.png")
def test_before_1_no_opponent_data():
    """Скріншот: RACE 1, зліва суперник BUGATTI CHIRON 5,105, TIME TO BEAT
    00:19.152, справа SELECT CAR; трек SAN FRANCISCO RAILROAD BUSTLE."""
    c = extract_one("accordion_before_1.png")
    assert c.race_number == 1
    # Рядок треку — це маркі (рухомий рядок), на цьому кадрі він прокручений
    # до "BUSTLE   RAIL". TrackResolver упізнає карту SAN FRANCISCO, а фрагмент
    # шукає як підрядок ПОДВОЄНОЇ назви треку — тож і мід-скрол кадр дає трек.
    assert c.track and c.track.value == TRACK_SF_RAILROAD
    assert c.car is None
    assert c.rank is None  # не 5105 суперника
    assert c.time is None  # не 19152 (TIME TO BEAT суперника)
    assert c.panel_image


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@fixture_guard("accordion_before_3.png")
def test_before_3_no_opponent_data():
    """Скріншот: RACE 3, зліва суперник RIMAC NEVERA TIME ATTACK 4,835,
    TIME TO BEAT 00:19.736; трек NORWAY FUTURE FUSION."""
    c = extract_one("accordion_before_3.png")
    assert c.race_number == 3
    assert c.track and c.track.value == TRACK_NORWAY_FUSION
    assert c.car is None
    assert c.rank is None
    assert c.time is None


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@fixture_guard("accordion_before_5.png")
def test_before_5_no_opponent_data():
    """Скріншот: RACE 5, зліва суперник ULTIMA RS 4,644, TIME TO BEAT 00:30.847;
    трек SHANGHAI DOUBLE ROUNDABOUT."""
    c = extract_one("accordion_before_5.png")
    assert c.race_number == 5
    assert c.track and c.track.value == TRACK_SHANGHAI_ROUNDABOUT
    assert c.car is None
    assert c.rank is None
    assert c.time is None


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@fixture_guard("accordion_race1.png")
def test_old_fixture_race1_is_before_variant():
    """Стара фікстура (before-варіант, інший челендж): RACE 1, трек PARIS NOTRE
    DAME, суперник ULTIMA RS 4,644, TIME TO BEAT 00:22.797. Семантика ЗМІНЕНА:
    дані суперника більше не витягуються."""
    c = extract_one("accordion_race1.png")
    assert c.race_number == 1
    assert c.track and c.track.value == TRACK_PARIS_NOTRE_DAME
    assert c.car is None
    assert c.rank is None  # раніше тут помилково було 4644 (ранг суперника)
    assert c.time is None  # раніше тут помилково було 22797 (час суперника)


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
def test_non_accordion_image_returns_empty():
    import numpy as np
    img = np.zeros((1600, 2560, 3), dtype=np.uint8)
    assert make_extractor().extract(img) == []
