import cv2
import numpy as np

from alu_gauntlet_helper.models import FieldGuess, RaceCapture
from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.matching import TrackResolver, VocabularyMatcher
from alu_gauntlet_helper.screen_recognition.regions import (
    BEFORE_RACE_MIN_WHITE_FRAC, BEFORE_RACE_PLAYER_CAR, BEFORE_RACE_PLAYER_RANK,
    BEFORE_RACE_SLOTS, BEFORE_RACE_TRACK, BEFORE_RACE_WHITE_THRESHOLD,
)
from alu_gauntlet_helper.screen_recognition.screens.base import ScreenExtractor, encode_png

# Кадр цілком (природного кропу панелі тут немає), зменшений удвічі — щоб не
# роздувати збережений для рев'ю PNG. Так само як у RaceResultExtractor.
REVIEW_IMAGE_SCALE = 0.5

# Назва карти намальована світло-блакитним, назва треку — білим, обидва на
# яскравому градієнті з білою іконкою-логотипом ліворуч. У сірому каналі Otsu
# на цьому фоні часто видає порожнечу/сміття. Канали ловлять текст по-різному
# (min — білий трек, max — блакитну карту), тож пробуємо всі й беремо найкращий
# resolve. gray першим — зберігає стару поведінку, де він давав повний рядок.
# Біле авто гравця так само читається нерівно по каналах — той самий підхід.
TRACK_CHANNELS = ("gray", "min", "max")
CAR_CHANNELS = ("gray", "min", "max")


class BeforeRaceExtractor(ScreenExtractor):
    """Екран перед стартом однієї гонки.

    Зверху зліва — карта і трек; знизу справа — індикатор "RACE 1 2 3 4 5", де
    поточний номер яскраво-білий. Знизу матчап авто: зліва суперник, справа
    гравець — беремо номер гонки, трек, авто гравця (праве) і його ранг. Час
    гравця лишається None — його добере екран результату.
    """

    name = "before_race"

    def __init__(self, track_resolver: TrackResolver, car_matcher: VocabularyMatcher):
        self.track_resolver = track_resolver
        self.car_matcher = car_matcher

    def _white_fraction(self, roi: np.ndarray) -> float:
        """Частка яскраво-білих пікселів (високий min-канал) у слоті."""
        if roi.size == 0:
            return 0.0
        return float((roi.min(axis=2) > BEFORE_RACE_WHITE_THRESHOLD).mean())

    def _current_race(self, img: np.ndarray) -> int | None:
        """Номер поточної гонки: найбіліший слот, чия OCR-цифра збігається з
        його позицією. Самоідентифікувальний якір екрана — на чужих екранах
        яскраве біле тло у слоті не читається як потрібна цифра, тож відсівається.

        Перебираємо слоти від найбілішого: стороннє яскраве тло, що випадково
        перебило поточну цифру за яскравістю, не пройде перевірку цифри й
        пропускається на користь справжнього номера."""
        scored = sorted(
            ((self._white_fraction(slot.crop(img)), i, slot) for i, slot in enumerate(BEFORE_RACE_SLOTS)),
            key=lambda t: t[0], reverse=True,
        )
        for frac, i, slot in scored:
            if frac < BEFORE_RACE_MIN_WHITE_FRAC:
                break
            if ocr.read_bright_digit(slot.crop(img)) == i + 1:
                return i + 1
        return None

    @staticmethod
    def _best_over_channels(crop: np.ndarray, channels, match) -> FieldGuess | None:
        """OCR кропу в кожному каналі → match → найвпевненіший збіг."""
        best: FieldGuess | None = None
        for channel in channels:
            guess = match(ocr.read_name(crop, channel=channel))
            if guess is not None and (best is None or guess.score > best.score):
                best = guess
        return best

    def _resolve_track(self, img: np.ndarray) -> FieldGuess | None:
        """Найкращий resolve треку по всіх каналах препроцесу (див. TRACK_CHANNELS)."""
        return self._best_over_channels(
            BEFORE_RACE_TRACK.crop(img), TRACK_CHANNELS, self.track_resolver.resolve)

    def _resolve_car(self, img: np.ndarray) -> FieldGuess | None:
        """Авто гравця (праве в матчапі) — найкращий збіг по каналах."""
        return self._best_over_channels(
            BEFORE_RACE_PLAYER_CAR.crop(img), CAR_CHANNELS, self.car_matcher.match)

    def extract(self, img: np.ndarray) -> list[RaceCapture]:
        race_number = self._current_race(img)
        if race_number is None:
            return []

        review_image = cv2.resize(img, None, fx=REVIEW_IMAGE_SCALE, fy=REVIEW_IMAGE_SCALE,
                                  interpolation=cv2.INTER_AREA)
        return [RaceCapture(
            race_number=race_number,
            track=self._resolve_track(img),
            car=self._resolve_car(img),
            rank=ocr.read_rank(BEFORE_RACE_PLAYER_RANK.crop(img)),
            source_screen=self.name,
            panel_image=encode_png(review_image),
        )]
