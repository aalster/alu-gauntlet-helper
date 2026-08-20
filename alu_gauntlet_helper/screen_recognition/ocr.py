import os
import re
import sys

import cv2
import numpy as np
from PIL import Image

from alu_gauntlet_helper.screen_recognition import tesseract_api


def _bundled_dir() -> str:
    """Тека портативного Tesseract (DLL + tessdata), що йде в комплекті.

    Frozen-збірка: тека `tesseract/` поруч з exe (її кладе інсталятор).
    Запуск із вихідників: та сама портативна копія з `installer/tesseract/`,
    щоб і в розробці використовувати саме бандлений Tesseract, а не системний.

    tesseract.exe в цій теці на рантаймі не використовується (движок вантажиться
    з DLL) — він лишається для перевірки збірки й ручної діагностики, див.
    installer/README.md."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.join(os.path.dirname(__file__), "..", "..", "installer")
    return os.path.normpath(os.path.join(base, "tesseract"))


# Латиниця для англ. назв і авто. Російські назви читаються БЕЗ whitelist:
# tessedit_char_whitelist з багатобайтними кириличними символами ламає LSTM-движок
# tesseract (повертає "?"), тож для lang="rus" whitelist не передаємо (див. read_name).
NAME_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
TIME_RE = re.compile(r"(\d{1,2})\s*:\s*(\d{2})\s*[.,]\s*(\d{2,3})")  # {2,3}: OCR інколи губить цифру мс
RANK_RE = re.compile(r"(\d)\s*[,.]?\s*(\d{3})")  # [,.]? необов'язковий: OCR інколи губить кому в "4,045"


def configure_tesseract() -> bool:
    """Вказує движку бандлену теку tesseract (DLL + tessdata).

    Завжди тільки комплектний Tesseract — системні установки не шукаємо:
    застосунок має працювати однаково незалежно від того, що стоїть у системі.
    True, якщо DLL на місці (робочість ініціалізації перевіряє is_available)."""
    bundled = _bundled_dir()
    if os.path.exists(os.path.join(bundled, tesseract_api.DLL_NAME)):
        tesseract_api.configure(bundled)
        return True
    return False


def is_available() -> bool:
    """Чи ініціалізується движок (DLL завантажилась, tessdata на місці).

    Ініціалізація лінива й кешується в tesseract_api — повторні виклики дешеві."""
    return tesseract_api.get_engine("eng") is not None


def preprocess(img: np.ndarray, scale: int = 3, channel: str = "gray") -> Image.Image:
    """Кроп ROI → один канал → апскейл → Otsu → темний текст на білому.

    channel:
      "gray" — звичайний сірий (зважена сума каналів);
      "max"  — max(B,G,R) попіксельно: червоний текст (програна гонка) у сірому
               зливається з темною плашкою, а в max-каналі лишається яскравим;
      "min"  — min(B,G,R) попіксельно: гасить червоне СЯЙВО під білим текстом
               (у червоного низький синій), білий текст лишається яскравим."""
    if channel == "max" and img.ndim == 3:
        gray = img.max(axis=2)
    elif channel == "min" and img.ndim == 3:
        gray = img.min(axis=2)
    else:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if binary.mean() < 127:
        binary = cv2.bitwise_not(binary)
    return Image.fromarray(binary)


def _run_ocr(image: Image.Image, lang: str = "eng", psm: int = 7, whitelist: str = "") -> str:
    """Єдина точка запуску OCR (движок у пам'яті).

    Скрипти замірів (bench/survey) рахують виклики, підміняючи саме цю функцію."""
    engine = tesseract_api.get_engine(lang)
    if engine is None:
        raise RuntimeError("Tesseract недоступний: configure_tesseract не знайшов DLL/tessdata")
    return engine.read(image, psm, whitelist)


def read_text(img: np.ndarray, whitelist: str = "", psm: int = 7, channel: str = "gray",
              lang: str = "eng") -> str:
    """lang: "eng" (латиниця/авто) або "rus" (кирилиця). whitelist="" — без обмеження
    символів (кириличні бейджі з логотипом краще читаються без whitelist)."""
    return _run_ocr(preprocess(img, channel=channel), lang=lang, psm=psm,
                    whitelist=whitelist).strip()


TIME_CHANNELS = ("gray", "max", "min")


def read_time(img: np.ndarray) -> int | None:
    """Час читається всіма канальними варіантами з голосуванням.

    «Перший збіг перемагає» тут небезпечний: пульсівне червоне сяйво під
    часом програної гонки на проміжній інтенсивності змушує сірий канал
    читати «4» як «6» (Otsu заливає відкриту верхівку цифри) — збіг валідний
    за форматом, але хибний. Канали помиляються в РІЗНИХ режимах (max рятує
    червоний текст, min гасить сяйво під білим текстом), тож значення,
    підтверджене двома каналами, надійніше за пріоритет будь-якого одного."""
    if img.size == 0:
        return None

    votes: list[int] = []
    for channel in TIME_CHANNELS:
        match = TIME_RE.search(read_text(img, "0123456789:.,", channel=channel))
        if match:
            minutes, seconds = int(match[1]), int(match[2])
            millis = int(match[3][:3].ljust(3, "0"))
            votes.append((minutes * 60 + seconds) * 1000 + millis)

    for value in votes:
        if votes.count(value) >= 2:
            return value
    # консенсусу немає — перше за порядком каналів (стара поведінка)
    return votes[0] if votes else None


# Детекція чорної плашки часу ("YOUR TIME"): плашка майже чорна на блакитному
# тлі, тож шукається як найбільший темний компонент зони пошуку. Пороги:
_PLATE_DARK_THR = 60        # яскравість, нижче якої піксель вважається плашкою
_PLATE_MIN_AREA_FRAC = 0.04  # мін. частка зони: дрібні темні деталі — не плашка
# Зріз країв знайденого прямокутника: краї плашки похилі (паралелограм), а по
# периметру лишається чорна рамка навколо цифр — і те, і те ламає tesseract
# (див. коментарі до *_TIME_ZONE у regions.py: читається стабільно лише кроп
# впритул до цифр, без переходів плашка/фон у кадрі).
_PLATE_SHRINK_X = 0.10
_PLATE_SHRINK_Y = 0.16


def read_time_plate(img: np.ndarray) -> int | None:
    """Час на чорній плашці: знаходить плашку в зоні пошуку і читає всередині.

    На відміну від фіксованого ROI не залежить від точної позиції плашки в
    зоні — детекція прив'язується до самої плашки (найбільший темний компонент
    достатньої площі). Компоненти, що торкаються країв зони, відкидаються:
    плашка завжди лежить усередині зони з запасом, а темні смуги фону сторінки
    та сусідніх колонок перетинають зону наскрізь — і бувають БІЛЬШІ за плашку
    за площею (car_selection_ru_1_sf: нижня смуга фону 1.03× площі плашки).
    Немає плашки (BEFORE-варіант: у зоні лише фон) → None."""
    if img.size == 0:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    dark = (gray < _PLATE_DARK_THR).astype(np.uint8)
    count, _, stats, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    h, w = gray.shape
    best_area = 0
    best_box = None
    for i in range(1, count):
        x, y = stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP]
        bw, bh = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        area = stats[i, cv2.CC_STAT_AREA]
        if x == 0 or y == 0 or x + bw == w or y + bh == h:
            continue  # торкається краю зони — фон/рамка, не плашка
        if area >= _PLATE_MIN_AREA_FRAC * h * w and area > best_area:
            best_area, best_box = area, (x, y, bw, bh)
    if best_box is None:
        return None
    x, y, bw, bh = best_box
    dx, dy = int(bw * _PLATE_SHRINK_X), int(bh * _PLATE_SHRINK_Y)
    inner = img[y + dy:y + bh - dy, x + dx:x + bw - dx]
    if inner.size == 0:
        return None
    return read_time(inner)


def read_rank(img: np.ndarray) -> int | None:
    if img.size == 0:
        return None
    match = RANK_RE.search(read_text(img, "0123456789,."))
    return int(match[1] + match[2]) if match else None


def read_name(img: np.ndarray, channel: str = "gray", lang: str = "eng") -> str:
    """Назва авто/треку; може бути 2 рядки — psm 6.

    channel див. preprocess(): "min" лишає тільки білий текст (гасить кольорові
    написи на яскравому тлі), "max" — кольоровий.
    lang: "rus" для російських назв карт/треків (авто завжди "eng")."""
    if img.size == 0:
        return ""
    # rus — без whitelist (кириличний whitelist ламає LSTM); шум добирає fuzzy-матч
    whitelist = "" if lang == "rus" else NAME_CHARS
    return read_text(img, whitelist, psm=6, channel=channel, lang=lang)


# Цифри індикатора намальовані жирним КУРСИВОМ — tesseract (psm 10) на сирому
# нахилі читає їх ненадійно ("1"→нічого, "2"→"4"). Перед OCR розпрямляємо нахил
# зсувом по x; одне значення зсуву крихке (різні цифри оптимальні за різного
# нахилу), тож пробуємо кілька й голосуємо — як read_time голосує по каналах.
# 0.0 обов'язковий: деякі рендери "4" читаються ЛИШЕ без зсуву (будь-який
# додатковий нахил дає порожнечу — див. tests/test_captures_regression.py).
DIGIT_SHEARS = (0.0, 0.1, 0.2, 0.3)


def read_bright_digit(img: np.ndarray, threshold: int = 150) -> int | None:
    """Єдина яскраво-БІЛА цифра 1..5 на темному тлі (індикатор поточної гонки).

    Фіксований поріг по min-каналу, а не Otsu: у поточного номера всі канали
    близькі до 255 (високий min), тоді як тьмяні сірі майбутні номери лишаються
    нижче порога, а кольорові іконки прапорів (червоний/зелений) мають низький
    min і теж не проходять. Так у кропі залишається тільки поточна цифра.
    Otsu тут не годиться: він адаптивно підхоплює і тьмяні сусідні цифри.

    Курсив розпрямляється deshear-зсувом; результат — найчастіша цифра по
    кількох значеннях зсуву (стійко до похибки конкретного нахилу)."""
    if img.size == 0:
        return None
    gray = img.min(axis=2) if img.ndim == 3 else img
    gray = cv2.resize(gray, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)

    votes: list[int] = []
    h, w = binary.shape
    for shear in DIGIT_SHEARS:
        m = np.float32([[1, shear, 0], [0, 1, 0]])
        sheared = cv2.warpAffine(binary, m, (round(w + shear * h), h), borderValue=0)
        sheared = cv2.bitwise_not(sheared)  # tesseract: темний текст на білому
        text = _run_ocr(Image.fromarray(sheared), lang="eng", psm=10, whitelist="12345")
        match = re.search(r"[1-5]", text)
        if match:
            votes.append(int(match.group()))
    if not votes:
        return None
    return max(set(votes), key=votes.count)
