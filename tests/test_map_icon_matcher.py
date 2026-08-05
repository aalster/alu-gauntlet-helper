"""Матчинг іконок карт (екрани скаутингу суперника). Чистий OpenCV, без OCR.

Очікувані карти панелей звірені очима з resources/icons/maps і зафіксовані
прототипом (див. план 2026-08-03-opponent-assistant-stage3-recognition.md)."""
from pathlib import Path
from types import SimpleNamespace

import cv2
import pytest

from alu_gauntlet_helper.screen_recognition.map_icon_matcher import MapIconMatcher
from alu_gauntlet_helper.screen_recognition.screens.expanded_panel import band_segments

FIXTURES = Path(__file__).parent / "fixtures"
ICONS = Path(__file__).parent.parent / "resources" / "icons" / "maps"

# Абсолютна зона іконки карти в панелі (частки кадру) — як у прототипі.
ICON_Y = (0.29, 0.42)

MAP_IDS = {p.stem: i for i, p in enumerate(sorted(ICONS.glob("*.png")))}


def matcher():
    return MapIconMatcher(SimpleNamespace(id=i, icon=str(ICONS / f"{name}.png"))
                          for name, i in MAP_IDS.items())


def panel_icon(img, index):
    h, w = img.shape[:2]
    left, right = band_segments(img)[index]
    return img[int(ICON_Y[0] * h):int(ICON_Y[1] * h), int(left * w):int(right * w)]


EXPECTED = {
    "opponent_tracks": ["Greenland", "San Francisco", "The Caribbean", "Osaka", "Scotland"],
    "opponent_times_1": ["The Caribbean", "Osaka", "Himalayas", "Rome", "Auckland"],
    "opponent_times_2": ["New York", "Himalayas", "San Francisco", "Greenland", "Singapore"],
}


@pytest.mark.parametrize("fixture", sorted(EXPECTED))
def test_matches_all_panels(fixture):
    path = FIXTURES / f"{fixture}.png"
    if not path.exists():
        pytest.skip("немає фікстури")
    img = cv2.imread(str(path))
    m = matcher()
    for i, expected in enumerate(EXPECTED[fixture]):
        guess = m.match(panel_icon(img, i))
        assert guess is not None, f"панель {i + 1}: іконку не розпізнано"
        assert guess.value == MAP_IDS[expected], f"панель {i + 1}"
        assert guess.score >= 0.5
        assert len(guess.candidates) <= 3


def test_no_match_on_blank_roi():
    import numpy as np
    m = matcher()
    assert m.match(np.zeros((160, 340, 3), dtype=np.uint8)) is None


def test_tiny_roi_returns_none():
    import numpy as np
    m = matcher()
    assert m.match(np.zeros((10, 10, 3), dtype=np.uint8)) is None


def test_ambiguous_match_caps_score():
    # два еталони — точні копії одного й того самого зображення (справжня
    # іконка панелі) під різними id: марджин між кандидатом 1 і 2 гарантовано
    # 0 → скор капиться <= 0.6, хоча без дубля панель матчиться на 0.6163
    icon = str(ICONS / "Greenland.png")
    m = MapIconMatcher([SimpleNamespace(id=1, icon=icon), SimpleNamespace(id=2, icon=icon)])
    img = cv2.imread(str(FIXTURES / "opponent_tracks.png"))
    roi = panel_icon(img, 0)  # panel 1 = Greenland
    guess = m.match(roi)
    assert guess is not None
    assert guess.score <= 0.6
