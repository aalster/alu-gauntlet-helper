from typing import Generic, TypeVar
from pydantic import BaseModel
from pydantic.generics import GenericModel

T = TypeVar("T")


class PageResult(GenericModel, Generic[T]):
    items: list[T]
    total: int

class RaceAddModel(BaseModel):
    track_id: int
    car_id: int
    rank: int
    time: int
