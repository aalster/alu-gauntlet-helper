from alu_helper.database import connect
from alu_helper.models import TrackEditModel
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

    def add(self, model: TrackEditModel):
        with connect() as conn:
            conn.execute("INSERT INTO tracks (map_id, name) VALUES (:map_id, :name)", model.model_dump())

    def get_all(self, query: str):
        with (connect() as conn):
            sql = "SELECT * FROM tracks"
            params = {}

            if query:
                sql += " WHERE name LIKE :query"
                params = {"query": f"%{query}%"}

            rows = conn.execute(sql + " ORDER BY name LIMIT 100", params).fetchall()
            return [self.parse(row) for row in rows]

    def update(self, item: Track):
        with connect() as conn:
            conn.execute("UPDATE tracks SET map_id = :map_id, name = :name WHERE id = :id", item.model_dump())

class TracksService:
    def __init__(self, repo: TracksRepository, maps: MapsService):
        self.repo = repo
        self.maps = maps

    def add(self, model: TrackEditModel):
        if model.map_id <= 0:
            model.map_id = self.maps.get_id_by_name(model.map_name)
        self.repo.add(model)

    def update(self, item: Track):
        self.repo.update(item)

    def get_all(self, query: str = "") -> list[Track]:
        return self.repo.get_all(query.strip())