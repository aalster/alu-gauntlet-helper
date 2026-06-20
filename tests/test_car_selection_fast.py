"""Тести ЕКСПЕРИМЕНТАЛЬНОГО CarSelectionFastExtractor (екран "ВЫБОР АВТО").

Той самий екран, що його обробляє ChallengeAccordionExtractor, але швидкий шлях:
розгорнута панель і номер гонки — геометрично (0 OCR), мова — одним читанням
бейджа. Перевіряємо коректність на всіх RU-фікстурах CAR SELECTION (включно з
двома новими — car_selection_ru_*) і що екстрактор не краде чужі екрани.

Словник — реальний (tests/recognition_vocab), бо швидкий екстрактор резолвить
повний набір назв карт/треків/авто.
"""
from pathlib import Path

import cv2
import numpy as np
import pytest

from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.screens.car_selection_fast import (
    CarSelectionFastExtractor, detect_expanded_panel,
)
from tests.recognition_vocab import build_resolvers, car_label, track_label

FIXTURES = Path(__file__).parent / "fixtures"
TESSERACT_OK = ocr.configure_tesseract() and ocr.is_available()

_TRACK_RESOLVER, _CAR_MATCHER, _TV, _CV = build_resolvers()


def make_extractor():
    return CarSelectionFastExtractor(_TRACK_RESOLVER, _CAR_MATCHER)


def fixture_guard(fixture: str):
    return pytest.mark.skipif(not (FIXTURES / fixture).exists(), reason="немає фікстури")


# (фікстура, номер, (карта, трек), авто, ранг)
RU_CASES = [
    ("car_selection_ru_1_sf.png", 1, ("San Francisco", "Railroad Bustle"),
     "Rimac Nevera Time Attack", 4835),
    ("car_selection_ru_2_auckland.png", 2, ("Auckland", "Straight Sprint"),
     "Ferrari SF90 Stradale", 4795),
    ("accordion_ru_1_nevada.png", 1, ("Nevada", "Bridge to Bridge"),
     "Bugatti Chiron", 5130),
    ("accordion_ru_2_osaka.png", 2, ("Osaka", "Namba Park"),
     "Vanda Electrics Dendrobium", 4099),
    ("accordion_ru_3_new_york.png", 3, ("New York", "Wall Street Ride"),
     "Koenigsegg CCXR", 4998),
    ("accordion_ru_4_singapore.png", 4, ("Singapore", "Urban Rush"),
     "Rimac Nevera Time Attack", 4835),
    ("accordion_ru_5_scotland.png", 5, ("Scotland", "Rocky Valley"),
     "Ferrari SF90 Stradale", 4795),
]


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@pytest.mark.parametrize("fixture, race, track, car, rank", RU_CASES)
def test_ru_car_selection(fixture, race, track, car, rank):
    if not (FIXTURES / fixture).exists():
        pytest.skip("немає фікстури")
    img = cv2.imread(str(FIXTURES / fixture))
    caps = make_extractor().extract(img)
    assert len(caps) == 1
    c = caps[0]
    assert c.race_number == race
    assert c.track and track_label(_TV, c.track.value) == track
    assert c.car and car_label(_CV, c.car.value) == car
    assert c.rank == rank
    assert c.time is None
    assert c.game_language == "ru"
    assert c.source_screen == "car_selection_fast"
    assert c.panel_image


# Номер гонки й розгорнута панель — ГЕОМЕТРИЧНО, без OCR: працює навіть без tesseract.
@pytest.mark.parametrize("fixture, race", [(f, r) for f, r, *_ in RU_CASES])
def test_panel_detection_no_ocr(fixture, race):
    if not (FIXTURES / fixture).exists():
        pytest.skip("немає фікстури")
    img = cv2.imread(str(FIXTURES / fixture))
    detected = detect_expanded_panel(img)
    assert detected is not None
    assert detected[2] == race  # номер гонки з геометрії


# Дешевий гейт (C6): на чужих екранах патерн панелей не складається → [].
@pytest.mark.parametrize("other", [
    "before_race_1.png", "before_race_1_scotland.png",
    "race_result_ru_1_won.png", "challenge_complete_ru.png",
])
def test_other_screens_no_panel(other):
    if not (FIXTURES / other).exists():
        pytest.skip("немає фікстури")
    img = cv2.imread(str(FIXTURES / other))
    assert detect_expanded_panel(img) is None
    assert make_extractor().extract(img) == []


def test_blank_image_returns_empty():
    img = np.zeros((1600, 2560, 3), dtype=np.uint8)
    assert detect_expanded_panel(img) is None
    assert make_extractor().extract(img) == []
