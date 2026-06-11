from pathlib import Path

import cv2
import pytest

from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.matching import VocabularyMatcher
from alu_gauntlet_helper.screen_recognition.screens.challenge_complete import ChallengeCompleteExtractor

FIXTURES = Path(__file__).parent / "fixtures"
TESSERACT_OK = ocr.configure_tesseract() and ocr.is_available()

# У словнику є й суперники з лівого боку (Lykan у рядку 4, Chiron у рядку 1):
# читання не того боку дало б хибний id і завалило тест.
CAR_BUGATTI_CHIRON = 202
CAR_LYKAN_HYPERSPORT = 205
CAR_FERRARI_SF90 = 210
CAR_KOENIGSEGG_CCXR = 211
CAR_RIMAC_NEVERA = 212
CAR_ULTIMA_RS = 213
CAR_VOCAB = [
    (CAR_BUGATTI_CHIRON, "Bugatti Chiron"),
    (CAR_LYKAN_HYPERSPORT, "W Motors Lykan Hypersport"),
    (CAR_FERRARI_SF90, "Ferrari SF90 Stradale"),
    (CAR_KOENIGSEGG_CCXR, "Koenigsegg CCXR"),
    (CAR_RIMAC_NEVERA, "Rimac Nevera Time Attack"),
    (CAR_ULTIMA_RS, "Ultima RS"),
]


def make_extractor():
    return ChallengeCompleteExtractor(VocabularyMatcher(CAR_VOCAB))


def fixture_guard(fixture: str):
    return pytest.mark.skipif(not (FIXTURES / fixture).exists(), reason="немає фікстури")


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@fixture_guard("challenge_complete_won.png")
def test_challenge_complete_all_five_races():
    """Скріншот: "CHALLENGE WON", 5 рядків. У кожному зліва час і авто
    СУПЕРНИКА, справа час (жовтий/червоний) і авто ГРАВЦЯ. Треку і рангу
    на екрані немає."""
    img = cv2.imread(str(FIXTURES / "challenge_complete_won.png"))
    captures = make_extractor().extract(img)
    assert [c.race_number for c in captures] == [1, 2, 3, 4, 5]

    # Авто ГРАВЦЯ (правий бік), а не суперника (лівий бік)
    expected_cars = [CAR_FERRARI_SF90, CAR_KOENIGSEGG_CCXR, CAR_RIMAC_NEVERA,
                     CAR_BUGATTI_CHIRON, CAR_ULTIMA_RS]
    assert [c.car and c.car.value for c in captures] == expected_cars

    # Час ГРАВЦЯ (правий), а не "TIME TO BEAT" суперника (лівий).
    # Рядок 4: 24182, не 24164; рядок 1: 19130, не 19152.
    expected_times = [19130, 25782, 19416, 24182, 31298]
    assert [c.time for c in captures] == expected_times

    for c in captures:
        assert c.track is None
        assert c.rank is None
        assert c.panel_image


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@pytest.mark.parametrize("fixture", [
    "accordion_before_1.png", "accordion_after_4.png", "accordion_race1.png",
    "race_result_4_lost.png"])
def test_other_screens_do_not_trigger(fixture):
    """Акордеон і результат однієї гонки не мають хибно розпізнаватись як
    підсумковий екран: у регіоні бейджа першого рядка там немає "RACE 1"."""
    if not (FIXTURES / fixture).exists():
        pytest.skip("немає фікстури")
    img = cv2.imread(str(FIXTURES / fixture))
    assert make_extractor().extract(img) == []


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
def test_non_challenge_complete_image_returns_empty():
    import numpy as np
    img = np.zeros((1600, 2560, 3), dtype=np.uint8)
    assert make_extractor().extract(img) == []
