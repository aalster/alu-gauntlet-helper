"""Регресія на реальних captures, які колись НЕ розпізнавались
(діагностика: docs/recognition-survey.md, scripts/probe_failures.py):

- EN race_result: квадратний логотип клубу зліва зливається з бейджем "RACE N"
  (OCR читає 'CACE3'/''/'RRACE') — якір не матчився. Фікс: обрізані EN-варіанти
  кропу заголовка (аналог RU-шляху).
- before_race: курсивна "4" на деяких рендерах читається лише при shear=0.0,
  якого не було в DIGIT_SHEARS.

Словник — повний (recognition_vocab), як у застосунку: перевіряємо і збіг авто.
"""
from pathlib import Path

import cv2
import pytest

from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.screens.before_race import BeforeRaceExtractor
from alu_gauntlet_helper.screen_recognition.screens.race_result import RaceResultExtractor
from tests.recognition_vocab import build_resolvers, car_label, track_label

CAPTURES = Path(__file__).parent / "fixtures" / "captures"
TESSERACT_OK = ocr.configure_tesseract() and ocr.is_available()

_track_resolver, _car_matcher, _tv, _cv = build_resolvers()


def capture_guard(fixture: str):
    return pytest.mark.skipif(not (CAPTURES / fixture).exists(), reason="немає фікстури")


# (файл, race, назва авто гравця, time мс, rank)
RACE_RESULT_CAPTURES = [
    ("capture_1784451941416937700.png", 3, "Rimac Nevera Time Attack", 23199, 4835),
    ("capture_1784538557283999600.png", 3, "Koenigsegg CCXR", 25132, 4998),
    ("capture_1784627025726575700.png", 1, "Bugatti Chiron", 20155, 5130),
    ("capture_1784794715365495300.png", 3, "W Motors Lykan Hypersport", 23319, 4683),
    ("capture_1784799351890838400.png", 5, "Ferrari SF90 Stradale", 26265, 4795),  # LOST: час червоний
    ("capture_1784881514278377300.png", 3, "Rimac Nevera Time Attack", 25941, 4835),
    ("capture_1784882769017084400.png", 1, "Rimac Nevera Time Attack", 20366, 4835),
    ("capture_1785488451435103800.png", 1, "Peugeot 9x8", 21467, 3948),
]


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@pytest.mark.parametrize("fixture, race, car_name, time, rank", RACE_RESULT_CAPTURES)
def test_race_result_with_club_logo(fixture, race, car_name, time, rank):
    """Бейдж "RACE N WON/LOST!" з логотипом клубу впритул зліва."""
    path = CAPTURES / fixture
    if not path.exists():
        pytest.skip("немає фікстури")
    captures = RaceResultExtractor(_car_matcher).extract(cv2.imread(str(path)))
    assert len(captures) == 1
    c = captures[0]
    assert c.race_number == race
    assert c.game_language == "en"
    assert c.car and car_label(_cv, c.car.value) == car_name
    assert c.time == time
    assert c.rank == rank


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@capture_guard("capture_1785420973341703600.png")
def test_before_race_digit_4_needs_zero_shear():
    """Singapore Waterslide Whirl, гонка 4: слот-кандидат знаходиться, але
    курсивна "4" читається лише без deshear-зсуву (shear=0.0)."""
    img = cv2.imread(str(CAPTURES / "capture_1785420973341703600.png"))
    captures = BeforeRaceExtractor(_track_resolver, _car_matcher).extract(img)
    assert len(captures) == 1
    c = captures[0]
    assert c.race_number == 4
    assert c.track and track_label(_tv, c.track.value) == ("Singapore", "Waterslide Whirl")
    assert c.car and car_label(_cv, c.car.value) == "Ferrari SF90 Stradale"
    assert c.rank == 4795
