"""Лобі приватної кімнати (тренування): карта + трек текстом зверху зліва.

Гейт (0 OCR): темна плашка ROOM ID знизу зліва + яскрава жовта кнопка READY
знизу справа — комбінація, якої немає на жодному челендж-екрані. Якір — сам
resolve треку: назва карти над назвою треку, як на before_race, тож
TrackResolver.resolve працює повним текстом. Мова — за мовним проходом, що дав
кращий resolve (текстового якоря мови на екрані немає, як і на before_race).

Авто гравця на екрані є лише картинкою — його свідомо не чіпаємо: авто заїзду
приходить з екрана результату (тренуватись можна різними авто на одному треку).
"""
import cv2
import numpy as np

from alu_gauntlet_helper.models import FieldGuess, RaceCapture
from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.matching import TrackResolver
from alu_gauntlet_helper.screen_recognition.regions import (
    TRAINING_LOBBY_MIN_READY_BRIGHT, TRAINING_LOBBY_MIN_ROOM_DARK,
    TRAINING_LOBBY_READY, TRAINING_LOBBY_ROOM_PLATE, TRAINING_LOBBY_TRACK,
)
from alu_gauntlet_helper.screen_recognition.screens.base import (
    ScreenExtractor, bright_fraction, dark_fraction, encode_png,
)

# Кадр цілком (природного кропу немає), зменшений удвічі — як у race_result.
REVIEW_IMAGE_SCALE = 0.5

# Назви на тайлі карти білі/світлі на темному тлі — читаються всіма каналами
# (перевірено на фікстурах), але тримаємо повний набір, як before_race: на
# інших роздільностях/фонах канали ловлять текст по-різному.
TRACK_CHANNELS = ("gray", "min", "max")


def looks_like_training_lobby(img: np.ndarray) -> bool:
    """Піксельна сигнатура лобі — без жодного OCR."""
    return (dark_fraction(TRAINING_LOBBY_ROOM_PLATE.crop(img)) >= TRAINING_LOBBY_MIN_ROOM_DARK
            and bright_fraction(TRAINING_LOBBY_READY.crop(img)) >= TRAINING_LOBBY_MIN_READY_BRIGHT)


class TrainingLobbyExtractor(ScreenExtractor):
    """Лобі тренування → один RaceCapture з треком/картою (без часу й авто).
    Номер заїзду не призначає (race_number=0) — сесія веде власну нумерацію."""

    name = "training_lobby"

    def __init__(self, track_resolver: TrackResolver):
        self.track_resolver = track_resolver

    def _resolve_track(self, img: np.ndarray) -> tuple[FieldGuess | None, str | None]:
        """Resolve треку по каналах і обох мовах → (guess, мова|None)."""
        crop = TRAINING_LOBBY_TRACK.crop(img)
        best: FieldGuess | None = None
        best_language: str | None = None
        for language, lang in (("en", "eng"), ("ru", "rus")):
            for channel in TRACK_CHANNELS:
                guess = self.track_resolver.resolve(ocr.read_name(crop, channel=channel, lang=lang))
                if guess is not None and (best is None or guess.score > best.score):
                    best, best_language = guess, language
        return best, best_language

    def extract(self, img: np.ndarray) -> list[RaceCapture]:
        if not looks_like_training_lobby(img):
            return []
        track, language = self._resolve_track(img)
        if track is None:
            return []  # гейт схожий, але назв карти/треку немає — не наш екран
        review_image = cv2.resize(img, None, fx=REVIEW_IMAGE_SCALE, fy=REVIEW_IMAGE_SCALE,
                                  interpolation=cv2.INTER_AREA)
        return [RaceCapture(
            race_number=0,
            track=track,
            source_screen=self.name,
            panel_image=encode_png(review_image),
            game_language=language,
        )]
