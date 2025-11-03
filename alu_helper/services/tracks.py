from alu_helper.database import connect
from pydantic import BaseModel

from alu_helper.services.maps import MapsService


class Track(BaseModel):
    id: int
    map_id: int
    name: str

class TrackView(Track):
    map_name: str

class TracksRepository:
    @staticmethod
    def parse(row):
        return Track(**row) if row else None

    def add(self, item: Track):
        with connect() as conn:
            return conn.execute("INSERT INTO tracks (map_id, name) VALUES (:map_id, :name)", item.model_dump()).lastrowid

    def get_by_name(self, map_id: int, name: str):
        with connect() as conn:
            row = conn.execute("SELECT * FROM tracks WHERE map_id = :map_id AND name = :name LIMIT 1",
                               {"map_id": map_id, "name": name}).fetchone()
            return self.parse(row)

    def get_by_ids(self, ids):
        ids_str = ", ".join(str(id) for id in ids)

        with connect() as conn:
            rows = conn.execute(f"SELECT * FROM tracks WHERE id in ({ids_str})").fetchall()
            return [self.parse(row) for row in rows]

    def autocomplete(self, query: str):
        with (connect() as conn):
            sql = "SELECT t.* FROM tracks t LEFT JOIN maps m ON t.map_id = m.id"
            params = {}

            if query:
                sql += " WHERE t.name LIKE :query OR m.name LIKE :query"
                params = {"query": f"%{query}%"}

            rows = conn.execute(sql + " ORDER BY t.name LIMIT 100", params).fetchall()
            return [self.parse(row) for row in rows]

    def update(self, item: Track):
        with connect() as conn:
            conn.execute("UPDATE tracks SET map_id = :map_id, name = :name WHERE id = :id", item.model_dump())

class TracksService:
    def __init__(self, repo: TracksRepository, maps: MapsService):
        self.repo = repo
        self.maps = maps

    def to_views(self, items: list[Track]):
        maps_ids = {t.map_id for t in items}
        maps = self.maps.get_by_ids(maps_ids)
        result = []
        for i in items:
            map_ = maps[i.map_id]
            result.append(TrackView(
                **i.model_dump(),
                map_name=map_.map_name if map_ else "Unknown Map"
            ))
        return result

    def get_by_ids(self, ids: set[int]) -> dict[int, TrackView]:
        if not ids:
            return dict()
        items = self.to_views(self.repo.get_by_ids(ids))
        return {i.id: i for i in items}

    def autocomplete(self, query: str) -> list[TrackView]:
        return self.to_views(self.repo.autocomplete(query.strip()))

    def add(self, item: TrackView) -> int:
        return self.save_by_name(item.name, item.map_name)

    def save_by_name(self, name, map_name) -> int:
        map_id = self.maps.save_by_name(map_name)
        existing = self.repo.get_by_name(map_id, name)
        if existing:
            return existing.id
        return self.repo.add(Track(id=0, map_id=map_id, name=name))

    def update(self, item: Track):
        self.repo.update(item)