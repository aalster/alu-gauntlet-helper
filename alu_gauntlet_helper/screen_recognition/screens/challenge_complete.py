import numpy as np

from alu_gauntlet_helper.models import RaceCapture
from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.matching import VocabularyMatcher
from alu_gauntlet_helper.screen_recognition.regions import (
    COMPLETE_PLAYER_CAR, COMPLETE_PLAYER_TIME, COMPLETE_RACE_BADGE, COMPLETE_ROWS,
)
from alu_gauntlet_helper.screen_recognition.screens.base import (
    HEADER_DY_OFFSETS, RACE_HEADER_RE, ScreenExtractor, encode_png,
)


class ChallengeCompleteExtractor(ScreenExtractor):
    """Підсумковий екран челенджа ("CHALLENGE WON/LOST"): 5 рядків-результатів.

    У кожному рядку зліва час і авто СУПЕРНИКА — їх не чіпаємо; справа час і
    авто ГРАВЦЯ. Треку й рангу на екрані немає: сесія добере трек із захоплень
    акордеона за номером гонки.
    """

    name = "challenge_complete"

    def __init__(self, car_matcher: VocabularyMatcher):
        self.car_matcher = car_matcher

    def _badge_matches(self, img: np.ndarray, row, race_number: int) -> bool:
        """Бейдж рядка читається саме як "RACE <race_number>". На чужих екранах
        (колонки акордеона) у регіон потрапляє кілька заголовків і читається
        "RACE1 RACE2 ..." — тому всі знайдені токени мають бути потрібним номером."""
        text = ocr.read_text(row.sub(COMPLETE_RACE_BADGE).crop(img), "RACE12345")
        tokens = RACE_HEADER_RE.findall(text)
        return bool(tokens) and set(tokens) == {str(race_number)}

    def _find_dy(self, img: np.ndarray) -> float | None:
        """Якір екрана: перший рядок читається як "RACE 1". Рядки зсуваються
        разом, тож знайдений вертикальний зсув застосовується до всіх."""
        for dy in HEADER_DY_OFFSETS:
            if self._badge_matches(img, COMPLETE_ROWS[0].shifted(0.0, dy), 1):
                return dy
        return None

    def extract(self, img: np.ndarray) -> list[RaceCapture]:
        dy = self._find_dy(img)
        if dy is None:
            return []

        captures = []
        for i, base_row in enumerate(COMPLETE_ROWS):
            row = base_row.shifted(0.0, dy)
            if i > 0 and not self._badge_matches(img, row, i + 1):
                continue
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
            ))
        return captures
