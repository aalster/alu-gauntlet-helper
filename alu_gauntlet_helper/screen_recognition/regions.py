from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RelRect:
    """Прямокутник у частках ширини/висоти кадру — не залежить від роздільної здатності."""
    x: float
    y: float
    w: float
    h: float

    def to_abs(self, width: int, height: int) -> tuple[int, int, int, int]:
        return round(self.x * width), round(self.y * height), round(self.w * width), round(self.h * height)

    def crop(self, img: np.ndarray) -> np.ndarray:
        img_h, img_w = img.shape[:2]
        x, y, w, h = self.to_abs(img_w, img_h)
        x, y = max(x, 0), max(y, 0)
        w, h = min(w, img_w - x), min(h, img_h - y)
        return img[y:y + h, x:x + w]

    def sub(self, rel: "RelRect") -> "RelRect":
        """Вкладений регіон, координати якого задані відносно цього прямокутника."""
        return RelRect(self.x + rel.x * self.w, self.y + rel.y * self.h, rel.w * self.w, rel.h * self.h)

    def shifted(self, dx: float, dy: float) -> "RelRect":
        return RelRect(self.x + dx, self.y + dy, self.w, self.h)


# --- Екран-акордеон челенджа (5 панелей, одна розгорнута) -------------------
# Екран має ДВА варіанти:
#   BEFORE — гонку ще не їхали: зліва авто суперника, в центрі трек,
#            справа "SELECT CAR", знизу зліва "TIME TO BEAT" (час суперника).
#            Даних гравця на цьому варіанті НЕМАЄ.
#   AFTER  — гонку вже їхали: зліва суперник, у центрі трек, СПРАВА авто
#            гравця з рангом, знизу справа "YOUR TIME" (час гравця),
#            у заголовку справа бейдж WON/LOST.
#
# Відкалібровано за tests/fixtures/accordion_before_{1,3,5}.png та
# accordion_after_{1,2,4}.png (2559x1599, 16:10). Виміряно програмно за
# темними смугами заголовків панелей: ліві краї розгорнутої панелі
# race 1..5 = 0.072 + 0.113*(i-1), ширина 0.405; вертикально 0.273..0.728.
# На цій роздільній здатності сітки обох варіантів збігаються, але списки
# тримаємо окремо — на інших пристроях/співвідношеннях вони можуть розійтись.
# ВАЖЛИВО: ROI задаються з запасом ~10-15% — точність добирає OCR-якір
# "RACE N" (скан зсувів у екстракторі) + словникове зіставлення.

ACCORDION_BEFORE_PANELS = [RelRect(0.06 + 0.113 * i, 0.26, 0.42, 0.49) for i in range(5)]
ACCORDION_AFTER_PANELS = [RelRect(0.06 + 0.113 * i, 0.26, 0.42, 0.49) for i in range(5)]

# Вкладені регіони відносно розгорнутої панелі (частки панелі).
# Header звужено по горизонталі: вертикальна лінія рамки панелі на краю кропу
# ламає tesseract (порожній результат), відступ 5% її відрізає.
ACCORDION_HEADER = RelRect(0.05, 0.0, 0.90, 0.12)  # "RACE N" (+ бейдж WON/LOST у варіанті after)

# BEFORE: у центрі панелі назва карти + треку (трек може бути обрізаний "...").
BEFORE_TRACK_NAME = RelRect(0.30, 0.27, 0.45, 0.17)

# AFTER: трек у центрі (між двома авто), праворуч авто гравця + ранг,
# знизу праворуч значення "YOUR TIME".
AFTER_TRACK_NAME = RelRect(0.30, 0.27, 0.45, 0.20)
AFTER_PLAYER_CAR = RelRect(0.62, 0.12, 0.38, 0.18)   # бренд + модель авто гравця
AFTER_PLAYER_RANK = RelRect(0.68, 0.26, 0.32, 0.13)  # ранг "4,795 S" під назвою авто
AFTER_PLAYER_TIME = RelRect(0.55, 0.78, 0.45, 0.18)  # час "00:19.130" (без лейбла YOUR TIME)


# --- Екран результату однієї гонки ("RACE N WON/LOST!" зверху) ---------------
# Показується одразу після фінішу: зліва авто СУПЕРНИКА з "TIME TO BEAT",
# справа авто ГРАВЦЯ з рангом і "YOUR TIME". У центрі знизу — нік суперника
# та його клуб (НЕ трек: назви треку на цьому екрані немає взагалі).
# Регіони — частки повного кадру. Відкалібровано за
# tests/fixtures/race_result_4_lost.png (2559x1599, 16:10).

RACE_RESULT_HEADER = RelRect(0.08, 0.03, 0.30, 0.10)       # "RACE N WON/LOST!"
RACE_RESULT_PLAYER_CAR = RelRect(0.74, 0.30, 0.24, 0.10)   # бренд + модель авто гравця
RACE_RESULT_PLAYER_RANK = RelRect(0.74, 0.40, 0.24, 0.07)  # ранг "5,130 S" під назвою авто
RACE_RESULT_PLAYER_TIME = RelRect(0.68, 0.74, 0.28, 0.12)  # час "00:24.182" (без лейбла YOUR TIME)
