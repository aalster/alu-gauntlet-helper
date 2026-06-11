import os
import urllib.request

from alu_gauntlet_helper.database import connect
from alu_gauntlet_helper.utils.utils import copy_resource_to_data, DATA_PATH_CARS
from pydantic import BaseModel

ASEC_ICON_URL = "https://img.asec.tools/{asec_id}.webp"
USER_AGENT = "ALU-Gauntlet-Helper"
ICON_FETCH_TIMEOUT_SECONDS = 15


class Car(BaseModel):
    id: int = 0
    asec_id: int = 0
    name: str = ""
    brand: str = ""
    model: str = ""
    car_class: str = ""
    rank: int = 0
    max_rank: int = 0
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
                "INSERT INTO cars(asec_id, name, brand, model, car_class, `rank`, max_rank, icon)"
                " VALUES (:asec_id, :name, :brand, :model, :car_class, :rank, :max_rank, :icon)",
                item.model_dump()).lastrowid


    def get_by_name(self, name: str):
        with connect() as conn:
            row = conn.execute("SELECT * FROM cars WHERE name = :name COLLATE NOCASE LIMIT 1", {"name": name}).fetchone()
            return self.parse(row)

    def get_by_asec_id(self, asec_id: int):
        with connect() as conn:
            row = conn.execute("SELECT * FROM cars WHERE asec_id = :asec_id LIMIT 1", {"asec_id": asec_id}).fetchone()
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
            conn.execute(f"UPDATE cars SET asec_id = :asec_id, name = :name, brand = :brand, model = :model,"
                         f" car_class = :car_class, max_rank = :max_rank, icon = :icon {rank_update}"
                         f" WHERE id = :id", item.model_dump())

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


class CarsService:
    def __init__(self, repo: CarsRepository):
        self.repo = repo

    def autocomplete(self, query: str = ""):
        return self.repo.autocomplete(query.strip())

    def get_by_ids(self, ids: set[int]) -> dict[int, Car]:
        if not ids:
            return dict()
        items = self.repo.get_by_ids(list(ids))
        return {i.id: i for i in items}

    def save(self, item: Car, update_empty_rank = True) -> int:
        if item.id <= 0:
            existing = self.repo.get_by_name(item.name)
            if not existing:
                return self.repo.add(item)
            item.id = existing.id

        self.repo.update(item, update_empty_rank)
        return item.id

    def get_or_create(self, name: str, rank: int = 0) -> int:
        existing = self.repo.get_by_name(name)
        if existing:
            if rank > 0 and rank != existing.rank:
                self.repo.update_rank(existing.id, rank)
            return existing.id
        return self.repo.add(Car(name=name, model=name, rank=rank))

    def update_rank(self, car_id: int, rank: int):
        self.repo.update_rank(car_id, rank)

    def sync_from_asec(self, entries: list[dict]):
        """Upsert cars from asec.tools carsList entries, matching by asec_id, then by name."""
        for entry in entries:
            try:
                self._sync_entry(entry)
            except Exception as e:
                print(f"Failed to sync car {entry}: {e}")

    def _sync_entry(self, entry: dict):
        asec_id = entry.get("id") or 0
        brand = (entry.get("brand") or "").strip()
        model = (entry.get("model") or "").strip()
        name = f"{brand} {model}".strip()
        if not asec_id or not name:
            return

        car = self.repo.get_by_asec_id(asec_id) or self.repo.get_by_name(name)
        if not car and name in LEGACY_NAMES:
            car = self.repo.get_by_name(LEGACY_NAMES[name])

        icon = self._resolve_icon(asec_id)
        if car:
            car.asec_id = asec_id
            car.name = name
            car.brand = brand
            car.model = model
            car.car_class = entry.get("car_class") or ""
            car.max_rank = entry.get("max_rank") or 0
            car.icon = icon or car.icon
            self.repo.update(car, False)
        else:
            self.repo.add(Car(asec_id=asec_id, name=name, brand=brand, model=model,
                              car_class=entry.get("car_class") or "", max_rank=entry.get("max_rank") or 0,
                              icon=icon))

    @staticmethod
    def _resolve_icon(asec_id: int) -> str:
        """Icon from data dir, falling back to bundled resources, then to img.asec.tools."""
        icon_file = f"{asec_id}.webp"
        dest = os.path.join(DATA_PATH_CARS, icon_file)
        if os.path.exists(dest):
            return dest

        copied = copy_resource_to_data(f"icons/cars/{icon_file}", dest)
        if copied:
            return copied

        try:
            request = urllib.request.Request(ASEC_ICON_URL.format(asec_id=asec_id), headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=ICON_FETCH_TIMEOUT_SECONDS) as response:
                data = response.read()
            os.makedirs(DATA_PATH_CARS, exist_ok=True)
            with open(dest, "wb") as f:
                f.write(data)
            return dest
        except Exception as e:
            print(f"Failed to download icon for car {asec_id}: {e}")
            return ""
