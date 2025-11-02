from typing import Generic, TypeVar
from pydantic import BaseModel
from pydantic.generics import GenericModel

T = TypeVar("T")


class PageResult(GenericModel, Generic[T]):
    items: list[T]
    total: int


class TrackEditModel(BaseModel):
    id: int
    map_id: int
    map_name: str
    name: str


class RaceAddModel(BaseModel):
    track_id: int
    car_id: int
    rank: int
    time: int
