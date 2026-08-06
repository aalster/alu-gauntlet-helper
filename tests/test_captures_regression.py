"""Регресія на реальних captures, які колись НЕ розпізнавались
(діагностика: docs/recognition-survey.md, scripts/probe_failures.py):

- EN race_result: квадратний логотип клубу зліва зливається з бейджем "RACE N"
  (OCR читає 'CACE3'/''/'RRACE') — якір не матчився. Фікс: обрізані EN-варіанти
  кропу заголовка (аналог RU-шляху).
- before_race: курсивна "4" на деяких рендерах читається лише при shear=0.0,
  якого не було в DIGIT_SHEARS.
- challenge_accordion (CAR SELECTION): купка captures серпня-2026 зберігалась
  як «невпевнені» — RU-карта "РИМ" (префікс назв треків "РИМСКИЕ ...")
  калічилась у _strip_map, плашка рангу залазила в кроп назви авто сміттєвим
  останнім рядком, а без вибраного авто гравця геометрія панелі не складалась.

Словник — повний (recognition_vocab), як у застосунку: перевіряємо і збіг авто.
"""
from pathlib import Path

import cv2
import pytest

from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.screens.before_race import BeforeRaceExtractor
from alu_gauntlet_helper.screen_recognition.screens.challenge_accordion import (
    ChallengeAccordionExtractor,
)
from alu_gauntlet_helper.screen_recognition.screens.race_result import RaceResultExtractor
from alu_gauntlet_helper.services.challenge_session import LOW_CONFIDENCE
from tests.recognition_vocab import build_resolvers, car_label, track_label

CAPTURES = Path(__file__).parent / "fixtures" / "captures"
TESSERACT_OK = ocr.configure_tesseract() and ocr.is_available()

_track_resolver, _car_matcher, _tv, _cv = build_resolvers()


def capture_guard(fixture: str):
    return pytest.mark.skipif(not (CAPTURES / fixture).exists(), reason="немає фікстури")


# (файл, race, назва авто гравця, time мс, rank, мова)
RACE_RESULT_CAPTURES = [
    ("capture_1784451941416937700.png", 3, "Rimac Nevera Time Attack", 23199, 4835, "en"),
    ("capture_1784538557283999600.png", 3, "Koenigsegg CCXR", 25132, 4998, "en"),
    ("capture_1784627025726575700.png", 1, "Bugatti Chiron", 20155, 5130, "en"),
    ("capture_1784794715365495300.png", 3, "W Motors Lykan Hypersport", 23319, 4683, "en"),
    ("capture_1784799351890838400.png", 5, "Ferrari SF90 Stradale", 26265, 4795, "en"),  # LOST: час червоний
    ("capture_1784881514278377300.png", 3, "Rimac Nevera Time Attack", 25941, 4835, "en"),
    ("capture_1784882769017084400.png", 1, "Rimac Nevera Time Attack", 20366, 4835, "en"),
    ("capture_1785488451435103800.png", 1, "Peugeot 9x8", 21467, 3948, "en"),
    # RU: широкий логотип клубу — слово "ГОНКА" читається лише при trim=0.22,
    # якого не було в гейті _ru_word_present
    ("capture_1786001971636410500.png", 5, "Koenigsegg CCXR", 24933, 4998, "ru"),
]


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@pytest.mark.parametrize("fixture, race, car_name, time, rank, lang", RACE_RESULT_CAPTURES)
def test_race_result_with_club_logo(fixture, race, car_name, time, rank, lang):
    """Бейдж "RACE N WON/LOST!" / "ГОНКА N ПОБЕДА!" з логотипом клубу впритул зліва."""
    path = CAPTURES / fixture
    if not path.exists():
        pytest.skip("немає фікстури")
    captures = RaceResultExtractor(_car_matcher).extract(cv2.imread(str(path)))
    assert len(captures) == 1
    c = captures[0]
    assert c.race_number == race
    assert c.game_language == lang
    assert c.car and car_label(_cv, c.car.value) == car_name
    assert c.time == time
    assert c.rank == rank


# (файл, race, track "Карта - Трек", авто гравця | None, rank | None,
#  авто суперника, opp_time мс, мова)
ACCORDION_CAPTURES = [
    # плашка рангу в кропі авто: "PEUGEOT\n98\nTSVWH" — без фіксу score 0.75
    ("capture_1785744680741669000.png", 2, "Shanghai - Double Roundabout",
     "Peugeot 9x8", 3948, "Chevrolet Camaro LT", 40650, "en"),
    # авто гравця не вибране → коло "+" рве панель, геометрія не складалась
    ("capture_1785836854551943800.png", 1, "Osaka - Meiji Rush",
     None, None, "Lamborghini Huracan Evo Spyder", 27333, "en"),
    ("capture_1785837931447249300.png", 4, "Greenland - Out of the Center",
     None, None, "Koenigsegg Agera RS", 42553, "en"),
    # RU: карта "РИМ" — префікс "РИМСКИЕ ..."; без фіксу _strip_map калічив фрагмент
    ("capture_1786001288381845200.png", 1, "Rome - Roman Byroads",
     None, None, "Bugatti Chiron", 22438, "ru"),
    ("capture_1786001356361191800.png", 1, "Rome - Roman Byroads",
     "Bugatti Chiron", 5130, "Bugatti Chiron", 22438, "ru"),
]


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@pytest.mark.parametrize("fixture, race, track, car_name, rank, opp_car, opp_time, lang",
                         ACCORDION_CAPTURES)
def test_accordion_car_selection(fixture, race, track, car_name, rank, opp_car, opp_time, lang):
    """CAR SELECTION / ВЫБОР АВТО: серпневі captures, збережені як «невпевнені»."""
    path = CAPTURES / fixture
    if not path.exists():
        pytest.skip("немає фікстури")
    captures = ChallengeAccordionExtractor(_track_resolver, _car_matcher).extract(
        cv2.imread(str(path)))
    assert len(captures) == 1
    c = captures[0]
    assert c.race_number == race
    assert c.game_language == lang
    assert c.track and " - ".join(track_label(_tv, c.track.value)) == track
    if car_name is None:
        assert c.car is None
    else:
        assert c.car and car_label(_cv, c.car.value) == car_name
        assert c.car.score >= LOW_CONFIDENCE
    assert c.rank == rank
    assert c.opponent_car and car_label(_cv, c.opponent_car.value) == opp_car
    assert c.opponent_time == opp_time


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@capture_guard("capture_1786001288381845200.png")
def test_ru_map_prefix_track_confident():
    """"РИМ / РИМСКИЕ ТРО": видимий фрагмент однозначно вказує на Тропы —
    після фіксу _strip_map скор має бути впевненим (вище порога ворнінга)."""
    captures = ChallengeAccordionExtractor(_track_resolver, _car_matcher).extract(
        cv2.imread(str(CAPTURES / "capture_1786001288381845200.png")))
    assert len(captures) == 1
    assert captures[0].track.score >= LOW_CONFIDENCE


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
