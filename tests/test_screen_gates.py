"""Дешеві піксельні гейти екранів (0 OCR).

Кожен екстрактор перед дорогим OCR-якорем перевіряє піксельну сигнатуру свого
екрана. Тести фіксують дві властивості на ВСІХ реальних фікстурах:
  1) гейт ПРОПУСКАЄ всі «свої» скріни (інакше екран перестане розпізнаватись);
  2) на «чужих» скрінах екстрактор відсіюється БЕЗ ЖОДНОГО OCR-виклику
     (ocr._run_ocr підмінено на фейл) — це і є прибраний «податок на відмову».

Tesseract цим тестам не потрібен — OCR тут не має запускатись взагалі.
"""
from pathlib import Path

import cv2
import numpy as np
import pytest

from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.regions import (
    BEFORE_RACE_MAX_WHITE_FRAC, BEFORE_RACE_MIN_WHITE_FRAC, BEFORE_RACE_SLOTS,
    BEFORE_RACE_WHITE_THRESHOLD,
)
from alu_gauntlet_helper.screen_recognition.screens.before_race import BeforeRaceExtractor
from alu_gauntlet_helper.screen_recognition.screens.challenge_accordion import (
    ChallengeAccordionExtractor,
)
from alu_gauntlet_helper.screen_recognition.screens.challenge_complete import (
    ChallengeCompleteExtractor, looks_like_challenge_complete,
)
from alu_gauntlet_helper.screen_recognition.screens.expanded_panel import (
    band_segments, detect_expanded_panel, has_accordion_columns,
)
from alu_gauntlet_helper.screen_recognition.screens.race_result import (
    RaceResultExtractor, looks_like_race_result,
)

FIXTURES = Path(__file__).parent / "fixtures"

# Фікстури за типом екрана (captures/ — реальні захоплення користувача).
RACE_RESULT = [
    "race_result_4_lost.png", "race_result_ru_1_won.png", "race_result_ru_2_won.png",
    "race_result_ru_3_won.png", "race_result_ru_3_won_lowres.png",
    "captures/capture_1784451941416937700.png", "captures/capture_1784538557283999600.png",
    "captures/capture_1784627025726575700.png", "captures/capture_1784794715365495300.png",
    "captures/capture_1784799351890838400.png", "captures/capture_1784881514278377300.png",
    "captures/capture_1784882769017084400.png", "captures/capture_1785488451435103800.png",
]
COMPLETE = ["challenge_complete_won.png", "challenge_complete_ru.png"]
BEFORE_RACE = [
    "before_race_1.png", "before_race_1_scotland.png", "before_race_1_tuscany.png",
    "before_race_2_rome.png", "before_race_3_nevada.png", "before_race_4.png",
    "captures/capture_1784795086089408800.png", "captures/capture_1785420973341703600.png",
]
ACCORDION = [
    "accordion_after_1.png", "accordion_after_2.png", "accordion_after_4.png",
    "accordion_after_shanghai_paris_east.png",
    "accordion_before_1.png", "accordion_before_3.png", "accordion_before_5.png",
    "accordion_race1.png",
    "accordion_ru_1_nevada.png", "accordion_ru_2_osaka.png", "accordion_ru_3_new_york.png",
    "accordion_ru_4_singapore.png", "accordion_ru_5_scotland.png",
    "car_selection_ru_1_sf.png", "car_selection_ru_2_auckland.png",
    "captures/capture_1784280093934504300.png", "captures/capture_1784280351685522500.png",
    "captures/capture_1784538421080048100.png", "captures/capture_1784626481643508500.png",
    "captures/capture_1784626682823724600.png", "captures/capture_1784626829149215100.png",
    "captures/capture_1784704425381040700.png", "captures/capture_1784794600198030500.png",
    "captures/capture_1784882730503432100.png", "captures/capture_1785587843254562800.png",
]


def load(fixture: str) -> np.ndarray:
    path = FIXTURES / fixture
    if not path.exists():
        pytest.skip("немає фікстури")
    return cv2.imread(str(path))


@pytest.fixture
def no_ocr(monkeypatch):
    """Будь-який OCR-виклик — провал тесту: гейт мусив відсікти екран раніше."""
    def _fail(*args, **kwargs):
        raise AssertionError("OCR не мав викликатись — екран мав відсіктись піксельним гейтом")
    monkeypatch.setattr(ocr, "_run_ocr", _fail)


# --- race_result -------------------------------------------------------------

@pytest.mark.parametrize("fixture", RACE_RESULT)
def test_race_result_gate_passes_own(fixture):
    assert looks_like_race_result(load(fixture))


# before_race тут навмисно немає: його сцена буває темною у регіоні часу,
# тож гейт race_result відсікає її не завжди (це свідомо консервативно).
@pytest.mark.parametrize("fixture", ACCORDION + COMPLETE)
def test_race_result_rejects_foreign_without_ocr(fixture, no_ocr):
    assert RaceResultExtractor(car_matcher=None).extract(load(fixture)) == []


# --- challenge_complete ------------------------------------------------------

@pytest.mark.parametrize("fixture", COMPLETE)
def test_complete_gate_passes_own(fixture):
    assert looks_like_challenge_complete(load(fixture))


@pytest.mark.parametrize("fixture", ACCORDION + BEFORE_RACE)
def test_complete_rejects_foreign_without_ocr(fixture, no_ocr):
    assert ChallengeCompleteExtractor(car_matcher=None).extract(load(fixture)) == []


# --- before_race -------------------------------------------------------------

@pytest.mark.parametrize("fixture", BEFORE_RACE)
def test_before_race_digit_slot_survives_white_cap(fixture):
    """Рівно один слот-кандидат (поточна цифра, 0.038–0.058 білого) — у межах
    [MIN, MAX]; кеп MAX не зрізає справжню цифру."""
    img = load(fixture)
    fracs = [float((slot.crop(img).min(axis=2) > BEFORE_RACE_WHITE_THRESHOLD).mean())
             for slot in BEFORE_RACE_SLOTS]
    candidates = [f for f in fracs
                  if BEFORE_RACE_MIN_WHITE_FRAC <= f <= BEFORE_RACE_MAX_WHITE_FRAC]
    assert len(candidates) == 1


@pytest.mark.parametrize("fixture", ACCORDION + COMPLETE + RACE_RESULT)
def test_before_race_rejects_foreign_without_ocr(fixture, no_ocr):
    """На чужих екранах усі 5 слотів залиті білим (~0.4) — жодної OCR-проби."""
    assert BeforeRaceExtractor(track_resolver=None, car_matcher=None).extract(load(fixture)) == []


# --- challenge_accordion -----------------------------------------------------

# Геометрія (з яскравісним критерієм проміжку) покриває ВСІ варіанти акордеона,
# включно з EN before-варіантом, що раніше падав у OCR-пошук (~45 викликів).
ACCORDION_RACE = {
    "accordion_after_1.png": 1, "accordion_after_2.png": 2, "accordion_after_4.png": 4,
    "accordion_after_shanghai_paris_east.png": 1,
    "accordion_before_1.png": 1, "accordion_before_3.png": 3, "accordion_before_5.png": 5,
    "accordion_race1.png": 1,
    "accordion_ru_1_nevada.png": 1, "accordion_ru_2_osaka.png": 2,
    "accordion_ru_3_new_york.png": 3, "accordion_ru_4_singapore.png": 4,
    "accordion_ru_5_scotland.png": 5,
    "car_selection_ru_1_sf.png": 1, "car_selection_ru_2_auckland.png": 2,
    "captures/capture_1784280093934504300.png": 3, "captures/capture_1784280351685522500.png": 3,
    "captures/capture_1784538421080048100.png": 2, "captures/capture_1784626481643508500.png": 3,
    "captures/capture_1784626682823724600.png": 3, "captures/capture_1784626829149215100.png": 2,
    "captures/capture_1784704425381040700.png": 2, "captures/capture_1784794600198030500.png": 4,
    "captures/capture_1784882730503432100.png": 3, "captures/capture_1785587843254562800.png": 2,
}


@pytest.mark.parametrize("fixture, race", sorted(ACCORDION_RACE.items()))
def test_accordion_geometry_covers_all_variants(fixture, race):
    detected = detect_expanded_panel(load(fixture))
    assert detected is not None
    assert detected[2] == race


@pytest.mark.parametrize("fixture", ACCORDION)
def test_accordion_columns_gate_passes_own(fixture):
    """Гейт запасного OCR-пошуку: на своїх скрінах завжди 4 вузькі колонки."""
    assert has_accordion_columns(band_segments(load(fixture)))


@pytest.mark.parametrize("fixture", RACE_RESULT + COMPLETE + BEFORE_RACE)
def test_accordion_rejects_foreign_without_ocr(fixture, no_ocr):
    """Геометрія не складається, гейт колонок теж → без OCR-пошуку."""
    extractor = ChallengeAccordionExtractor(track_resolver=None, car_matcher=None)
    assert extractor.extract(load(fixture)) == []
