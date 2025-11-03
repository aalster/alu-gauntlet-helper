from alu_helper.database import connect
from pydantic import BaseModel


class Map(BaseModel):
    id: int
    name: str

class MapsRepository:
    @staticmethod
    def parse(row):
        return Map(**row) if row else None

    def add(self, item: Map) -> int:
        with connect() as conn:
            return conn.execute("INSERT INTO maps (name) VALUES (:name)", item.model_dump()).lastrowid

    def get_by_name(self, name: str):
        with connect() as conn:
            row = conn.execute("SELECT * FROM maps WHERE name = :name LIMIT 1", {"name": name}).fetchone()
            return self.parse(row)

    def get_all(self, query: str):
        with connect() as conn:
            sql = "SELECT * FROM maps"
            params = {}

            if query:
                sql += " WHERE name LIKE :query"
                params = {"query": f"%{query}%"}

            rows = conn.execute(sql + " ORDER BY name LIMIT 100", params).fetchall()
            return [self.parse(row) for row in rows]

    def update(self, item: Map):
        with connect() as conn:
            conn.execute("UPDATE maps SET name = :name WHERE id = :id", item.model_dump())

    def get_by_ids(self, ids):
        ids_str = ", ".join(str(id) for id in ids)

        with connect() as conn:
            rows = conn.execute(f"SELECT * FROM maps WHERE id in ({ids_str})").fetchall()
            return [self.parse(row) for row in rows]


class MapsService:
    def __init__(self, repo: MapsRepository):
        self.repo = repo

    def get_by_name(self, name: str) -> Map:
        return self.repo.get_by_name(name)

    def autocomplete(self, query: str):
        return self.repo.get_all(query.strip())

    def get_by_ids(self, ids: set[int]) -> dict[int, Map]:
        if not ids:
            return dict()
        items = self.repo.get_by_ids(ids)
        return {m.id: m for m in items}

    def add(self, item: Map) -> int:
        return self.save_by_name(item.name)

    def save_by_name(self, name: str) -> int:
        existing = self.get_by_name(name)
        if existing:
            return existing.id
        return self.repo.add(Map(id=0, name=name))

    def update(self, item: Map):
        self.repo.update(item)
