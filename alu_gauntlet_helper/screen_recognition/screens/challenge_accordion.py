import re

import numpy as np

from alu_gauntlet_helper.models import RaceCapture
from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.matching import TrackResolver, VocabularyMatcher
from alu_gauntlet_helper.screen_recognition.regions import (
    ACCORDION_AFTER_PANELS, ACCORDION_BEFORE_PANELS, ACCORDION_HEADER,
    AFTER_PLAYER_CAR, AFTER_PLAYER_RANK, AFTER_PLAYER_TIME, AFTER_TRACK_NAME,
    BEFORE_TRACK_NAME,
)
from alu_gauntlet_helper.screen_recognition.screens.base import (
    HEADER_DY_OFFSETS, ScreenExtractor, encode_png, read_race_header,
)
from alu_gauntlet_helper.screen_recognition.screens.expanded_panel import detect_expanded_panel

# Канали препроцесу для назви треку (як у before_race): карта блакитна, трек
# білий — різні канали ловлять їх по-різному, беремо найкращий resolve.
TRACK_CHANNELS = ("gray", "min", "max")

_RACE_WORD_RE = re.compile(r"RACE")


class ChallengeAccordionExtractor(ScreenExtractor):
    """Екран-акордеон челенджа: 5 панелей, одна розгорнута.

    Два варіанти екрана:
      BEFORE (гонку ще не їхали) — зліва авто СУПЕРНИКА і його "TIME TO BEAT";
        даних гравця немає, тож повертаємо лише номер гонки і трек.
        Дані суперника НЕ зберігаємо — інакше вони помилково записувались
        як результат гравця (саме це був баг).
      AFTER (гонку вже їхали) — справа авто ГРАВЦЯ, його ранг і "YOUR TIME";
        повертаємо номер гонки, трек і дані гравця з правого боку.
    """

    name = "challenge_accordion"

    def __init__(self, track_resolver: TrackResolver, car_matcher: VocabularyMatcher):
        self.track_resolver = track_resolver
        self.car_matcher = car_matcher

    def _find_expanded(self, img: np.ndarray):
        """Шукає розгорнуту панель → (race_number, panel, language) або None.

        C6: спершу геометричний пошук (detect_expanded_panel) — 0 OCR-викликів на
        панель і номер. Якщо вдалося, мову визначаємо ОДНИМ читанням бейджа (B2:
        латинське "RACE" → en, інакше ru), а panel беремо з відкаліброваної сітки
        ACCORDION_AFTER_PANELS за номером. Якщо геометрія не спрацювала (напр.
        англ. before-екран з іншим тлом) — падаємо у повний OCR-пошук нижче."""
        geom = detect_expanded_panel(img)
        if geom is not None:
            race_number = geom[2]
            panel = ACCORDION_AFTER_PANELS[race_number - 1]
            text = ocr.read_text(panel.sub(ACCORDION_HEADER).crop(img), "RACE12345")
            language = "en" if _RACE_WORD_RE.search(text) else "ru"
            return race_number, panel, language
        return self._find_expanded_by_ocr(img)

    def _find_expanded_by_ocr(self, img: np.ndarray):
        """Запасний OCR-пошук розгорнутої панелі (коли геометрія не спрацювала).

        Заголовок панелі читається як "RACE N"/"ГОНКА N". Кроп на позиції i, коли
        розгорнута інша панель, накриває кілька згорнутих колонок → read_race_header
        повертає None (кілька різних номерів), тож позиція відсівається.

        ВАЖЛИВО: якщо ACCORDION_BEFORE_PANELS колись розійдеться з
        ACCORDION_AFTER_PANELS, цей метод має також повертати, у якій сітці
        знайдено панель, бо саме від неї залежить геометрія sub-регіонів
        (BEFORE_* vs AFTER_*), застосованих у extract().

        Сітки варіантів сьогодні збігаються — скануємо лише унікальні,
        щоб не платити подвійну ціну на шляху "екран не розпізнано"."""
        grids = [ACCORDION_AFTER_PANELS]
        if ACCORDION_BEFORE_PANELS != ACCORDION_AFTER_PANELS:
            grids.append(ACCORDION_BEFORE_PANELS)
        candidates = []  # (race_number, panel, language)
        for panels in grids:
            for i, base_panel in enumerate(panels):
                for dy in HEADER_DY_OFFSETS:
                    panel = base_panel.shifted(0.0, dy)
                    number, language = read_race_header(img, panel.sub(ACCORDION_HEADER))
                    if number == i + 1:
                        candidates.append((i + 1, panel, language))
                        break
        if len(candidates) <= 1:
            return candidates[0] if candidates else None
        # Неоднозначність: коли розгорнуто гонку з вищим номером, згорнуті колонки
        # ліворуч опиняються на позиціях нижчих індексів і їхній бейдж може збігтись
        # (напр. "ГОНКА 2" на позиції i=1, поки насправді розгорнуто гонку 4). Лише
        # справжня розгорнута панель має читабельну назву треку — обираємо за нею.
        return max(candidates, key=lambda c: self._track_score(img, c[1], c[2]))

    def _track_score(self, img: np.ndarray, panel, language: str | None) -> float:
        for region in (BEFORE_TRACK_NAME, AFTER_TRACK_NAME):
            guess = self._resolve_track(panel.sub(region).crop(img), language)
            if guess is not None:
                return guess.score
        return 0.0

    def _resolve_track(self, crop: np.ndarray, language: str | None):
        """Назва треку мовою екрана, найкращий resolve по каналах препроцесу."""
        lang = "rus" if language == "ru" else "eng"
        best = None
        for channel in TRACK_CHANNELS:
            guess = self.track_resolver.resolve(ocr.read_name(crop, channel=channel, lang=lang))
            if guess is not None and (best is None or guess.score > best.score):
                best = guess
        return best

    def extract(self, img: np.ndarray) -> list[RaceCapture]:
        found = self._find_expanded(img)
        if not found:
            return []
        race_number, panel, language = found

        # Варіант визначаємо за ВМІСТОМ, а не за списком, у якому знайшли панель
        # (див. _find_expanded для зауваження щодо розбіжності сіток у майбутньому).
        # AFTER підтверджує час "YOUR TIME" праворуч знизу або розпізнане авто гравця.
        # Авто завжди англійською (lang за замовчуванням "eng").
        player_time = ocr.read_time(panel.sub(AFTER_PLAYER_TIME).crop(img))
        player_car_text = ocr.read_name(panel.sub(AFTER_PLAYER_CAR).crop(img))
        player_car = self.car_matcher.match(player_car_text)

        if player_time is None and player_car is None:
            # BEFORE: лише номер гонки і трек; дані суперника не чіпаємо.
            return [RaceCapture(
                race_number=race_number,
                track=self._resolve_track(panel.sub(BEFORE_TRACK_NAME).crop(img), language),
                source_screen=self.name,
                panel_image=encode_png(panel.crop(img)),
                game_language=language,
            )]

        return [RaceCapture(
            race_number=race_number,
            track=self._resolve_track(panel.sub(AFTER_TRACK_NAME).crop(img), language),
            car=player_car,
            rank=ocr.read_rank(panel.sub(AFTER_PLAYER_RANK).crop(img)),
            time=player_time,
            source_screen=self.name,
            panel_image=encode_png(panel.crop(img)),
            game_language=language,
        )]
