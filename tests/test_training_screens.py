"""Екрани тренування (приватне лобі): лобі та результати заїзду.

Фікстури 2560×1600:
  training_lobby_osaka.png      — EN-лобі: OSAKA / MEIJI RUSH, ROOM ID 44fqfu
  training_lobby_ru_osaka.png   — RU-лобі: ОСАКА / НАТИСК МЭЙДЗИ
  training_result_battista.png  — EN-результат: YOUR TIME 00:26.499,
                                  AUTOMOBILI PININFARINA BATTISTA
  training_result_ru_chiron.png — RU-результат: ТВОЕ ВРЕМЯ 00:25.533,
                                  BUGATTI CHIRON
Екран RACE REWARDS (без назви авто текстом) свідомо НЕ підтримується."""
from pathlib import Path

import cv2
import numpy as np
import pytest

from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.screens.training_lobby import TrainingLobbyExtractor
from alu_gauntlet_helper.screen_recognition.screens.training_result import TrainingResultExtractor
from tests.recognition_vocab import build_resolvers, car_label, track_label

FIXTURES = Path(__file__).parent / "fixtures"
TESSERACT_OK = ocr.configure_tesseract() and ocr.is_available()

TRACK_RESOLVER, CAR_MATCHER, TRACK_VIEWS, CAR_VIEWS = build_resolvers()


def lobby_extractor():
    return TrainingLobbyExtractor(TRACK_RESOLVER)


def result_extractor():
    return TrainingResultExtractor(CAR_MATCHER)


def load(fixture: str):
    path = FIXTURES / fixture
    if not path.exists():
        pytest.skip("немає фікстури")
    return cv2.imread(str(path))


# --- лобі --------------------------------------------------------------------

@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@pytest.mark.parametrize("fixture, language", [
    ("training_lobby_osaka.png", "en"),
    ("training_lobby_ru_osaka.png", "ru"),
])
def test_lobby_extracts_track(fixture, language):
    captures = lobby_extractor().extract(load(fixture))
    assert len(captures) == 1
    c = captures[0]
    assert c.race_number == 0  # номер заїзду призначає сесія, не екстрактор
    assert c.time is None
    assert c.track is not None
    assert track_label(TRACK_VIEWS, c.track.value) == ("Osaka", "Meiji Rush")
    assert c.game_language == language
    assert c.source_screen == "training_lobby"
    assert c.panel_image


# --- результат заїзду --------------------------------------------------------

@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@pytest.mark.parametrize("fixture, time, car_name, language", [
    ("training_result_battista.png", 26499, "Automobili Pininfarina Battista", "en"),
    ("training_result_ru_chiron.png", 25533, "Bugatti Chiron", "ru"),
])
def test_result_extracts_time_and_car(fixture, time, car_name, language):
    captures = result_extractor().extract(load(fixture))
    assert len(captures) == 1
    c = captures[0]
    assert c.race_number == 0
    assert c.time == time
    assert c.track is None
    assert c.rank is None  # рангів у тренуванні немає
    assert c.car is not None
    assert car_label(CAR_VIEWS, c.car.value) == car_name
    assert c.game_language == language
    assert c.source_screen == "training_result"
    assert c.panel_image


# --- гейти: чужі екрани не спрацьовують --------------------------------------

OTHER_SCREENS = [
    "race_result_4_lost.png", "accordion_before_1.png", "challenge_complete_won.png",
    "before_race_1.png", "opponent_tracks.png",
]


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@pytest.mark.parametrize("fixture", OTHER_SCREENS + ["training_result_battista.png"])
def test_other_screens_do_not_trigger_lobby(fixture):
    assert lobby_extractor().extract(load(fixture)) == []


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@pytest.mark.parametrize("fixture", OTHER_SCREENS + ["training_lobby_osaka.png"])
def test_other_screens_do_not_trigger_result(fixture):
    assert result_extractor().extract(load(fixture)) == []


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
def test_black_image_returns_empty():
    img = np.zeros((1600, 2560, 3), dtype=np.uint8)
    assert lobby_extractor().extract(img) == []
    assert result_extractor().extract(img) == []


# --- інтеграція: повний потік engine → SessionManager -------------------------

@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
def test_full_training_flow_through_session_manager():
    """Лобі → сесія тренування з треком; два результати → два заїзди;
    рескан лобі того самого треку (іншою мовою) — мерж, а не нова сесія."""
    from alu_gauntlet_helper.screen_recognition.engine import RecognitionEngine
    from alu_gauntlet_helper.services.session_manager import SessionManager
    from alu_gauntlet_helper.services.training_session import TrainingSessionService

    engine = RecognitionEngine([result_extractor(), lobby_extractor()])
    manager = SessionManager()
    for fixture in ["training_lobby_osaka.png", "training_result_battista.png",
                    "training_result_ru_chiron.png", "training_lobby_ru_osaka.png"]:
        recognized = engine.recognize(load(fixture))
        assert recognized is not None, fixture
        manager.apply(recognized)

    assert len(manager.sessions) == 1
    session = manager.active
    assert isinstance(session, TrainingSessionService)
    assert track_label(TRACK_VIEWS, session.track.value) == ("Osaka", "Meiji Rush")
    assert session.run_numbers() == [1, 2]
    assert session.effective(1).time == 26499
    assert car_label(CAR_VIEWS, session.effective(2).car_id) == "Bugatti Chiron"
    # трек сесії просвічує в кожен заїзд
    assert session.effective(1).track_id == session.track.value
