import numpy as np

from alu_gauntlet_helper.models import RaceCapture
from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.matching import VocabularyMatcher
from alu_gauntlet_helper.screen_recognition.regions import (
    COMPLETE_PLAYER_CAR, COMPLETE_PLAYER_TIME, COMPLETE_RACE_BADGE, COMPLETE_ROWS,
)
from alu_gauntlet_helper.screen_recognition.screens.base import (
    HEADER_DY_OFFSETS, ScreenExtractor, encode_png, read_race_header,
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

    def _badge_number(self, img: np.ndarray, base_row) -> tuple[int | None, float, str | None]:
        """Бейдж рядка "RACE N"/"ГОНКА N". → (номер, dy, мова). Скан dy: рядки
        зсуваються разом, тож dy першого рядка-якоря застосовний до решти."""
        for dy in HEADER_DY_OFFSETS:
            number, language = read_race_header(img, base_row.shifted(0.0, dy).sub(COMPLETE_RACE_BADGE))
            if number is not None:
                return number, dy, language
        return None, 0.0, None

    def extract(self, img: np.ndarray) -> list[RaceCapture]:
        # Якір екрана: перший рядок читається як "RACE 1" / "ГОНКА 1".
        first_number, dy, language = self._badge_number(img, COMPLETE_ROWS[0])
        if first_number != 1:
            return []

        captures = []
        for i, base_row in enumerate(COMPLETE_ROWS):
            row = base_row.shifted(0.0, dy)
            # B5: заголовки рядків 2..5 НЕ перечитуємо — рядки рівновіддалені, тож
            # номер i-го = i+1 геометрично (раніше тут був повторний дорогий
            # read_race_header на кожен рядок, ~45 зайвих запусків tesseract на
            # RU-скрін). Порожній рядок однаково відсівається перевіркою нижче.
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
