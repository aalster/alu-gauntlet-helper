from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int

class FieldGuess(BaseModel):
    """Розпізнане значення-довідник: id + впевненість + альтернативи."""
    value: int
    score: float
    candidates: list[tuple[int, float]] = []


class RaceCapture(BaseModel):
    """Часткові дані однієї гонки, витягнуті з одного скріншота."""
    race_number: int  # 1..5
    track: FieldGuess | None = None
    car: FieldGuess | None = None
    rank: int | None = None
    time: int | None = None  # мс, як Race.time
    source_screen: str = ""
    panel_image: bytes | None = None  # PNG-кроп панелі-джерела для рев'ю
    game_language: str | None = None  # "en"/"ru" — мова, визначена з якоря екрана


class RecognitionResult(BaseModel):
    screen: str
    captures: list[RaceCapture] = []
    game_language: str | None = None  # мова гри, визначена з цього скріншота
