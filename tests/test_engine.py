import numpy as np

from alu_gauntlet_helper.models import RaceCapture
from alu_gauntlet_helper.screen_recognition.engine import RecognitionEngine
from alu_gauntlet_helper.screen_recognition.screens.base import ScreenExtractor

IMG = np.zeros((100, 100, 3), dtype=np.uint8)


class FakeExtractor(ScreenExtractor):
    def __init__(self, name, captures, error=False):
        self.name = name
        self._captures = captures
        self._error = error

    def extract(self, img):
        if self._error:
            raise RuntimeError("boom")
        return self._captures


def test_first_extractor_with_captures_wins():
    engine = RecognitionEngine([
        FakeExtractor("empty", []),
        FakeExtractor("accordion", [RaceCapture(race_number=2)]),
    ])
    result = engine.recognize(IMG)
    assert result.screen == "accordion"
    assert result.captures[0].race_number == 2


def test_no_match_returns_none():
    engine = RecognitionEngine([FakeExtractor("empty", [])])
    assert engine.recognize(IMG) is None


def test_extractor_exception_does_not_break_engine():
    engine = RecognitionEngine([
        FakeExtractor("broken", [], error=True),
        FakeExtractor("ok", [RaceCapture(race_number=1)]),
    ])
    assert engine.recognize(IMG).screen == "ok"
