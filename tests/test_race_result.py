from pathlib import Path

import cv2
import pytest

from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.matching import VocabularyMatcher
from alu_gauntlet_helper.screen_recognition.screens.race_result import RaceResultExtractor

FIXTURES = Path(__file__).parent / "fixtures"
TESSERACT_OK = ocr.configure_tesseract() and ocr.is_available()

# У словнику НАВМИСНО є суперник з лівого боку (W Motors Lykan): читання
# не того боку дало б хибний id і завалило тест.
CAR_BUGATTI_CHIRON = 202
CAR_LYKAN_HYPERSPORT = 205
CAR_VANDA_DENDROBIUM = 207
CAR_KOENIGSEGG_CCXR = 204
CAR_VOCAB = [
    (CAR_BUGATTI_CHIRON, "Bugatti Chiron"),
    (CAR_LYKAN_HYPERSPORT, "W Motors Lykan Hypersport"),
    (CAR_VANDA_DENDROBIUM, "Vanda Electrics Dendrobium"),
    (CAR_KOENIGSEGG_CCXR, "Koenigsegg CCXR"),
]


def make_extractor():
    return RaceResultExtractor(VocabularyMatcher(CAR_VOCAB))


def fixture_guard(fixture: str):
    return pytest.mark.skipif(not (FIXTURES / fixture).exists(), reason="немає фікстури")


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@fixture_guard("race_result_4_lost.png")
def test_race_result_player_data():
    """Скріншот: зверху "RACE 4 LOST!", зліва суперник W MOTORS LYKAN HYPERSPORT
    4,683 (TIME TO BEAT 00:24.164), справа гравець BUGATTI CHIRON 5,130
    (YOUR TIME 00:24.182 червоним). У центрі знизу — нік суперника Milln і його
    клуб Strassenband: це НЕ трек, назви треку на цьому екрані немає."""
    img = cv2.imread(str(FIXTURES / "race_result_4_lost.png"))
    captures = make_extractor().extract(img)
    assert len(captures) == 1
    c = captures[0]
    assert c.race_number == 4  # із заголовка "RACE 4 LOST!", не "5" з індикатора прогресу
    assert c.track is None
    # Має бути авто ГРАВЦЯ (правий бік), а не суперника (лівий бік)
    assert c.car and c.car.value == CAR_BUGATTI_CHIRON
    assert c.car.value != CAR_LYKAN_HYPERSPORT
    assert c.rank == 5130  # ранг гравця, не 4683 суперника
    assert c.time == 24182  # YOUR TIME, не 24164 (TIME TO BEAT)
    assert c.panel_image


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@pytest.mark.parametrize("fixture", [
    "accordion_before_1.png", "accordion_after_4.png", "accordion_race1.png",
    "challenge_complete_won.png"])
def test_other_screens_do_not_trigger(fixture):
    """Екрани акордеона і підсумку челенджа не мають хибно розпізнаватись як
    результат гонки: у регіоні заголовка race_result там читається сміття
    без "RACE N" (на підсумку — "CHALLENGE WON" без номера)."""
    if not (FIXTURES / fixture).exists():
        pytest.skip("немає фікстури")
    img = cv2.imread(str(FIXTURES / fixture))
    assert make_extractor().extract(img) == []


# --- RU: екран результату гонки "ГОНКА N ПОБЕДА!" російською ------------------
# Заголовок кирилицею; авто гравця лишається англ. Перевіряє двомовний якір
# (курсивна "1" у шрифті гри читається як "7" → мапиться назад) і авто-визначення
# мови гри. Треку на цьому екрані немає (як і в англ. варіанті).

@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@pytest.mark.parametrize("fixture, race, car_id, time, rank", [
    ("race_result_ru_1_won.png", 1, CAR_BUGATTI_CHIRON, 23229, 5130),
    ("race_result_ru_2_won.png", 2, CAR_VANDA_DENDROBIUM, 21965, 4099),
    ("race_result_ru_3_won.png", 3, CAR_KOENIGSEGG_CCXR, 22749, 4998),
])
def test_ru_race_result(fixture, race, car_id, time, rank):
    if not (FIXTURES / fixture).exists():
        pytest.skip("немає фікстури")
    img = cv2.imread(str(FIXTURES / fixture))
    captures = make_extractor().extract(img)
    assert len(captures) == 1
    c = captures[0]
    assert c.race_number == race  # із заголовка "ГОНКА N ПОБЕДА!"
    assert c.track is None
    assert c.car and c.car.value == car_id  # авто гравця, англ.
    assert c.time == time
    assert c.rank == rank
    assert c.game_language == "ru"


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@fixture_guard("race_result_ru_3_won_lowres.png")
def test_ru_race_result_lowres_digit_glued_to_word():
    """Низькоякісний скрін (1921x1080): курсивна "3" зливається зі словом і
    читається як кирилична "З" ("ГОНКАЗ"), а праворуч декор читається як "11".
    Номер гонки має лишитись 3, а не схопити шумову "1"."""
    img = cv2.imread(str(FIXTURES / "race_result_ru_3_won_lowres.png"))
    captures = make_extractor().extract(img)
    assert len(captures) == 1
    assert captures[0].race_number == 3
    assert captures[0].game_language == "ru"


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
def test_non_race_result_image_returns_empty():
    import numpy as np
    img = np.zeros((1600, 2560, 3), dtype=np.uint8)
    assert make_extractor().extract(img) == []
