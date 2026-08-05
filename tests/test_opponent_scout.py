"""Екстрактор скаут-екранів суперника (спека §3, «екран 2» і «екран 3»).

Очікувані значення — з таблиці плану 2026-08-03-...-stage3-recognition.md
(звірені очима зі скріншотами й сідом треків)."""
from pathlib import Path
from types import SimpleNamespace

import cv2
import pytest

from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.map_icon_matcher import MapIconMatcher
from alu_gauntlet_helper.screen_recognition.screens.opponent_scout import (
    OpponentScoutExtractor, detect_scout_panels,
)
from tests.recognition_vocab import build_resolvers

FIXTURES = Path(__file__).parent / "fixtures"
ICONS = Path(__file__).parent.parent / "resources" / "icons" / "maps"

MAP_IDS = {p.stem: 100 + i for i, p in enumerate(sorted(ICONS.glob("*.png")))}

TRACK_RESOLVER, _, TRACK_VIEWS, _ = build_resolvers()


def tid(map_name, name):
    return next(v.id for v in TRACK_VIEWS if v.map_name == map_name and v.name == name)


def extractor():
    m = MapIconMatcher(SimpleNamespace(id=i, icon=str(ICONS / f"{name}.png"), name=name)
                       for name, i in MAP_IDS.items())
    return OpponentScoutExtractor(TRACK_RESOLVER, m)


def load(name):
    path = FIXTURES / f"{name}.png"
    if not path.exists():
        pytest.skip("немає фікстури")
    return cv2.imread(str(path))


def need_tesseract():
    if not (ocr.configure_tesseract() and ocr.is_available()):
        pytest.skip("немає tesseract")


def test_detect_scout_panels_on_fixtures():
    for name in ("opponent_tracks", "opponent_times_1", "opponent_times_2"):
        panels = detect_scout_panels(load(name))
        assert panels is not None and len(panels) == 5, name


def test_detect_rejects_accordion():
    assert detect_scout_panels(load("accordion_before_1")) is None
    assert detect_scout_panels(load("race_result_4_lost")) is None


def test_tracks_variant():
    """Екран 2: трек + карта на кожній панелі, часів немає."""
    need_tesseract()
    captures = extractor().extract(load("opponent_tracks"))
    assert [c.race_number for c in captures] == [1, 2, 3, 4, 5]
    expected = [("Greenland", "Out of the Center"),
                ("San Francisco", "Railroad Bustle"),
                ("The Caribbean", "Hell Vale"),
                ("Osaka", "Namba Park"),
                ("Scotland", "Rocky Valley")]
    for c, (map_name, track_name) in zip(captures, expected):
        assert c.track is not None and c.track.value == tid(map_name, track_name)
        assert c.map is not None and c.map.value == MAP_IDS[map_name]
        assert c.opponent_time is None
        assert c.car is None and c.time is None and c.rank is None
        assert c.game_language == "en"
        assert c.source_screen == "opponent_scout"
        assert c.panel_image


def test_times_variant_1():
    """Екран 3: карта + час суперника, назв треків немає."""
    need_tesseract()
    captures = extractor().extract(load("opponent_times_1"))
    assert [c.race_number for c in captures] == [1, 2, 3, 4, 5]
    expected = [("The Caribbean", 27100), ("Osaka", 24983), ("Himalayas", 22166),
                ("Rome", 21966), ("Auckland", 30499)]
    for c, (map_name, time_ms) in zip(captures, expected):
        assert c.map is not None and c.map.value == MAP_IDS[map_name]
        assert c.opponent_time == time_ms
        assert c.track is None
        assert c.car is None and c.time is None and c.rank is None


def test_times_variant_2():
    need_tesseract()
    captures = extractor().extract(load("opponent_times_2"))
    expected = [("New York", 25203), ("Himalayas", 21285), ("San Francisco", 22552),
                ("Greenland", 44489), ("Singapore", 24036)]
    for c, (map_name, time_ms) in zip(captures, expected):
        assert c.map is not None and c.map.value == MAP_IDS[map_name]
        assert c.opponent_time == time_ms


def test_alien_screen_returns_empty():
    need_tesseract()
    assert extractor().extract(load("accordion_before_1")) == []
    assert extractor().extract(load("before_race_1")) == []
