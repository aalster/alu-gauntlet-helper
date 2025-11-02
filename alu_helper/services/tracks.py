from alu_helper.database import connect
from alu_helper.models import TrackAddModel
from pydantic import BaseModel

from alu_helper.services.maps import MapsService


class Track(BaseModel):
    id: int
    map_id: int
    name: str

class TracksRepository:
    @staticmethod
    def parse(row):
        return Track(**row) if row else None

    def add(self, model: TrackAddModel):
        with connect() as conn:
            conn.execute("INSERT INTO tracks (map_id, name) VALUES (:map_id, :name)", model.model_dump())

    def get_all(self):
        with connect() as conn:
            rows = conn.execute("SELECT * FROM tracks ORDER BY name").fetchall()
            return [self.parse(row) for row in rows]

class TracksService:
    def __init__(self, repo: TracksRepository, maps: MapsService):
        self.repo = repo
        self.maps = maps

    def add(self, model: TrackAddModel):
        if model.map_id <= 0:
            model.map_id = self.maps.get_or_add(model.map_name)
        self.repo.add(model)

    def get_all(self) -> list[Track]:
        return self.repo.get_all()