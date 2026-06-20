"""ЕКСПЕРИМЕНТАЛЬНИЙ швидкий ChallengeCompleteExtractor.

Той самий підсумковий екран (5 рядків), але:
  B2/B3/B4 — заголовок-якір 1-го рядка читаємо через read_race_header_fast.
  B5 — заголовки рядків 2..5 БІЛЬШЕ НЕ ПЕРЕЧИТУЄМО: рядки рівновіддалені, тож
       номер i-го = i+1 геометрично. Порожній рядок (немає ні часу, ні авто)
       однаково відсівається перевіркою нижче, тож валідація номера зайва.

Наявний екстрактор не змінює — для замірів (scripts/bench_recognition.py).
"""
import numpy as np

from alu_gauntlet_helper.models import RaceCapture
from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.matching import VocabularyMatcher
from alu_gauntlet_helper.screen_recognition.regions import (
    COMPLETE_PLAYER_CAR, COMPLETE_PLAYER_TIME, COMPLETE_RACE_BADGE, COMPLETE_ROWS,
)
from alu_gauntlet_helper.screen_recognition.screens.base import (
    HEADER_DY_OFFSETS, ScreenExtractor, encode_png,
)
from alu_gauntlet_helper.screen_recognition.screens.base_fast import read_race_header_fast


class ChallengeCompleteFastExtractor(ScreenExtractor):
    name = "challenge_complete_fast"

    def __init__(self, car_matcher: VocabularyMatcher):
        self.car_matcher = car_matcher

    def _anchor(self, img: np.ndarray) -> tuple[float, str | None]:
        """dy-зсув і мова з якоря 1-го рядка ("RACE 1"/"ГОНКА 1"). dy=NaN — не наш екран."""
        for dy in HEADER_DY_OFFSETS:
            number, language = read_race_header_fast(
                img, COMPLETE_ROWS[0].shifted(0.0, dy).sub(COMPLETE_RACE_BADGE))
            if number == 1:
                return dy, language
        return float("nan"), None

    def extract(self, img: np.ndarray) -> list[RaceCapture]:
        dy, language = self._anchor(img)
        if dy != dy:  # NaN → якоря "гонка 1" немає
            return []

        captures = []
        for i, base_row in enumerate(COMPLETE_ROWS):
            row = base_row.shifted(0.0, dy)
            # B5: номер = i+1 геометрично, заголовок рядка не перечитуємо.
            time = ocr.read_time(row.sub(COMPLETE_PLAYER_TIME).crop(img))
            car_text = ocr.read_name(row.sub(COMPLETE_PLAYER_CAR).crop(img))
            car = self.car_matcher.match(car_text)
            if time is None and car is None:
                continue
            captures.append(RaceCapture(
                race_number=i + 1,
                car=car,
                time=time,
                source_screen=self.name,
                panel_image=encode_png(row.crop(img)),
                game_language=language,
            ))
        return captures
