import os

from alu_gauntlet_helper.database import connect
from alu_gauntlet_helper.services.observable import Observable
from alu_gauntlet_helper.utils.utils import copy_resource_to_data, DATA_PATH_CARS
from pydantic import BaseModel


class Car(BaseModel):
    id: int = 0
    asec_id: int = 0
    name: str = ""
    brand: str = ""
    model: str = ""
    car_class: str = ""
    rank: int = 0
    max_rank: int = 0
    favorite: bool = False
    icon: str = ""

# Names from the old hardcoded seed list that differ from asec.tools naming,
# used to link pre-existing DB rows to asec entries instead of creating duplicates
LEGACY_NAMES = {
    "Ferrari FXX K": "Ferrari FXX-K",
    "Faraday Future FFZero1": "Faraday FFZERO1",
    "Inferno Automobili Settimo Cerchio": "Inferno Settimo Cerchio",
    "W Motors Lykan Neon Edition": "W Motors Lykan Neon",
}

class CarsRepository:
    @staticmethod
    def parse(row):
        return Car(**row) if row else None

    def add(self, item: Car) -> int:
        with connect() as conn:
            return conn.execute(
                "INSERT INTO cars(asec_id, name, brand, model, car_class, `rank`, max_rank, favorite, icon)"
                " VALUES (:asec_id, :name, :brand, :model, :car_class, :rank, :max_rank, :favorite, :icon)",
                item.model_dump()).lastrowid


    def get_by_name(self, name: str):
        with connect() as conn:
            row = conn.execute("SELECT * FROM cars WHERE name = :name COLLATE NOCASE LIMIT 1", {"name": name}).fetchone()
            return self.parse(row)

    def get_by_asec_id(self, asec_id: int):
        with connect() as conn:
            row = conn.execute("SELECT * FROM cars WHERE asec_id = :asec_id LIMIT 1", {"asec_id": asec_id}).fetchone()
            return self.parse(row)

    LIMIT = 100

    @staticmethod
    def _build_filter(query: str, car_class: str):
        conditions = []
        params = {}

        if query:
            conditions.append("lower_u(name) LIKE :query")
            params["query"] = f"%{query.lower()}%"

        if car_class:
            conditions.append("car_class = :car_class")
            params["car_class"] = car_class

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        return where, params

    def autocomplete(self, query: str, by_max_rank: bool = False, car_class: str = ""):
        with connect() as conn:
            where, params = self._build_filter(query, car_class)
            sql = "SELECT * FROM cars" + where

            if by_max_rank:
                sql += f" ORDER BY max_rank DESC, name LIMIT {self.LIMIT}"
            else:
                sql += (" ORDER BY favorite DESC,"
                        " CASE WHEN `rank` > 0 THEN `rank` ELSE max_rank END DESC,"
                        f" name LIMIT {self.LIMIT}")
            rows = conn.execute(sql, params).fetchall()
            return [self.parse(row) for row in rows]

    def count(self, query: str, car_class: str = "") -> int:
        with connect() as conn:
            where, params = self._build_filter(query, car_class)
            return conn.execute("SELECT COUNT(*) FROM cars" + where, params).fetchone()[0]

    def update(self, item: Car, update_empty_rank):
        with connect() as conn:
            rank_update = ", `rank` = :rank" if update_empty_rank or item.rank > 0 else ""
            conn.execute(f"UPDATE cars SET asec_id = :asec_id, name = :name, brand = :brand, model = :model,"
                         f" car_class = :car_class, max_rank = :max_rank, favorite = :favorite, icon = :icon {rank_update}"
                         f" WHERE id = :id", item.model_dump())

    def toggle_favorite(self, car_id: int):
        with connect() as conn:
            conn.execute("UPDATE cars SET favorite = 1 - favorite WHERE id = :id", {"id": car_id})

    def update_rank(self, car_id: int, rank: int):
        with connect() as conn:
            conn.execute("UPDATE cars SET `rank` = :rank WHERE id = :id", {"id": car_id, "rank": rank})

    def get_by_ids(self, ids: list[int]) -> list[Car]:
        if not ids:
            return []
        placeholders = ", ".join("?" * len(ids))
        with connect() as conn:
            rows = conn.execute(f"SELECT * FROM cars WHERE id IN ({placeholders})", tuple(ids)).fetchall()
            return [self.parse(row) for row in rows]

    def get_all(self) -> list[Car]:
        with connect() as conn:
            rows = conn.execute("SELECT * FROM cars ORDER BY id").fetchall()
            return [self.parse(row) for row in rows]

    def bulk_sync(self, updates: list[Car], inserts: list[Car]):
        """Усі апсерти синку в одній транзакції (один commit замість одного на авто).

        rank/favorite не чіпаємо — бандл їх не містить, зберігаємо наявні значення."""
        if not updates and not inserts:
            return
        with connect() as conn:
            for item in updates:
                conn.execute(
                    "UPDATE cars SET asec_id = :asec_id, name = :name, brand = :brand, model = :model,"
                    " car_class = :car_class, max_rank = :max_rank, icon = :icon WHERE id = :id",
                    item.model_dump())
            for item in inserts:
                conn.execute(
                    "INSERT INTO cars(asec_id, name, brand, model, car_class, `rank`, max_rank, favorite, icon)"
                    " VALUES (:asec_id, :name, :brand, :model, :car_class, :rank, :max_rank, :favorite, :icon)",
                    item.model_dump())


class CarsService(Observable):
    def __init__(self, repo: CarsRepository):
        self.repo = repo

    def autocomplete(self, query: str = "", by_max_rank: bool = False, car_class: str = ""):
        return self.repo.autocomplete(query.strip(), by_max_rank, car_class)

    def count(self, query: str = "", car_class: str = "") -> int:
        return self.repo.count(query.strip(), car_class)

    @property
    def list_limit(self) -> int:
        return self.repo.LIMIT

    def get_by_ids(self, ids: set[int]) -> dict[int, Car]:
        if not ids:
            return dict()
        items = self.repo.get_by_ids(list(ids))
        return {i.id: i for i in items}

    def get_all(self) -> list[Car]:
        """Усі авто — словник для розпізнавання."""
        return self.repo.get_all()

    def save(self, item: Car, update_empty_rank = True) -> int:
        if item.id <= 0:
            existing = self.repo.get_by_name(item.name)
            if not existing:
                new_id = self.repo.add(item)
                self._notify()
                return new_id
            item.id = existing.id

        self.repo.update(item, update_empty_rank)
        self._notify()
        return item.id

    def get_or_create(self, name: str, rank: int = 0) -> int:
        existing = self.repo.get_by_name(name)
        if existing:
            if rank > 0 and rank != existing.rank:
                self.repo.update_rank(existing.id, rank)
                self._notify()
            return existing.id
        new_id = self.repo.add(Car(name=name, model=name, rank=rank))
        self._notify()
        return new_id

    def update_rank(self, car_id: int, rank: int):
        self.repo.update_rank(car_id, rank)
        self._notify()

    def toggle_favorite(self, car_id: int):
        self.repo.toggle_favorite(car_id)
        self._notify()

    def sync_from_asec(self, entries: list[dict]):
        """Upsert cars from asec.tools carsList entries, matching by asec_id, then by name.

        Виконується на кожному старті. Читаємо всі авто один раз, пишемо лише змінені
        рядки й однією транзакцією — теплий старт (бандл не змінився) не робить жодного запису."""
        existing = self.repo.get_all()
        by_asec = {c.asec_id: c for c in existing if c.asec_id}
        by_name = {c.name.lower(): c for c in existing}

        updates: list[Car] = []
        inserts: list[Car] = []
        for entry in entries:
            try:
                planned = self._plan_entry(entry, by_asec, by_name)
                if planned is None:
                    continue
                kind, car = planned
                (updates if kind == "update" else inserts).append(car)
            except Exception as e:
                print(f"Failed to sync car {entry}: {e}")

        self.repo.bulk_sync(updates, inserts)

    def _plan_entry(self, entry: dict, by_asec: dict[int, Car], by_name: dict[str, Car]):
        """Повертає ("update"/"insert", Car) або None, якщо запис не потрібен (немає даних чи без змін)."""
        asec_id = entry.get("id") or 0
        brand = (entry.get("brand") or "").strip()
        model = (entry.get("model") or "").strip()
        name = f"{brand} {model}".strip()
        if not asec_id or not name:
            return None

        car = by_asec.get(asec_id) or by_name.get(name.lower())
        if not car and name in LEGACY_NAMES:
            car = by_name.get(LEGACY_NAMES[name].lower())

        icon = self._resolve_icon(asec_id)
        car_class = entry.get("car_class") or ""
        max_rank = entry.get("max_rank") or 0

        if car:
            new_icon = icon or car.icon
            if (car.asec_id == asec_id and car.name == name and car.brand == brand
                    and car.model == model and car.car_class == car_class
                    and car.max_rank == max_rank and car.icon == new_icon):
                return None  # без змін — не пишемо
            car.asec_id = asec_id
            car.name = name
            car.brand = brand
            car.model = model
            car.car_class = car_class
            car.max_rank = max_rank
            car.icon = new_icon
            return "update", car

        new_car = Car(asec_id=asec_id, name=name, brand=brand, model=model,
                      car_class=car_class, max_rank=max_rank, icon=icon)
        # реєструємо, щоб дублікати в межах одного бандла не призвели до подвійного insert
        by_asec[asec_id] = new_car
        by_name[name.lower()] = new_car
        return "insert", new_car

    @staticmethod
    def _resolve_icon(asec_id: int) -> str:
        """Іконка з data-теки або копія з бандлених ресурсів; "" якщо в бандлі немає.

        Оновлення іконок у бандлі — вручну, див. docs/updating-cars-data.md."""
        icon_file = f"{asec_id}.webp"
        dest = os.path.join(DATA_PATH_CARS, icon_file)
        if os.path.exists(dest):
            return dest

        return copy_resource_to_data(f"icons/cars/{icon_file}", dest) or ""
