"""Результат заїзду тренування: таблиця RACE RESULTS / РЕЗУЛЬТАТЫ ГОНКИ.

Гейт (0 OCR): яскравий білий рядок таблиці (головний дискримінатор: ≥0.90 на
фікстурах проти ≤0.09 на всіх інших екранах) + темна плашка часу в шапці.
Якір — текст плашки "YOUR TIME"/"ТВОЕ ВРЕМЯ", він же дає мову інтерфейсу.

Час беремо з плашки шапки (це завжди час ГРАВЦЯ). Авто — з колонки CAR NAME
рядка таблиці, і лише коли час рядка збігається з часом шапки: якщо в лобі
хтось є ще і перший рядок не мій, чуже авто не підтягнеться. Варіант екрана
RACE REWARDS (авто лише картинкою) свідомо не підтримується.
"""
import re

import cv2
import numpy as np

from alu_gauntlet_helper.models import RaceCapture
from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.matching import VocabularyMatcher
from alu_gauntlet_helper.screen_recognition.regions import (
    TRAINING_RESULT_HEADER_PLATE, TRAINING_RESULT_MIN_HEADER_DARK,
    TRAINING_RESULT_MIN_ROW_BRIGHT, TRAINING_RESULT_ROW, TRAINING_RESULT_ROW_CAR,
    TRAINING_RESULT_ROW_TIME,
)
from alu_gauntlet_helper.screen_recognition.screens.base import (
    ScreenExtractor, bright_fraction, dark_fraction, encode_png,
)

# Кадр цілком (природного кропу немає), зменшений удвічі — як у race_result.
REVIEW_IMAGE_SCALE = 0.5

_EN_ANCHOR_RE = re.compile(r"YOUR\s*TIME")
# кирилиця читається без whitelist; «ВРЕМЯ» достатньо самоідентифікувальне
_RU_ANCHOR_RE = re.compile(r"ВРЕМЯ")


def looks_like_training_result(img: np.ndarray) -> bool:
    """Піксельна сигнатура екрана результату тренування — без жодного OCR."""
    return (bright_fraction(TRAINING_RESULT_ROW.crop(img)) >= TRAINING_RESULT_MIN_ROW_BRIGHT
            and dark_fraction(TRAINING_RESULT_HEADER_PLATE.crop(img)) >= TRAINING_RESULT_MIN_HEADER_DARK)


class TrainingResultExtractor(ScreenExtractor):
    """Результат заїзду → один RaceCapture з часом (+авто, якщо рядок мій).
    Номер заїзду не призначає (race_number=0) — сесія веде власну нумерацію."""

    name = "training_result"

    def __init__(self, car_matcher: VocabularyMatcher):
        self.car_matcher = car_matcher

    @staticmethod
    def _language(plate: np.ndarray) -> str | None:
        """Якір екрана: лейбл плашки часу. max-канал — білий текст і зелені
        цифри на чорній плашці лишаються яскравими."""
        if _EN_ANCHOR_RE.search(ocr.read_text(plate, channel="max")):
            return "en"
        if _RU_ANCHOR_RE.search(ocr.read_text(plate, channel="max", lang="rus")):
            return "ru"
        return None

    def extract(self, img: np.ndarray) -> list[RaceCapture]:
        if not looks_like_training_result(img):
            return []
        plate = TRAINING_RESULT_HEADER_PLATE.crop(img)
        language = self._language(plate)
        if language is None:
            return []
        time = ocr.read_time(plate)
        if time is None:
            return []

        car = None
        if ocr.read_time(TRAINING_RESULT_ROW_TIME.crop(img)) == time:
            car = self.car_matcher.match(ocr.read_name(TRAINING_RESULT_ROW_CAR.crop(img)))

        review_image = cv2.resize(img, None, fx=REVIEW_IMAGE_SCALE, fy=REVIEW_IMAGE_SCALE,
                                  interpolation=cv2.INTER_AREA)
        return [RaceCapture(
            race_number=0,
            car=car,
            time=time,
            source_screen=self.name,
            panel_image=encode_png(review_image),
            game_language=language,
        )]
