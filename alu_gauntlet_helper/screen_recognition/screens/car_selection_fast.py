"""ЕКСПЕРИМЕНТАЛЬНИЙ швидкий екстрактор екрана CAR SELECTION ("ВЫБОР АВТО").

Це той самий екран, що його обробляє ChallengeAccordionExtractor: 5 гонок, одна
розгорнута в широку панель із матчапом (зліва суперник, справа авто гравця +
ранг), решта — вузькі колонки. На RU наявний екстрактор шукає розгорнуту панель,
читаючи бейдж "ГОНКА N" на 5 позиціях × 3 зсувах дорогим кириличним OCR-шляхом —
~100 запусків tesseract, ~15 с на скрин.

Тут інша стратегія (демонстрація пунктів C6 + B2 з docs/optimizing-recognition-speed.md):

  C6 — РОЗГОРНУТУ ПАНЕЛЬ І НОМЕР ГОНКИ знаходимо ГЕОМЕТРИЧНО, без жодного OCR:
       панелі лежать на темному напівпрозорому тлі, між ними — яскраво-сині
       проміжки фону сторінки. Найширший сегмент між проміжками = розгорнута
       панель; кількість вузьких колонок ліворуч від неї + 1 = номер гонки.
       Це ж і дешевий гейт екрана: немає характерного патерну "1 широка + вузькі,
       разом 5" → це не наш екран, повертаємо [].

  B2 — МОВУ визначаємо ОДНИМ читанням бейджа (латинська проба: є "RACE" → en,
       інакше ru), далі трек читаємо лише в одній мові, а не в обох.

Екстрактор НЕ замінює наявний — це окрема реалізація для замірів (див.
scripts/bench_recognition.py). Калібровано за tests/fixtures/car_selection_ru_*.png
та accordion_ru_*.png (2560x1600, 16:10).
"""
import re

import numpy as np

from alu_gauntlet_helper.models import FieldGuess, RaceCapture
from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.matching import TrackResolver, VocabularyMatcher
from alu_gauntlet_helper.screen_recognition.regions import RelRect
from alu_gauntlet_helper.screen_recognition.screens.base import ScreenExtractor, encode_png
# detect_expanded_panel винесено у спільний модуль (його ж використовує
# ChallengeAccordionExtractor у продакшені). Реекспорт для тестів цього модуля.
from alu_gauntlet_helper.screen_recognition.screens.expanded_panel import detect_expanded_panel

# Розгорнута панель: верх 0.265, низ 0.72 (частки кадру). Підрегіони нижче —
# частки цієї панелі. Відкалібровано за car_selection_ru_*.png.
_PANEL_TOP = 0.265
_PANEL_H = 0.455

# Підрегіони відносно розгорнутої панелі (частки панелі).
_BADGE = RelRect(0.30, 0.0, 0.40, 0.12)    # "ГОНКА N" / "RACE N" — лише для мови
_TRACK = RelRect(0.30, 0.18, 0.40, 0.42)   # карта + marquee-фрагмент треку (центр)
_PLAYER_CAR = RelRect(0.66, 0.11, 0.34, 0.20)  # бренд+модель авто гравця (праворуч)
_PLAYER_RANK = RelRect(0.82, 0.27, 0.18, 0.10)  # ранг "N NNN S" під авто

_TRACK_CHANNELS = ("gray", "min", "max")
_CAR_CHANNELS = ("min", "gray")
_RACE_WORD_RE = re.compile(r"RACE")


class CarSelectionFastExtractor(ScreenExtractor):
    name = "car_selection_fast"

    def __init__(self, track_resolver: TrackResolver, car_matcher: VocabularyMatcher):
        self.track_resolver = track_resolver
        self.car_matcher = car_matcher

    def _probe_language(self, panel: RelRect, img: np.ndarray) -> str:
        """B2: одне латинське читання бейджа. "RACE" видно → en, інакше ru."""
        text = ocr.read_text(panel.sub(_BADGE).crop(img), "RACE12345")
        return "en" if _RACE_WORD_RE.search(text) else "ru"

    def _resolve_track(self, panel: RelRect, img: np.ndarray, lang: str) -> FieldGuess | None:
        crop = panel.sub(_TRACK).crop(img)
        ocr_lang = "rus" if lang == "ru" else "eng"
        best: FieldGuess | None = None
        for channel in _TRACK_CHANNELS:
            guess = self.track_resolver.resolve(ocr.read_name(crop, channel=channel, lang=ocr_lang))
            if guess is not None and (best is None or guess.score > best.score):
                best = guess
        return best

    def _resolve_car(self, panel: RelRect, img: np.ndarray) -> FieldGuess | None:
        crop = panel.sub(_PLAYER_CAR).crop(img)
        best: FieldGuess | None = None
        for channel in _CAR_CHANNELS:
            guess = self.car_matcher.match(ocr.read_name(crop, channel=channel))
            if guess is not None and (best is None or guess.score > best.score):
                best = guess
        return best

    def extract(self, img: np.ndarray) -> list[RaceCapture]:
        detected = detect_expanded_panel(img)
        if detected is None:
            return []
        left, right, race_number = detected
        panel = RelRect(left, _PANEL_TOP, right - left, _PANEL_H)

        language = self._probe_language(panel, img)
        track = self._resolve_track(panel, img, language)
        car = self._resolve_car(panel, img)
        rank = ocr.read_rank(panel.sub(_PLAYER_RANK).crop(img))

        # Екран = вибір авто перед гонкою: час гравця ще не їхав (показано
        # "TIME TO BEAT" суперника), тож time лишаємо None.
        return [RaceCapture(
            race_number=race_number,
            track=track,
            car=car,
            rank=rank,
            source_screen=self.name,
            panel_image=encode_png(panel.crop(img)),
            game_language=language,
        )]
