import os
import re
import shutil
import subprocess
import sys

import cv2
import numpy as np
import pytesseract
from PIL import Image

DEFAULT_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


def _bundled_tesseract() -> str:
    """Шлях до портативного Tesseract, що йде в комплекті з застосунком.

    Frozen-збірка: тека `tesseract/` поруч з exe (її кладе інсталятор).
    Запуск із вихідників: та сама портативна копія з `installer/tesseract/`,
    щоб і в розробці використовувати саме бандлений Tesseract, а не системний."""
    name = "tesseract.exe" if sys.platform == "win32" else "tesseract"
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.join(os.path.dirname(__file__), "..", "..", "installer")
    return os.path.normpath(os.path.join(base, "tesseract", name))


# Латиниця для англ. назв і авто. Російські назви читаються БЕЗ whitelist:
# tessedit_char_whitelist з багатобайтними кириличними символами ламає LSTM-движок
# tesseract (повертає "?"), тож для lang="rus" whitelist не передаємо (див. read_name).
NAME_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
TIME_RE = re.compile(r"(\d{1,2})\s*:\s*(\d{2})\s*[.,]\s*(\d{2,3})")  # {2,3}: OCR інколи губить цифру мс
RANK_RE = re.compile(r"(\d)\s*[,.]?\s*(\d{3})")  # [,.]? необов'язковий: OCR інколи губить кому в "4,045"


def configure_tesseract(path: str = "") -> bool:
    """Виставляє tesseract_cmd: явний шлях → бандл → PATH → типові локації. True, якщо знайдено."""
    candidates = [path] if path else []
    bundled = _bundled_tesseract()
    if bundled:
        candidates.append(bundled)
    which = shutil.which("tesseract")
    if which:
        candidates.append(which)
    candidates += DEFAULT_TESSERACT_PATHS

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            pytesseract.pytesseract.tesseract_cmd = candidate
            return True
    return False


_availability_cache: dict[str, bool] = {}


def is_available() -> bool:
    """Чи запускається поточний tesseract_cmd. Результат кешується на шлях.

    Власна перевірка замість pytesseract.get_tesseract_version(): та спавнить
    консольний процес без прихованого вікна, і у windowed-збірці на кожну
    перевірку блимає вікно консолі."""
    cmd = pytesseract.pytesseract.tesseract_cmd
    if cmd not in _availability_cache:
        _availability_cache[cmd] = _probe_tesseract(cmd)
    return _availability_cache[cmd]


def _probe_tesseract(cmd: str) -> bool:
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        return subprocess.run([cmd, "--version"], capture_output=True, timeout=10, **kwargs).returncode == 0
    except Exception:
        return False


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


def read_text(img: np.ndarray, whitelist: str = "", psm: int = 7, channel: str = "gray",
              lang: str = "eng") -> str:
    """lang: "eng" (латиниця/авто) або "rus" (кирилиця). whitelist="" — без обмеження
    символів (кириличні бейджі з логотипом краще читаються без whitelist)."""
    config = f"--oem 3 --psm {psm}"
    if whitelist:
        config += f" -c tessedit_char_whitelist={whitelist}"
    return pytesseract.image_to_string(preprocess(img, channel=channel),
                                       lang=lang, config=config).strip()


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
DIGIT_SHEARS = (0.1, 0.2, 0.3)


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

    config = "--oem 3 --psm 10 -c tessedit_char_whitelist=12345"
    votes: list[int] = []
    h, w = binary.shape
    for shear in DIGIT_SHEARS:
        m = np.float32([[1, shear, 0], [0, 1, 0]])
        sheared = cv2.warpAffine(binary, m, (round(w + shear * h), h), borderValue=0)
        sheared = cv2.bitwise_not(sheared)  # tesseract: темний текст на білому
        text = pytesseract.image_to_string(Image.fromarray(sheared), lang="eng", config=config)
        match = re.search(r"[1-5]", text)
        if match:
            votes.append(int(match.group()))
    if not votes:
        return None
    return max(set(votes), key=votes.count)
