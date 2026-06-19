from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.matching import TrackResolver, build_car_matcher
from alu_gauntlet_helper.screen_recognition.screens.before_race import BeforeRaceExtractor

FIXTURES = Path(__file__).parent / "fixtures"
TESSERACT_OK = ocr.configure_tesseract() and ocr.is_available()

TRACK_CAIRO_GEZIRA = 105
TRACK_SCOTLAND_ROCKY = 110
TRACK_SF_RAILROAD = 101
TRACK_NORWAY_FUSION = 102
TRACK_SCOTLAND_GHOST = 111
TRACK_TUSCANY_VINEYARD = 120
TRACK_ROME_TUMBLE = 121
TRACK_NEVADA_TUNNEL = 122


def track_view(track_id: int, name: str, map_name: str):
    return SimpleNamespace(id=track_id, name=name, map_name=map_name)


TRACK_VIEWS = [
    track_view(TRACK_CAIRO_GEZIRA, "Gezira Island", "Cairo"),
    track_view(TRACK_SCOTLAND_ROCKY, "Rocky Valley", "Scotland"),
    track_view(TRACK_SF_RAILROAD, "Railroad Bustle", "San Francisco"),
    track_view(TRACK_NORWAY_FUSION, "Future Fusion", "Norway"),
    track_view(TRACK_SCOTLAND_GHOST, "Ghost Ships", "Scotland"),
    track_view(TRACK_TUSCANY_VINEYARD, "Vineyard Voyage", "Tuscany"),
    track_view(TRACK_ROME_TUMBLE, "Roman Tumble", "Rome"),
    track_view(TRACK_NEVADA_TUNNEL, "Tunnel Sprint", "Nevada"),
]

# Праве авто матчапу = авто гравця.
CAR_LYKAN = 201
CAR_RIMAC_TIME_ATTACK = 202
CAR_BUGATTI_CHIRON = 203
CAR_KOENIGSEGG_CCXR = 204

CARS = [
    SimpleNamespace(id=CAR_LYKAN, name="W Motors Lykan Hypersport"),
    SimpleNamespace(id=CAR_RIMAC_TIME_ATTACK, name="Rimac Nevera Time Attack"),
    SimpleNamespace(id=CAR_BUGATTI_CHIRON, name="Bugatti Chiron"),
    SimpleNamespace(id=CAR_KOENIGSEGG_CCXR, name="Koenigsegg CCXR"),
]


def make_extractor():
    return BeforeRaceExtractor(TrackResolver(TRACK_VIEWS), build_car_matcher(CARS))


def extract_one(fixture: str):
    img = cv2.imread(str(FIXTURES / fixture))
    captures = make_extractor().extract(img)
    assert len(captures) == 1
    return captures[0]


def fixture_guard(fixture: str):
    return pytest.mark.skipif(not (FIXTURES / fixture).exists(), reason="немає фікстури")


# --- BEFORE RACE: номер гонки, трек і авто гравця (праве в матчапі) ---

@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@fixture_guard("before_race_1.png")
def test_before_race_1_cairo():
    """Скріншот: поточна гонка 1 (ярко-біла "1", решта тьмяні); карта CAIRO,
    трек GEZIRA ISLAND; праве авто гравця — W MOTORS LYKAN HYPERSPORT."""
    c = extract_one("before_race_1.png")
    assert c.race_number == 1
    assert c.track and c.track.value == TRACK_CAIRO_GEZIRA
    assert c.car and c.car.value == CAR_LYKAN
    assert c.rank == 4683
    assert c.time is None
    assert c.source_screen == "before_race"
    assert c.panel_image


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@fixture_guard("before_race_4.png")
def test_before_race_4_scotland_with_played_flags():
    """Скріншот: гонки 1-3 уже зіграні (кольорові іконки прапорів), поточна 4
    ярко-біла, 5 тьмяна; карта SCOTLAND, трек ROCKY VALLEY, праве авто
    KOENIGSEGG CCXR. Перевіряє, що номер береться саме з білого слота, а не з
    кольорових іконок зіграних гонок."""
    c = extract_one("before_race_4.png")
    assert c.race_number == 4
    assert c.track and c.track.value == TRACK_SCOTLAND_ROCKY
    assert c.car and c.car.value == CAR_KOENIGSEGG_CCXR
    assert c.rank == 4998
    assert c.time is None


# Реальні скріншоти гри (2560x1600), де стилізований курсивний шрифт ламав OCR:
# цифру поточної гонки tesseract читав хибно ("1"→None, "2"→"4"), а назву треку
# світло-блакитна карта + білий трек на яскравому тлі робили нечитабельною в
# сірому каналі. Регресія для deshear-голосування цифри й мультиканального треку.
# Також перевіряє розпізнавання правого авто гравця.
@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@pytest.mark.parametrize("fixture, race_number, track_id, car_id, rank", [
    ("before_race_1_scotland.png", 1, TRACK_SCOTLAND_GHOST, CAR_RIMAC_TIME_ATTACK, 4835),
    ("before_race_1_tuscany.png", 1, TRACK_TUSCANY_VINEYARD, CAR_BUGATTI_CHIRON, 5130),
    ("before_race_2_rome.png", 2, TRACK_ROME_TUMBLE, CAR_KOENIGSEGG_CCXR, 4998),
    ("before_race_3_nevada.png", 3, TRACK_NEVADA_TUNNEL, CAR_RIMAC_TIME_ATTACK, 4835),
])
def test_before_race_stylized_font(fixture, race_number, track_id, car_id, rank):
    if not (FIXTURES / fixture).exists():
        pytest.skip(f"немає фікстури {fixture}")
    c = extract_one(fixture)
    assert c.race_number == race_number
    assert c.track and c.track.value == track_id
    assert c.car and c.car.value == car_id
    assert c.rank == rank
    assert c.time is None


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@pytest.mark.parametrize("other", [
    "accordion_before_1.png", "accordion_after_1.png",
    "race_result_4_lost.png", "challenge_complete_won.png",
])
@fixture_guard("accordion_before_1.png")
def test_other_screens_return_empty(other):
    """Інші екрани челенджа не мають індикатора "RACE 1..5" з білим номером —
    BeforeRaceExtractor має повертати [] (інакше вкрав би чужий екран)."""
    img = cv2.imread(str(FIXTURES / other))
    if img is None:
        pytest.skip(f"немає фікстури {other}")
    assert make_extractor().extract(img) == []


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
def test_blank_image_returns_empty():
    img = np.zeros((1600, 2560, 3), dtype=np.uint8)
    assert make_extractor().extract(img) == []
