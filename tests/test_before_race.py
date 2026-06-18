from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.matching import TrackResolver
from alu_gauntlet_helper.screen_recognition.screens.before_race import BeforeRaceExtractor

FIXTURES = Path(__file__).parent / "fixtures"
TESSERACT_OK = ocr.configure_tesseract() and ocr.is_available()

TRACK_CAIRO_GEZIRA = 105
TRACK_SCOTLAND_ROCKY = 110
TRACK_SF_RAILROAD = 101
TRACK_NORWAY_FUSION = 102


def track_view(track_id: int, name: str, map_name: str):
    return SimpleNamespace(id=track_id, name=name, map_name=map_name)


TRACK_VIEWS = [
    track_view(TRACK_CAIRO_GEZIRA, "Gezira Island", "Cairo"),
    track_view(TRACK_SCOTLAND_ROCKY, "Rocky Valley", "Scotland"),
    track_view(TRACK_SF_RAILROAD, "Railroad Bustle", "San Francisco"),
    track_view(TRACK_NORWAY_FUSION, "Future Fusion", "Norway"),
]


def make_extractor():
    return BeforeRaceExtractor(TrackResolver(TRACK_VIEWS))


def extract_one(fixture: str):
    img = cv2.imread(str(FIXTURES / fixture))
    captures = make_extractor().extract(img)
    assert len(captures) == 1
    return captures[0]


def fixture_guard(fixture: str):
    return pytest.mark.skipif(not (FIXTURES / fixture).exists(), reason="немає фікстури")


# --- BEFORE RACE: лише номер гонки і трек; даних суперника/гравця не беремо ---

@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@fixture_guard("before_race_1.png")
def test_before_race_1_cairo():
    """Скріншот: поточна гонка 1 (ярко-біла "1", решта тьмяні); карта CAIRO,
    трек GEZIRA ISLAND."""
    c = extract_one("before_race_1.png")
    assert c.race_number == 1
    assert c.track and c.track.value == TRACK_CAIRO_GEZIRA
    assert c.car is None
    assert c.rank is None
    assert c.time is None
    assert c.source_screen == "before_race"
    assert c.panel_image


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@fixture_guard("before_race_4.png")
def test_before_race_4_scotland_with_played_flags():
    """Скріншот: гонки 1-3 уже зіграні (кольорові іконки прапорів), поточна 4
    ярко-біла, 5 тьмяна; карта SCOTLAND, трек ROCKY VALLEY. Перевіряє, що номер
    береться саме з білого слота, а не з кольорових іконок зіграних гонок."""
    c = extract_one("before_race_4.png")
    assert c.race_number == 4
    assert c.track and c.track.value == TRACK_SCOTLAND_ROCKY
    assert c.car is None
    assert c.rank is None
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
