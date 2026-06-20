"""ЕКСПЕРИМЕНТАЛЬНИЙ швидкий RaceResultExtractor: той самий екран, що
RaceResultExtractor, але заголовок читає через base_fast.read_race_header_fast
(B2/B3/B4). Решта логіки ідентична. Для замірів, наявний не змінює.
"""
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
    HEADER_DY_OFFSETS, ScreenExtractor, encode_png,
)
from alu_gauntlet_helper.screen_recognition.screens.base_fast import read_race_header_fast

REVIEW_IMAGE_SCALE = 0.5


class RaceResultFastExtractor(ScreenExtractor):
    name = "race_result_fast"

    def __init__(self, car_matcher: VocabularyMatcher):
        self.car_matcher = car_matcher

    def _race_number(self, img: np.ndarray) -> tuple[int | None, str | None]:
        for dy in HEADER_DY_OFFSETS:
            number, language = read_race_header_fast(img, RACE_RESULT_HEADER.shifted(0.0, dy))
            if number is not None:
                return number, language
        return None, None

    def extract(self, img: np.ndarray) -> list[RaceCapture]:
        race_number, language = self._race_number(img)
        if race_number is None:
            return []

        time = ocr.read_time(RACE_RESULT_PLAYER_TIME.crop(img))
        car_text = ocr.read_name(RACE_RESULT_PLAYER_CAR.crop(img))
        car = self.car_matcher.match(car_text)
        if time is None and car is None:
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
            game_language=language,
        )]
