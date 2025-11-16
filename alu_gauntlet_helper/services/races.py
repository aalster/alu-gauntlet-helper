from datetime import datetime

from pydantic import BaseModel, validator, field_validator

from alu_gauntlet_helper.database import connect
from alu_gauntlet_helper.services.cars import CarsService, Car
from alu_gauntlet_helper.services.tracks import TracksService, TrackView


class Race(BaseModel):
    id: int = 0
    track_id: int = 0
    car_id: int = 0
    rank: int = 0
    time: int = 0
    created_at: datetime | None = None

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v)
            except ValueError:
                return None
        return v

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

    def get_all(self, track_query: str, car_query: str):
        with (connect() as conn):
            sql = ("SELECT r.* FROM races r"
                   " LEFT JOIN tracks t ON r.track_id = t.id"
                   " LEFT JOIN maps m ON t.map_id = m.id"
                   " LEFT JOIN cars c ON r.car_id = c.id")
            params = {}

            if track_query:
                sql += " WHERE t.name LIKE :track_query OR m.name LIKE :track_query"
                params = {"track_query": f"%{track_query}%"}

            if car_query:
                sql += " WHERE c.name LIKE :car_query"
                params = {"car_query": f"%{car_query}%"}

            rows = conn.execute(sql + " ORDER BY r.created_at LIMIT 100", params).fetchall()
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

    def get_all(self, track_query: str, car_query: str) -> list[RaceView]:
        return self.to_views(self.repo.get_all(track_query, car_query))

    def save(self, item: RaceView):
        if item.track_id <= 0:
            item.track_id = self.tracks.save(TrackView(name=item.track_name, map_name=item.map_name))
        if item.car_id <= 0 or item.rank > 0:
            item.car_id = self.cars.save(Car(name=item.car_name, rank=item.rank), False)

        if item.id <= 0:
            self.repo.add(item)
        else:
            self.repo.update(item)