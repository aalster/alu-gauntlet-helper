"""Скаут-екрани суперника: пропозиція (екран 2) і реванш-лог (екран 3).

Обидва — 5 ОДНАКОВИХ панелей RACE 1..5 у ряд, без розгорнутої. Гейт (0 OCR):
band_segments дає рівно 5 сегментів однакової ширини SCOUT_W_RANGE — акордеон
(4 вузькі + 1 широка) і решта екранів цей патерн не мають. Якір екрана — бейдж
першої панелі ("RACE 1"/"ГОНКА 1"), він же дає мову інтерфейсу гри.

Номер гонки позиційний (i+1): панелі завжди йдуть 1..5 зліва направо.
Варіант екрана — за чорною плашкою часу внизу панелі (dark_fraction):
є плашка → реванш-лог (карта + час суперника), немає → пропозиція
(карта + назва треку). Іконка карти матчиться шаблонами (MapIconMatcher)
в обох варіантах: (а) при невизначеному треку вона живить звуження за
часом (спека §6) через RaceCapture.map; (б) на екрані 2 назва зматченої
карти (MapIconMatcher.name_of) звужує пошук треку до треків цієї карти —
див. OpponentScoutExtractor._resolve_track."""
import numpy as np

from alu_gauntlet_helper.models import RaceCapture
from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.map_icon_matcher import MapIconMatcher
from alu_gauntlet_helper.screen_recognition.matching import TrackResolver
from alu_gauntlet_helper.screen_recognition.regions import (
    RelRect, SCOUT_HEADER, SCOUT_MAP_ICON, SCOUT_PANEL_BOTTOM, SCOUT_PANEL_TOP,
    SCOUT_TIME, SCOUT_TIME_PLATE_MIN_DARK, SCOUT_TRACK_NAME, SCOUT_W_RANGE,
)
from alu_gauntlet_helper.screen_recognition.screens.base import (
    HEADER_DY_OFFSETS, ScreenExtractor, dark_fraction, encode_png, read_race_header,
)
from alu_gauntlet_helper.screen_recognition.screens.expanded_panel import band_segments

_PANEL_COUNT = 5

# Канали препроцесу назви треку — як в акордеоні (текст білий на градієнті).
TRACK_CHANNELS = ("gray", "min", "max")


def detect_scout_panels(img: np.ndarray) -> list[RelRect] | None:
    """Панелі скаут-екрана або None. Піксельний гейт, 0 OCR: рівно 5 сегментів,
    усі в SCOUT_W_RANGE (акордеонові колонки вужчі, розгорнута панель ширша)."""
    segments = band_segments(img)
    if len(segments) != _PANEL_COUNT:
        return None
    widths = [right - left for left, right in segments]
    if not all(SCOUT_W_RANGE[0] <= w <= SCOUT_W_RANGE[1] for w in widths):
        return None
    return [RelRect(left, SCOUT_PANEL_TOP, right - left,
                    SCOUT_PANEL_BOTTOM - SCOUT_PANEL_TOP)
            for left, right in segments]


class OpponentScoutExtractor(ScreenExtractor):
    """Пропозиція суперника / реванш-лог: 5 панелей → 5 RaceCapture
    (map завжди; track — екран 2; opponent_time — екран 3)."""

    name = "opponent_scout"

    def __init__(self, track_resolver: TrackResolver, map_matcher: MapIconMatcher):
        self.track_resolver = track_resolver
        self.map_matcher = map_matcher

    def _anchor_language(self, img: np.ndarray, first_panel: RelRect) -> str | None:
        """Якір екрана: бейдж першої панелі має читатись як номер 1.
        Повертає мову ("en"/"ru") або None, якщо якоря немає (чужий екран)."""
        for dy in HEADER_DY_OFFSETS:
            number, language = read_race_header(
                img, first_panel.shifted(0.0, dy).sub(SCOUT_HEADER))
            if number == 1:
                return language
        return None

    def _resolve_track(self, crop: np.ndarray, language: str | None, map_name: str | None = None):
        """Назва треку без назви карти: TrackResolver.resolve_track_only() НЕ
        шукає карту в тексті (_best_map тут дає лише хибні спрацювання — див.
        нижче), а звужує пошук до треків map_name, якщо вона вже відома з
        матчингу іконки (MapIconMatcher.name_of); при промаху серед треків цієї
        карти діє глобальний fallback-словник (синонім «сама назва треку», EN і
        RU) — страховка від хибно зматченої іконки.

        Причина, чому НЕ TrackResolver.resolve(): він спершу шукає в тексті
        НАЗВУ КАРТИ (_best_map), якої на цьому екрані немає взагалі (лише назва
        треку). На короткому тексті fuzzy partial_ratio інколи хибно «знаходить»
        чужу коротку назву карти (напр. "CAIRO" проти "RAILROADBUSTLE" дає
        partial_ratio=80 при порозі 75 — випадковий збіг символів, а не назва
        карти в тексті); тоді resolve() шукає трек серед треків ЧУЖОЇ карти й
        не знаходить нічого."""
        lang = "rus" if language == "ru" else "eng"
        best = None
        for channel in TRACK_CHANNELS:
            text = ocr.read_name(crop, channel=channel, lang=lang)
            guess = self.track_resolver.resolve_track_only(text, map_name=map_name)
            if guess is not None and (best is None or guess.score > best.score):
                best = guess
        return best

    def extract(self, img: np.ndarray) -> list[RaceCapture]:
        panels = detect_scout_panels(img)
        if panels is None:
            return []
        language = self._anchor_language(img, panels[0])
        if language is None:
            return []
        captures = []
        for i, panel in enumerate(panels):
            map_guess = self.map_matcher.match(panel.sub(SCOUT_MAP_ICON).crop(img))
            map_name = self.map_matcher.name_of(map_guess.value) if map_guess else None
            time_roi = panel.sub(SCOUT_TIME).crop(img)
            opponent_time = None
            track = None
            if dark_fraction(time_roi) >= SCOUT_TIME_PLATE_MIN_DARK:
                # реванш-лог: чорна плашка → час суперника, назв треків немає
                opponent_time = ocr.read_time(time_roi)
            else:
                # пропозиція: назва треку текстом під іконкою карти; map_name
                # (якщо іконка зматчилась) звужує пошук до треків цієї карти
                track = self._resolve_track(panel.sub(SCOUT_TRACK_NAME).crop(img), language, map_name)
            if map_guess is None and track is None and opponent_time is None:
                continue  # порожня/нечитабельна панель — не засмічуємо сесію
            captures.append(RaceCapture(
                race_number=i + 1,
                track=track,
                map=map_guess,
                opponent_time=opponent_time,
                source_screen=self.name,
                panel_image=encode_png(panel.crop(img)),
                game_language=language,
            ))
        return captures
