from pydantic import BaseModel

from alu_helper.database import connect
from alu_helper.services.cars import CarsService
from alu_helper.services.tracks import TracksService


class Race(BaseModel):
    id: int = 0
    track_id: int = 0
    car_id: int = 0
    rank: int = 0
    time: int = 0
    created_at: str = ""

class RaceView(Race):
    map_name: str = ""
    track_name: str = ""
    car_name: str = ""


class RacesRepository:
    @staticmethod
    def parse(row):
        return Race(**row) if row else None

    def add(self, item: Race):
        with connect() as conn:
            conn.execute("INSERT INTO races (track_id, car_id, `rank`, time) VALUES (:track_id, :car_id, :rank, :time)",
                         item.model_dump())

    def get_all(self):
        with connect() as conn:
            rows = conn.execute("SELECT * FROM races ORDER BY created_at DESC LIMIT 100").fetchall()
            return [self.parse(row) for row in rows]

    def update(self, item: Race):
        with connect() as conn:
            conn.execute("UPDATE races SET track_id = :track_id, car_id = :car_id, `rank` = :rank, time = :time"
                         " WHERE id = :id", item.model_dump())

class RacesService:
    def __init__(self, repo: RacesRepository, tracks: TracksService, cars: CarsService):
        self.repo = repo
        self.tracks = tracks
        self.cars = cars

    def to_views(self, items: list[Race]):
        tracks = self.tracks.get_by_ids({i.track_id for i in items})
        cars = self.cars.get_by_ids({i.track_id for i in items})
        result = []
        for i in items:
            track = tracks[i.track_id]
            car = cars[i.car_id]
            result.append(RaceView(
                **i.model_dump(),
                map_name=track.map_name if track else "Unknown Map",
                track_name=track.name if track else "Unknown Track",
                car_name=car.name if car else "Unknown Car"
            ))
        return result

    def get_all(self) -> list[Race]:
        return self.repo.get_all()

    def add(self, item: RaceView):
        if item.track_id <= 0:
            item.track_id = self.tracks.save_by_name(item.track_name, item.map_name)
        self.repo.add(item)

    def update(self, item: RaceView):
        self.repo.update(item)