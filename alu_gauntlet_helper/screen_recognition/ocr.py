import os
import re
import shutil

import cv2
import numpy as np
import pytesseract
from PIL import Image

DEFAULT_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]

NAME_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
TIME_RE = re.compile(r"(\d{1,2})\s*:\s*(\d{2})\s*[.,]\s*(\d{2,3})")  # {2,3}: OCR інколи губить цифру мс
RANK_RE = re.compile(r"(\d)\s*[,.]?\s*(\d{3})")  # [,.]? необов'язковий: OCR інколи губить кому в "4,045"


def configure_tesseract(path: str = "") -> bool:
    """Виставляє tesseract_cmd: явний шлях → PATH → типові локації. True, якщо знайдено."""
    candidates = [path] if path else []
    which = shutil.which("tesseract")
    if which:
        candidates.append(which)
    candidates += DEFAULT_TESSERACT_PATHS

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            pytesseract.pytesseract.tesseract_cmd = candidate
            return True
    return False


def is_available() -> bool:
    try:
        pytesseract.get_tesseract_version()
        return True
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


def read_text(img: np.ndarray, whitelist: str, psm: int = 7, channel: str = "gray") -> str:
    config = f"--oem 3 --psm {psm} -c tessedit_char_whitelist={whitelist}"
    return pytesseract.image_to_string(preprocess(img, channel=channel),
                                       lang="eng", config=config).strip()


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


def read_name(img: np.ndarray) -> str:
    """Назва авто/треку; може бути 2 рядки — psm 6."""
    if img.size == 0:
        return ""
    return read_text(img, NAME_CHARS, psm=6)
