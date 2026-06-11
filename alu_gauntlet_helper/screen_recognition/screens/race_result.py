import cv2
import numpy as np

from alu_gauntlet_helper.models import RaceCapture
from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.matching import VocabularyMatcher
from alu_gauntlet_helper.screen_recognition.regions import (
    RACE_RESULT_HEADER, RACE_RESULT_PLAYER_CAR, RACE_RESULT_PLAYER_RANK,
    RACE_RESULT_PLAYER_TIME,
)
from alu_gauntlet_helper.screen_recognition.screens.base import (
    HEADER_DY_OFFSETS, RACE_HEADER_RE, ScreenExtractor, encode_png,
)

# Кадр цілком (на відміну від панелі акордеона тут немає природного кропу),
# зменшений удвічі — щоб не роздувати збережений PNG для рев'ю.
REVIEW_IMAGE_SCALE = 0.5


class RaceResultExtractor(ScreenExtractor):
    """Екран результату однієї гонки: "RACE N WON/LOST!" у заголовку зверху.

    Зліва авто СУПЕРНИКА і його "TIME TO BEAT" — їх не чіпаємо; справа авто
    ГРАВЦЯ, його ранг і "YOUR TIME". Назви треку на екрані немає (у центрі —
    нік суперника та його клуб), тож track лишається None: сесія добере його
    з захоплень акордеона за номером гонки.

    Номер гонки беремо саме із заголовка, а не з індикатора прогресу знизу:
    заголовок — великий шрифт із самоідентифікувальним якорем "RACE N", тоді
    як унизу дві дрібні цифри поруч ("поточна" і "всього"), які OCR плутає.
    """

    name = "race_result"

    def __init__(self, car_matcher: VocabularyMatcher):
        self.car_matcher = car_matcher

    def _race_number(self, img: np.ndarray) -> int | None:
        """Якір екрана: зверху зліва читається "RACE N" (бейдж WON/LOST і
        трикутне лого відфільтровує whitelist). Вимагаємо єдиний номер —
        кілька різних токенів означали б, що це не той екран."""
        for dy in HEADER_DY_OFFSETS:
            text = ocr.read_text(RACE_RESULT_HEADER.shifted(0.0, dy).crop(img), "RACE12345")
            tokens = RACE_HEADER_RE.findall(text)
            if tokens and len(set(tokens)) == 1:
                return int(tokens[0])
        return None

    def extract(self, img: np.ndarray) -> list[RaceCapture]:
        race_number = self._race_number(img)
        if race_number is None:
            return []

        time = ocr.read_time(RACE_RESULT_PLAYER_TIME.crop(img))
        car_text = ocr.read_name(RACE_RESULT_PLAYER_CAR.crop(img))
        car = self.car_matcher.match(car_text)
        if time is None and car is None:
            # заголовок схожий, але даних гравця немає — не наш екран
            return []

        review_image = cv2.resize(img, None, fx=REVIEW_IMAGE_SCALE, fy=REVIEW_IMAGE_SCALE,
                                  interpolation=cv2.INTER_AREA)
        return [RaceCapture(
            race_number=race_number,
            car=car,
            rank=ocr.read_rank(RACE_RESULT_PLAYER_RANK.crop(img)),
            time=time,
            source_screen=self.name,
            panel_image=encode_png(review_image),
        )]
