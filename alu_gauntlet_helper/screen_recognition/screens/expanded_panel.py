"""C6: геометричний пошук розгорнутої панелі на екрані-акордеоні / CAR SELECTION.

5 гонок лежать у ряд на темному напівпрозорому тлі, між ними — яскраво-сині
проміжки фону сторінки. Одна гонка розгорнута в широку панель (матчап), решта —
вузькі колонки. Розгорнуту панель і НОМЕР гонки визначаємо геометрично, БЕЗ
OCR: найширший сегмент між проміжками — розгорнутий; кількість вузьких колонок
ліворуч + 1 = номер гонки.

Це замінює пошук бейджа "ГОНКА N" на 5 позиціях × 3 зсувах дорогим кириличним
OCR (~95 запусків tesseract на RU-скрін) і водночас править за дешевий гейт
екрана: немає патерну «1 широка + вузькі, разом 5» → це не наш екран.

Калібровано за tests/fixtures/{car_selection_ru_*,accordion_ru_*}.png
(2560x1600, 16:10). Деталі: docs/optimizing-recognition-speed.md.
"""
import numpy as np

# Вертикальна смуга, у якій шукаємо проміжки між панелями.
_BAND_TOP, _BAND_BOTTOM = 0.31, 0.71
# Межі зони панелей по горизонталі (поля сторінки зрізаємо).
_X_LEFT, _X_RIGHT = 0.045, 0.915
_GAP_BLUE_MIN = 20        # поріг "синяви" (B−R) стовпця, щоб вважати його проміжком
_NARROW_MAX_W = 0.13      # ширша за це частка кадру — вже не вузька колонка
_MIN_SEG_W = 0.03         # сегменти, вужчі за це, ігноруємо (шум)
_EXPANDED_W_RANGE = (0.36, 0.42)  # очікувана ширина розгорнутої панелі (частка кадру)
_PANEL_COUNT = 5


def detect_expanded_panel(img: np.ndarray) -> tuple[float, float, int] | None:
    """(left, right, race_number) розгорнутої панелі або None, якщо це не наш екран.

    Жодного OCR. Внутрішній яскравий градієнт "VS" може розбити широку панель на
    кілька «широких» сегментів — зливаємо їх в один."""
    h, w = img.shape[:2]
    blue = img[:, :, 0].astype(np.int16) - img[:, :, 2].astype(np.int16)
    band = blue[int(_BAND_TOP * h):int(_BAND_BOTTOM * h), :]
    col_min = band.min(axis=0)  # проміжок лишається синім по всій смузі
    k = max(1, int(0.008 * w))
    smooth = np.convolve(col_min, np.ones(k) / k, mode="same")
    is_gap = smooth > _GAP_BLUE_MIN

    segments: list[tuple[float, float]] = []
    x, x_end = int(_X_LEFT * w), int(_X_RIGHT * w)
    while x < x_end:
        if is_gap[x]:
            x += 1
            continue
        start = x
        while x < x_end and not is_gap[x]:
            x += 1
        if (x - start) > _MIN_SEG_W * w:
            segments.append((start / w, x / w))

    wide = [s for s in segments if s[1] - s[0] >= _NARROW_MAX_W]
    if not wide:
        return None
    exp_left = min(s[0] for s in wide)
    exp_right = max(s[1] for s in wide)
    if not (_EXPANDED_W_RANGE[0] < exp_right - exp_left < _EXPANDED_W_RANGE[1]):
        return None

    narrow = [s for s in segments if s[1] - s[0] < _NARROW_MAX_W]
    n_left = sum(1 for s in narrow if s[1] <= exp_left + 0.005)
    n_right = sum(1 for s in narrow if s[0] >= exp_right - 0.005)
    if n_left + 1 + n_right != _PANEL_COUNT:
        return None
    return exp_left, exp_right, n_left + 1
