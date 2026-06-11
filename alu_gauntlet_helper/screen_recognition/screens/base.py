import re
from abc import ABC, abstractmethod

import cv2
import numpy as np

from alu_gauntlet_helper.models import RaceCapture

# Якір "RACE N" — спільний для екранів, що ідентифікуються заголовком гонки.
RACE_HEADER_RE = re.compile(r"RACE\s*([1-5])")

# Скан невеликих вертикальних зсувів — стійкість до інших співвідношень сторін
# і відмінностей лейауту між пристроями.
HEADER_DY_OFFSETS = [0.0, -0.03, 0.03]


def encode_png(img: np.ndarray) -> bytes | None:
    ok, buffer = cv2.imencode(".png", img)
    return buffer.tobytes() if ok else None


class ScreenExtractor(ABC):
    """Розпізнавач одного типу екрана гри."""

    name: str = ""

    @abstractmethod
    def extract(self, img: np.ndarray) -> list[RaceCapture]:
        """Повертає захоплені гонки або [] якщо це не той екран / нічого не зчиталось."""
