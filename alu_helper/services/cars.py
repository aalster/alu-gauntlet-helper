from alu_helper.database import connect
from pydantic import BaseModel


class Car(BaseModel):
    id: int = 0
    name: str = ""
    rank: int = 0

class CarsRepository:
    @staticmethod
    def parse(row):
        return Car(**row) if row else None

    def add(self, item: Car) -> int:
        with connect() as conn:
            return conn.execute("INSERT INTO cars(name, `rank`) VALUES (:name, :rank)", item.model_dump()).lastrowid


    def get_by_name(self, name: str):
        with connect() as conn:
            row = conn.execute("SELECT * FROM cars WHERE name = :name COLLATE NOCASE LIMIT 1", {"name": name}).fetchone()
            return self.parse(row)

    def autocomplete(self, query: str):
        with connect() as conn:
            sql = "SELECT * FROM cars"
            params = {}

            if query:
                sql += " WHERE name LIKE :query"
                params = {"query": f"%{query}%"}

            rows = conn.execute(sql + " ORDER BY `rank` DESC, name LIMIT 100", params).fetchall()
            return [self.parse(row) for row in rows]

    def update(self, item: Car, update_empty_rank):
        with connect() as conn:
            rank_update = ", `rank` = :rank" if update_empty_rank or item.rank > 0 else ""
            conn.execute(f"UPDATE cars SET name = :name {rank_update} WHERE id = :id", item.model_dump())

    def get_by_ids(self, ids):
        ids_str = ", ".join(str(id) for id in ids)

        with connect() as conn:
            rows = conn.execute(f"SELECT * FROM cars WHERE id in ({ids_str})").fetchall()
            return [self.parse(row) for row in rows]


class CarsService:
    def __init__(self, repo: CarsRepository):
        self.repo = repo

    def autocomplete(self, query: str = ""):
        return self.repo.autocomplete(query.strip())

    def get_by_ids(self, ids: set[int]) -> dict[int, Car]:
        if not ids:
            return dict()
        items = self.repo.get_by_ids(ids)
        return {i.id: i for i in items}

    def save(self, item: Car, update_empty_rank = True) -> int:
        if item.id <= 0:
            existing = self.repo.get_by_name(item.name)
            if not existing:
                return self.repo.add(item)
            item.id = existing.id

        self.repo.update(item, update_empty_rank)
        return item.id