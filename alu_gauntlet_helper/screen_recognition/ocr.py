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


def preprocess(img: np.ndarray, scale: int = 3, max_channel: bool = False) -> Image.Image:
    """Кроп ROI → сірий → апскейл → Otsu → темний текст на білому.

    max_channel=True: замість звичайного сірого береться max(B,G,R) попіксельно —
    червоний текст (програна гонка) у сірому зливається з темною плашкою,
    а в max-каналі лишається яскравим."""
    gray = img.max(axis=2) if max_channel and img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if binary.mean() < 127:
        binary = cv2.bitwise_not(binary)
    return Image.fromarray(binary)


def read_text(img: np.ndarray, whitelist: str, psm: int = 7, max_channel: bool = False) -> str:
    config = f"--oem 3 --psm {psm} -c tessedit_char_whitelist={whitelist}"
    return pytesseract.image_to_string(preprocess(img, max_channel=max_channel),
                                       lang="eng", config=config).strip()


def read_time(img: np.ndarray) -> int | None:
    if img.size == 0:
        return None
    match = TIME_RE.search(read_text(img, "0123456789:.,"))
    if not match:
        # фолбек для червоного часу програної гонки (див. preprocess max_channel)
        match = TIME_RE.search(read_text(img, "0123456789:.,", max_channel=True))
    if not match:
        return None
    minutes, seconds = int(match[1]), int(match[2])
    millis = int(match[3][:3].ljust(3, "0"))
    return (minutes * 60 + seconds) * 1000 + millis


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
