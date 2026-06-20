"""ЕКСПЕРИМЕНТАЛЬНИЙ швидкий читач бейджа гонки "RACE N" / "ГОНКА N".

Демонструє пункти B2+B3+B4 з docs/optimizing-recognition-speed.md, не змінюючи
наявний base.read_race_header.

Наявний шлях для RU-бейджа: 1 (англ.) + до 4 (гейт слова "ГОНКА") + 9 (пошук
цифри, БЕЗ раннього виходу) = до 14 запусків tesseract на ОДИН бейдж.

Тут:
  B2 — дешевий гейт: спершу одне англ. читання (whitelist "RACE12345"). Якщо
       "RACE N" знайдено — готово (1 виклик). Інакше ОДНЕ кириличне читання на
       дефолтному каналі — чи є "ОНКА" і цифра поруч.
  B3 — ранній вихід: щойно знайдено впевнену цифру — повертаємо, не проганяючи
       решту каналів/обрізань.
  B4 — скорочена сітка: до резерву (2 канали × 2 обрізання) доходимо лише коли
       дешеве читання дало слово, але не дало цифри.
"""
import re

import numpy as np

from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.regions import RelRect

_RACE_RE = re.compile(r"RACE\s*([1-5])")
_RU_WORD_RE = re.compile(r"ОНКА")
_RU_NUM_RE = re.compile(r"ОНКА\D{0,3}([1-7])")
_RU_DIGIT_FIX = {"6": "", "7": "1"}  # курсивна "1" читається як "7"; "6" — шум

# Дешевий RU-прохід: ті самі канали, що й гейт слова в наявному base (min глушить
# кольоровий логотип, max витягує білий), але з раннім виходом на першу валідну
# цифру (B3). Безпечно для race_result/complete — там у кропі рівно один бейдж.
_CHEAP_CHANNELS = ("min", "max")
# Резерв, коли слово знайшли, а цифру — ні (B4: вужча сітка, ніж 3×3 у наявному base).
_FALLBACK_TRIMS = (0.22, 0.30)


def _ru_digit(text: str) -> int | None:
    match = _RU_NUM_RE.search(text)
    if not match:
        return None
    digit = _RU_DIGIT_FIX.get(match.group(1), match.group(1))
    return int(digit) if digit else None


def read_race_header_fast(img: np.ndarray, region: RelRect) -> tuple[int | None, str | None]:
    """(номер|None, мова|None). Дешевий шлях спершу, дорогий резерв — лише за потреби."""
    # B2: англійський whitelist-шлях (дешевий, надійний).
    text = ocr.read_text(region.crop(img), "RACE12345")
    numbers = set(_RACE_RE.findall(text))
    if len(numbers) == 1:
        return int(next(iter(numbers))), "en"
    if numbers:
        return None, None  # кілька різних → кроп накрив кілька бейджів

    # B2/B3: кириличне читання на min/max каналах, ранній вихід на першу цифру.
    crop = region.crop(img)
    word_seen = False
    for channel in _CHEAP_CHANNELS:
        cheap = ocr.read_text(crop, channel=channel, lang="rus")
        if _RU_WORD_RE.search(cheap):
            word_seen = True
            digit = _ru_digit(cheap)
            if digit is not None:
                return digit, "ru"  # B3: ранній вихід
    if not word_seen:
        return None, None  # дешевий гейт: слова "ГОНКА" немає → не наш бейдж

    # Слово є, цифри немає — B4: вужчий резерв (2 обрізання × 2 канали).
    found: set[int] = set()
    for trim in _FALLBACK_TRIMS:
        sub = region.sub(RelRect(trim, 0.0, 1 - trim, 1.0))
        for channel in _CHEAP_CHANNELS:
            digit = _ru_digit(ocr.read_text(sub.crop(img), channel=channel, lang="rus"))
            if digit is not None:
                found.add(digit)
    # рівно одна унікальна цифра — інакше ненадійно
    return (next(iter(found)) if len(found) == 1 else None), "ru"
