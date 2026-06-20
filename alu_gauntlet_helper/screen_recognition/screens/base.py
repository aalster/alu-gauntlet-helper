import re
from abc import ABC, abstractmethod

import cv2
import numpy as np

from alu_gauntlet_helper.models import RaceCapture
from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.regions import RelRect

# Якір "RACE N" — спільний для екранів, що ідентифікуються заголовком гонки.
RACE_HEADER_RE = re.compile(r"RACE\s*([1-5])")

# Скан невеликих вертикальних зсувів — стійкість до інших співвідношень сторін
# і відмінностей лейауту між пристроями.
HEADER_DY_OFFSETS = [0.0, -0.03, 0.03]

# Російський бейдж "ГОНКА N". 'Г' часто зливається з рамкою/логотипом ліворуч,
# тож якоримось на хвіст слова "ОНКА"; whitelist кирилицю ламає (логотип
# форситься в цифру), тому читаємо без нього й шукаємо регексом.
_RU_HEADER_WORD_RE = re.compile(r"ОНКА")
# Цифру беремо ВПРИТУЛ після "ОНКА" (лише пробіли між ними): на низькоякісних
# кадрах курсивна цифра злипається зі словом і читається як кирилична літера-
# двійник (напр. "3"→"З" у "ГОНКАЗ"). Старий "\D{0,3}" трактував цей двійник як
# пропускний нецифровий символ і захоплював натомість дальший декор, що читається
# як "11" → хибна "1". Тож двійники теж у групі захоплення й мапляться на цифру.
# Курсивна "1" стабільно читається як "7" (гонок 7 немає, мапимо назад).
_RU_HEADER_NUM_RE = re.compile(r"ОНКА\s*([1-7Зз])")
_RU_DIGIT_FIX = {"6": "", "7": "1", "З": "3", "з": "3"}
# Логотип зліва має різну ширину на різних бейджах; курсивна цифра відділяється
# від слова лише після обрізання логотипа — пробуємо кілька обрізань.
_RU_HEADER_TRIMS = (0.0, 0.22, 0.30)
# "min" глушить кольоровий логотип, "max" витягує яскраву курсивну цифру.
_RU_HEADER_CHANNELS = ("min", "max", "gray")


def _ru_word_present(img: np.ndarray, region: RelRect) -> bool:
    """Дешевий гейт перед дорогим пошуком цифри: чи є на бейджі слово "ГОНКА".
    min глушить кольоровий логотип бейджа, max ловить білий логотип race_result.
    Логотип на деяких бейджах зливається зі словом — пробуємо й обрізаний варіант,
    інакше частина рядків проскакує (напр. рядок 3 на підсумковому екрані)."""
    for trim in (0.0, 0.30):
        sub = region.sub(RelRect(trim, 0.0, 1 - trim, 1.0)) if trim else region
        for channel in ("min", "max"):
            if _RU_HEADER_WORD_RE.search(ocr.read_text(sub.crop(img), channel=channel, lang="rus")):
                return True
    return False


def _ru_header_number(img: np.ndarray, region: RelRect) -> int | None:
    """Номер з російського бейджа. Рівно одна цифра на всіх спробах — інакше None
    (кілька різних означає, що кроп накрив сусідні бейджі — як у англ. варіанті)."""
    found: set[str] = set()
    for trim in _RU_HEADER_TRIMS:
        sub = region.sub(RelRect(trim, 0.0, 1 - trim, 1.0)) if trim else region
        for channel in _RU_HEADER_CHANNELS:
            match = _RU_HEADER_NUM_RE.search(ocr.read_text(sub.crop(img), channel=channel, lang="rus"))
            if match:
                digit = _RU_DIGIT_FIX.get(match.group(1), match.group(1))
                if digit:
                    found.add(digit)
    return int(next(iter(found))) if len(found) == 1 else None


def read_race_header(img: np.ndarray, region: RelRect) -> tuple[int | None, str | None]:
    """Бейдж "RACE N" / "ГОНКА N" в одній позиції → (номер|None, мова|None).

    Спершу англійський whitelist-шлях (дешевий, надійний). Якщо слова RACE немає —
    російський шлях (логотип і курсивна цифра вимагають кількох обрізань/каналів).
    Повертає мову навіть коли номер не зчитався — для авто-перемикання мови гри.
    Скан dy-зсувів — на боці викликача (йому потрібна dy й для решти геометрії).
    """
    text = ocr.read_text(region.crop(img), "RACE12345")
    numbers = set(RACE_HEADER_RE.findall(text))
    if len(numbers) == 1:
        return int(next(iter(numbers))), "en"
    if numbers:
        return None, None  # кілька різних номерів → кроп накрив кілька бейджів
    if _ru_word_present(img, region):
        return _ru_header_number(img, region), "ru"
    return None, None


def encode_png(img: np.ndarray) -> bytes | None:
    ok, buffer = cv2.imencode(".png", img)
    return buffer.tobytes() if ok else None


class ScreenExtractor(ABC):
    """Розпізнавач одного типу екрана гри."""

    name: str = ""

    @abstractmethod
    def extract(self, img: np.ndarray) -> list[RaceCapture]:
        """Повертає захоплені гонки або [] якщо це не той екран / нічого не зчиталось."""
