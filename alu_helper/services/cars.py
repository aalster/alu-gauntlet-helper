from alu_helper.database import connect
from pydantic import BaseModel


class Car(BaseModel):
    id: int
    name: str
    rank: int

class CarsRepository:
    @staticmethod
    def parse(row):
        return Car(**row) if row else None

    def add(self, item: Car) -> int:
        with connect() as conn:
            return conn.execute("INSERT INTO cars(name, `rank`) VALUES (:name, :rank)", item.model_dump()).lastrowid


    def get_by_name(self, name: str):
        with connect() as conn:
            row = conn.execute("SELECT * FROM cars WHERE name = :name LIMIT 1", {"name": name}).fetchone()
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

    def update(self, item: Car):
        with connect() as conn:
            conn.execute("UPDATE cars SET name = :name, `rank` = :rank WHERE id = :id", item.model_dump())

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

    def add(self, item: Car) -> int:
        return self.save_by_name(item.name, item.rank)

    def save_by_name(self, name: str, rank: int) -> int:
        existing = self.repo.get_by_name(name)
        if existing:
            if rank > 0 and existing.rank < rank:
                existing.rank = rank
                self.repo.update(existing)
            return existing.id
        return self.repo.add(Car(id=0, name=name, rank=rank))

    def update(self, item: Car):
        self.repo.update(item)