from alu_helper.database import connect
from pydantic import BaseModel

from alu_helper.models import PageResult


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
            # conn.execute("""
            #              INSERT INTO maps (name) VALUES (:name)
            #              ON CONFLICT (name) DO NOTHING
            #              RETURNING id
            #              """, {"name": name}).fetchone()[0]


    def get(self, name: str):
        with connect() as conn:
            row = conn.execute("SELECT * FROM maps WHERE name = :name", {"name": name}).fetchone()
            return self.parse(row)

    def get_all(self, query: str):
        with (connect() as conn):
            sql = "SELECT * FROM maps"
            params = {}

            if query:
                sql += " WHERE name LIKE :query"
                params = {"query": f"%{query}%"}

            rows = conn.execute(sql + " ORDER BY name LIMIT 100", params).fetchall()
            return [self.parse(row) for row in rows]

            # total = conn.execute("SELECT COUNT(*) FROM maps").fetchone()[0]
            #
            # return PageResult(
            #     items=[self.parse(row) for row in rows],
            #     total=total
            # )

    def update(self, item: Map):
        with connect() as conn:
            conn.execute("UPDATE maps SET name = :name WHERE id = :id", item.model_dump())


class MapsService:
    def __init__(self, repo: MapsRepository):
        self.repo = repo

    def add(self, item: Map) -> int:
        return self.repo.add(item)

    def get_or_add(self, map_name: str) -> int:
        return self.add(Map(id=0, name=map_name))

    def get_all(self, query: str):
        return self.repo.get_all(query)

    def update(self, item: Map):
        self.repo.update(item)
