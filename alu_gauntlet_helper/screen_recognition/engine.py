import traceback

import numpy as np

from alu_gauntlet_helper.models import RecognitionResult
from alu_gauntlet_helper.screen_recognition.screens.base import ScreenExtractor


class RecognitionEngine:
    """Пробує екстрактори по черзі; перший, що повернув захоплення, перемагає."""

    def __init__(self, extractors: list[ScreenExtractor]):
        self.extractors = extractors

    def recognize(self, img: np.ndarray) -> RecognitionResult | None:
        for extractor in self.extractors:
            try:
                captures = extractor.extract(img)
            except Exception:
                print(f"Extractor {extractor.name} failed:")
                traceback.print_exc()
                continue
            if captures:
                language = next((c.game_language for c in captures if c.game_language), None)
                return RecognitionResult(screen=extractor.name, captures=captures,
                                         game_language=language)
        return None
