from abc import ABC, abstractmethod

import numpy as np

from alu_gauntlet_helper.models import RaceCapture


class ScreenExtractor(ABC):
    """Розпізнавач одного типу екрана гри."""

    name: str = ""

    @abstractmethod
    def extract(self, img: np.ndarray) -> list[RaceCapture]:
        """Повертає захоплені гонки або [] якщо це не той екран / нічого не зчиталось."""
