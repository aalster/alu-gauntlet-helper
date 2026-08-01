"""C6: геометричний пошук розгорнутої панелі на екрані-акордеоні / CAR SELECTION.

5 гонок лежать у ряд на темному напівпрозорому тлі, між ними — вузькі проміжки
яскравого фону сторінки. Одна гонка розгорнута в широку панель (матчап), решта —
вузькі колонки. Розгорнуту панель і НОМЕР гонки визначаємо геометрично, БЕЗ
OCR: найширший сегмент між проміжками — розгорнутий; кількість вузьких колонок
ліворуч + 1 = номер гонки.

Проміжок розпізнається двома критеріями (або-або):
  - «синій» (B−R високий по всій смузі) — звичайний синій фон сторінки;
  - «яскравий» (min яскравості стовпця по смузі високий) — EN before-варіант
    має інший, не синій фон, але проміжки однаково світлі згори до низу.

Це замінює пошук бейджа "ГОНКА N" на 5 позиціях × 3 зсувах дорогим кириличним
OCR (~95 запусків tesseract на RU-скрін) і водночас править за дешевий гейт
екрана: немає патерну «1 широка + вузькі, разом 5» → це не наш екран.

Калібровано за tests/fixtures/{car_selection_ru_*,accordion_*}.png
(2560x1600, 16:10). Деталі: docs/optimizing-recognition-speed.md.
"""
import cv2
import numpy as np

# Вертикальна смуга, у якій шукаємо проміжки між панелями.
_BAND_TOP, _BAND_BOTTOM = 0.31, 0.71
# Межі зони панелей по горизонталі (поля сторінки зрізаємо).
_X_LEFT, _X_RIGHT = 0.045, 0.915
_GAP_BLUE_MIN = 20        # поріг "синяви" (B−R) стовпця, щоб вважати його проміжком
_GAP_BRIGHT_MIN = 50      # поріг яскравості (min по смузі): світлий проміжок не-синього фону
_NARROW_MAX_W = 0.13      # ширша за це частка кадру — вже не вузька колонка
_MIN_SEG_W = 0.03         # сегменти, вужчі за це, ігноруємо (шум)
# Очікувана ширина розгорнутої панелі (частка кадру): after-варіант ~0.405,
# before-варіант вужчий ~0.348 — нижню межу тримаємо із запасом під обидва.
_EXPANDED_W_RANGE = (0.32, 0.42)
_PANEL_COUNT = 5

# Вузька згорнута колонка на фікстурах — 0.08..0.10 частки кадру; діапазон із
# запасом. Використовується гейтом has_accordion_columns.
_COLUMN_W_RANGE = (0.05, 0.13)


def band_segments(img: np.ndarray) -> list[tuple[float, float]]:
    """Темні сегменти (панелі/колонки) між проміжками у смузі. Жодного OCR."""
    h, w = img.shape[:2]
    band = img[int(_BAND_TOP * h):int(_BAND_BOTTOM * h), :]
    blue = band[:, :, 0].astype(np.int16) - band[:, :, 2].astype(np.int16)
    gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
    k = max(1, int(0.008 * w))
    kernel = np.ones(k) / k
    smooth_blue = np.convolve(blue.min(axis=0), kernel, mode="same")
    smooth_bright = np.convolve(gray.min(axis=0).astype(np.float32), kernel, mode="same")
    is_gap = (smooth_blue > _GAP_BLUE_MIN) | (smooth_bright > _GAP_BRIGHT_MIN)

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
    return segments


def find_expanded(segments: list[tuple[float, float]]) -> tuple[float, float, int] | None:
    """(left, right, race_number) розгорнутої панелі за сегментами або None.

    Внутрішній яскравий градієнт "VS" може розбити широку панель на кілька
    «широких» сегментів — зливаємо їх в один."""
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


def detect_expanded_panel(img: np.ndarray) -> tuple[float, float, int] | None:
    """(left, right, race_number) розгорнутої панелі або None, якщо це не наш екран."""
    return find_expanded(band_segments(img))


def has_accordion_columns(segments: list[tuple[float, float]]) -> bool:
    """Дешевий гейт запасного OCR-пошуку: чи схожа смуга на акордеон узагалі.

    В акордеона (обидва варіанти, обидві мови) завжди рівно 4 вузькі згорнуті
    колонки шириною ~0.08–0.10; на чужих фікстурах у діапазон _COLUMN_W_RANGE
    влучає щонайбільше 3 сегменти. Немає 4 колонок → OCR-пошук марний."""
    columns = [s for s in segments if _COLUMN_W_RANGE[0] <= s[1] - s[0] < _COLUMN_W_RANGE[1]]
    return len(columns) >= _PANEL_COUNT - 1
