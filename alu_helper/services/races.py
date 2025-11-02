from alu_helper.database import connect
from alu_helper.gui_models import TrackAddModel, RaceAddModel
from pydantic import BaseModel

from alu_helper.maps import MapsService


class Race(BaseModel):
    id: int
    track_id: int
    car_id: int
    rank: int
    time: int
    created_at: str

class RacesRepository:
    @staticmethod
    def parse(row):
        return Race(**row) if row else None

    def add(self, model: RaceAddModel):
        with connect() as conn:
            conn.execute("INSERT INTO races (track_id, car_id, rank, time) VALUES (:track_id, :car_id, :rank, :time)", model.model_dump())

    def get_all(self):
        with connect() as conn:
            rows = conn.execute("SELECT * FROM races ORDER BY created_at DESC").fetchall()
            return [self.parse(row) for row in rows]

class RacesService:
    def __init__(self, repo: RacesRepository):
        self.repo = repo

    def add(self, model: RaceAddModel):
        self.repo.add(model)

    def get_all(self) -> list[Race]:
        return self.repo.get_all()