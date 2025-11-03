from pydantic import BaseModel

from alu_helper.database import connect
from alu_helper.services.cars import CarsService, Car
from alu_helper.services.tracks import TracksService, TrackView


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
        cars = self.cars.get_by_ids({i.car_id for i in items})
        result = []
        for i in items:
            track = tracks.get(i.track_id)
            car = cars.get(i.car_id)
            result.append(RaceView(
                **i.model_dump(),
                map_name=track.map_name if track else "Unknown Map",
                track_name=track.name if track else "Unknown Track",
                car_name=car.name if car else "Unknown Car"
            ))
        return result

    def get_all(self) -> list[RaceView]:
        return self.to_views(self.repo.get_all())

    def save(self, item: RaceView):
        if item.track_id <= 0:
            item.track_id = self.tracks.save(TrackView(name=item.track_name, map_name=item.map_name))
        if item.car_id <= 0:
            item.car_id = self.cars.save(Car(name=item.car_name, rank=item.rank), False)

        if item.id <= 0:
            self.repo.add(item)
        else:
            self.repo.update(item)