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
    HEADER_DY_OFFSETS, RACE_HEADER_RE, ScreenExtractor, encode_png,
)


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

    def _header_matches(self, img: np.ndarray, panel, race_number: int) -> bool:
        """Самоперевірка: заголовок панелі читається саме як "RACE <race_number>".

        Кроп на позиції розгорнутої панелі i, коли насправді розгорнута інша,
        накриває кілька згорнутих колонок і читається як "RACE1 RACE2 ..." —
        тому вимагаємо, щоб УСІ знайдені токени були потрібним номером.
        Бейдж WON/LOST у заголовку after-варіанта відфільтровує whitelist."""
        header_text = ocr.read_text(panel.sub(ACCORDION_HEADER).crop(img), "RACE12345")
        tokens = RACE_HEADER_RE.findall(header_text)
        return bool(tokens) and set(tokens) == {str(race_number)}

    def _find_expanded(self, img: np.ndarray):
        """Шукає розгорнуту панель: спершу позиції after-варіанта, потім before.
        Повертає (race_number, panel) або None.

        ВАЖЛИВО: якщо ACCORDION_BEFORE_PANELS колись розійдеться з
        ACCORDION_AFTER_PANELS, цей метод має також повертати, у якій сітці
        знайдено панель, бо саме від неї залежить геометрія sub-регіонів
        (BEFORE_* vs AFTER_*), застосованих у extract().

        Сітки варіантів сьогодні збігаються — скануємо лише унікальні,
        щоб не платити подвійну ціну на шляху "екран не розпізнано"."""
        grids = [ACCORDION_AFTER_PANELS]
        if ACCORDION_BEFORE_PANELS != ACCORDION_AFTER_PANELS:
            grids.append(ACCORDION_BEFORE_PANELS)
        for panels in grids:
            for i, base_panel in enumerate(panels):
                for dy in HEADER_DY_OFFSETS:
                    panel = base_panel.shifted(0.0, dy)
                    if self._header_matches(img, panel, i + 1):
                        return i + 1, panel
        return None

    def extract(self, img: np.ndarray) -> list[RaceCapture]:
        found = self._find_expanded(img)
        if not found:
            return []
        race_number, panel = found

        # Варіант визначаємо за ВМІСТОМ, а не за списком, у якому знайшли панель
        # (див. _find_expanded для зауваження щодо розбіжності сіток у майбутньому).
        # AFTER підтверджує час "YOUR TIME" праворуч знизу або розпізнане авто гравця.
        player_time = ocr.read_time(panel.sub(AFTER_PLAYER_TIME).crop(img))
        player_car_text = ocr.read_name(panel.sub(AFTER_PLAYER_CAR).crop(img))
        player_car = self.car_matcher.match(player_car_text)

        if player_time is None and player_car is None:
            # BEFORE: лише номер гонки і трек; дані суперника не чіпаємо.
            track_text = ocr.read_name(panel.sub(BEFORE_TRACK_NAME).crop(img))
            return [RaceCapture(
                race_number=race_number,
                track=self.track_resolver.resolve(track_text),
                source_screen=self.name,
                panel_image=encode_png(panel.crop(img)),
            )]

        track_text = ocr.read_name(panel.sub(AFTER_TRACK_NAME).crop(img))
        return [RaceCapture(
            race_number=race_number,
            track=self.track_resolver.resolve(track_text),
            car=player_car,
            rank=ocr.read_rank(panel.sub(AFTER_PLAYER_RANK).crop(img)),
            time=player_time,
            source_screen=self.name,
            panel_image=encode_png(panel.crop(img)),
        )]
