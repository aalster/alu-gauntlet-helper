from datetime import datetime

from pydantic import BaseModel, field_validator

from alu_gauntlet_helper import game_lang
from alu_gauntlet_helper.database import connect
from alu_gauntlet_helper.services.cars import CarsService
from alu_gauntlet_helper.services.observable import Observable
from alu_gauntlet_helper.services.tracks import TracksService, TrackView
from alu_gauntlet_helper.utils.utils import parse_utc_datetime


class Race(BaseModel):
    id: int = 0
    track_id: int = 0
    car_id: int = 0
    rank: int = 0
    time: int = 0
    bad_timing: bool = False
    note: str = ""
    created_at: datetime | None = None

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_datetime(cls, v):
        return parse_utc_datetime(v)

class RaceView(Race):
    map_name: str = ""
    map_name_ru: str = ""
    map_icon: str = ""
    track_name: str = ""
    track_name_ru: str = ""
    track_icon: str = ""
    car_name: str = ""
    car_brand: str = ""
    car_model: str = ""
    car_class: str = ""
    car_rank: int = 0
    car_max_rank: int = 0
    car_icon: str = ""

    @property
    def display_map_name(self) -> str:
        return game_lang.localize(self.map_name, self.map_name_ru)

    @property
    def display_track_name(self) -> str:
        return game_lang.localize(self.track_name, self.track_name_ru)


class RaceAggregate(BaseModel):
    """Зведена статистика заїздів пари трек+авто в межах поточного фільтра."""
    track_id: int = 0
    map_name: str = ""
    map_name_ru: str = ""
    map_icon: str = ""
    track_name: str = ""
    track_name_ru: str = ""
    track_icon: str = ""
    car_id: int = 0
    car_name: str = ""
    car_brand: str = ""
    car_model: str = ""
    car_class: str = ""
    car_rank: int = 0
    car_max_rank: int = 0
    car_icon: str = ""
    best_time: int = 0
    avg_recent: int = 0  # середнє за останні 10 заїздів без дизлайків
    recent_count: int = 0  # кількість заїздів, з яких пораховане avg_recent
    avg_time: int = 0  # середнє успішних (без дизлайків) за весь час
    avg_fail: int = 0  # середнє заїздів з дизлайком за весь час
    timed_count: int = 0  # заїзди з часом (для best_time)
    ok_count: int = 0  # успішні заїзди з часом (для avg_time)
    fail_count: int = 0  # дизлайкнуті заїзди з часом (для avg_fail)
    race_count: int = 0
    dislike_count: int = 0

    @property
    def dislike_pct(self) -> int:
        return round(100 * self.dislike_count / self.race_count) if self.race_count else 0

    @property
    def display_map_name(self) -> str:
        return game_lang.localize(self.map_name, self.map_name_ru)

    @property
    def display_track_name(self) -> str:
        return game_lang.localize(self.track_name, self.track_name_ru)


class CarSuggestion(BaseModel):
    car_id: int = 0
    car_name: str = ""
    car_brand: str = ""
    car_model: str = ""
    car_class: str = ""
    car_rank: int = 0
    car_favorite: bool = False
    car_icon: str = ""
    avg_time: int = 0
    race_count: int = 0


class RacesRepository:
    @staticmethod
    def parse(row):
        return Race(**row) if row else None

    def add(self, item: Race):
        with connect() as conn:
            conn.execute("INSERT INTO races"
                         " (track_id, car_id, `rank`, time, bad_timing, note) VALUES"
                         " (:track_id, :car_id, :rank, :time, :bad_timing, :note)",
                         item.model_dump())

    LIMIT = 100

    @staticmethod
    def _build_filter(track_query: str, car_query: str):
        sql = (" FROM races r"
               " LEFT JOIN tracks t ON r.track_id = t.id"
               " LEFT JOIN maps m ON t.map_id = m.id"
               " LEFT JOIN cars c ON r.car_id = c.id"
               " WHERE 1 = 1")
        params = {}

        if track_query:
            sql += (" AND (lower_u(t.name) LIKE :track_query OR lower_u(t.name_ru) LIKE :track_query"
                    " OR lower_u(m.name) LIKE :track_query OR lower_u(m.name_ru) LIKE :track_query)")
            params['track_query'] = f"%{track_query.lower()}%"

        if car_query:
            sql += " AND lower_u(c.name) LIKE :car_query"
            params['car_query'] = f"%{car_query.lower()}%"

        return sql, params

    def get_all(self, track_query: str, car_query: str, by_best_time: bool = False):
        with (connect() as conn):
            from_where, params = self._build_filter(track_query, car_query)
            # заїзди без часу (драфти) при сортуванні за часом ідуть у кінець
            order = " ORDER BY r.time <= 0, r.time ASC" if by_best_time else " ORDER BY r.created_at DESC"
            sql = "SELECT r.*" + from_where + order + f" LIMIT {self.LIMIT}"
            rows = conn.execute(sql, params).fetchall()
            return [self.parse(row) for row in rows]

    def get_aggregates(self, track_query: str, car_query: str, by_best_time: bool = False) -> list[dict]:
        """Зведення заїздів по парі трек+авто в межах фільтра."""
        with connect() as conn:
            from_where, params = self._build_filter(track_query, car_query)
            order_col = "best_time" if by_best_time else "avg_recent"
            sql = f"""
            WITH filtered AS (
                SELECT r.track_id, r.car_id, r.time, r.bad_timing, r.created_at{from_where} AND r.car_id > 0
            ),
            ranked AS (
                SELECT track_id, car_id, time, bad_timing,
                       ROW_NUMBER() OVER (PARTITION BY track_id, car_id ORDER BY created_at DESC) AS rn
                FROM filtered
            )
            SELECT track_id, car_id,
                   MIN(CASE WHEN time > 0 THEN time END) AS best_time,
                   AVG(CASE WHEN bad_timing = 0 AND time > 0 THEN time END) AS avg_time,
                   AVG(CASE WHEN bad_timing = 1 AND time > 0 THEN time END) AS avg_fail,
                   AVG(CASE WHEN rn <= 10 AND bad_timing = 0 AND time > 0 THEN time END) AS avg_recent,
                   COUNT(CASE WHEN rn <= 10 AND bad_timing = 0 AND time > 0 THEN 1 END) AS recent_count,
                   COUNT(CASE WHEN time > 0 THEN 1 END) AS timed_count,
                   COUNT(CASE WHEN bad_timing = 0 AND time > 0 THEN 1 END) AS ok_count,
                   COUNT(CASE WHEN bad_timing = 1 AND time > 0 THEN 1 END) AS fail_count,
                   COUNT(*) AS race_count,
                   SUM(bad_timing) AS dislike_count
            FROM ranked
            GROUP BY track_id, car_id
            ORDER BY {order_col} IS NULL, {order_col} ASC
            LIMIT {self.LIMIT}
            """
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]

    def get_aggregates_for_track(self, track_id: int) -> list[dict]:
        """Зведення по всіх авто одного треку (за id, без текстового фільтра) —
        та сама статистика, що й у get_aggregates; для підбору проти суперника."""
        with connect() as conn:
            sql = """
            WITH ranked AS (
                SELECT track_id, car_id, time, bad_timing,
                       ROW_NUMBER() OVER (PARTITION BY car_id ORDER BY created_at DESC) AS rn
                FROM races
                WHERE track_id = :track_id AND car_id > 0
            )
            SELECT track_id, car_id,
                   MIN(CASE WHEN time > 0 THEN time END) AS best_time,
                   AVG(CASE WHEN bad_timing = 0 AND time > 0 THEN time END) AS avg_time,
                   AVG(CASE WHEN bad_timing = 1 AND time > 0 THEN time END) AS avg_fail,
                   AVG(CASE WHEN rn <= 10 AND bad_timing = 0 AND time > 0 THEN time END) AS avg_recent,
                   COUNT(CASE WHEN rn <= 10 AND bad_timing = 0 AND time > 0 THEN 1 END) AS recent_count,
                   COUNT(CASE WHEN time > 0 THEN 1 END) AS timed_count,
                   COUNT(CASE WHEN bad_timing = 0 AND time > 0 THEN 1 END) AS ok_count,
                   COUNT(CASE WHEN bad_timing = 1 AND time > 0 THEN 1 END) AS fail_count,
                   COUNT(*) AS race_count,
                   SUM(bad_timing) AS dislike_count
            FROM ranked
            GROUP BY track_id, car_id
            """
            rows = conn.execute(sql, {"track_id": track_id}).fetchall()
            return [dict(row) for row in rows]

    def count_aggregates(self, track_query: str, car_query: str) -> int:
        with connect() as conn:
            from_where, params = self._build_filter(track_query, car_query)
            sql = ("SELECT COUNT(*) FROM (SELECT DISTINCT r.track_id, r.car_id"
                   + from_where + " AND r.car_id > 0)")
            return conn.execute(sql, params).fetchone()[0]

    def get_recent_clean_races(self, track_id: int, car_id: int, limit: int = 10) -> list[Race]:
        """Заїзди, з яких пораховане avg_recent агрегату: серед останніх `limit` заїздів
        пари — без дизлайків і без порожнього часу."""
        with connect() as conn:
            sql = """
            WITH ranked AS (
                SELECT id, track_id, car_id, `rank`, time, bad_timing, note, created_at,
                       ROW_NUMBER() OVER (ORDER BY created_at DESC) AS rn
                FROM races
                WHERE track_id = :track_id AND car_id = :car_id
            )
            SELECT id, track_id, car_id, `rank`, time, bad_timing, note, created_at
            FROM ranked
            WHERE rn <= :limit AND bad_timing = 0 AND time > 0
            ORDER BY created_at DESC
            """
            rows = conn.execute(sql, {"track_id": track_id, "car_id": car_id, "limit": limit}).fetchall()
            return [self.parse(row) for row in rows]

    def count(self, track_query: str, car_query: str) -> int:
        with connect() as conn:
            from_where, params = self._build_filter(track_query, car_query)
            return conn.execute("SELECT COUNT(*)" + from_where, params).fetchone()[0]

    def update(self, item: Race):
        with connect() as conn:
            conn.execute("UPDATE races SET"
                         " track_id = :track_id, car_id = :car_id, `rank` = :rank, time = :time,"
                         " bad_timing = :bad_timing, note = :note"
                         " WHERE id = :id", item.model_dump())

    def delete(self, race_id: int):
        with connect() as conn:
            conn.execute("DELETE FROM races WHERE id = :id", {"id": race_id})

    def get_car_stats_for_track(self, track_id: int) -> list[dict]:
        with connect() as conn:
            sql = """
            WITH ranked_races AS (
                SELECT car_id, time,
                       ROW_NUMBER() OVER (PARTITION BY car_id ORDER BY created_at DESC) as rn
                FROM races
                WHERE track_id = :track_id AND car_id > 0 AND time > 0
            ),
            last_10_races AS (
                SELECT car_id, time FROM ranked_races WHERE rn <= 10
            )
            SELECT lr.car_id, AVG(lr.time) as avg_time, COUNT(*) as race_count
            FROM last_10_races lr
            LEFT JOIN cars c ON c.id = lr.car_id
            GROUP BY lr.car_id
            ORDER BY c.favorite DESC, avg_time ASC
            """
            rows = conn.execute(sql, {"track_id": track_id}).fetchall()
            return [dict(row) for row in rows]

    def get_recent_clean_times_by_car(self, track_id: int, limit: int = 10) -> dict[int, list[int]]:
        """car_id → часи останніх `limit` ЧИСТИХ (без 👎) заїздів авто на треку.
        Та сама вибірка, що й у avg_recent агрегатів — для підбору проти суперника."""
        with connect() as conn:
            sql = """
            WITH ranked AS (
                SELECT car_id, time,
                       ROW_NUMBER() OVER (PARTITION BY car_id ORDER BY created_at DESC) AS rn
                FROM races
                WHERE track_id = :track_id AND car_id > 0 AND time > 0 AND bad_timing = 0
            )
            SELECT car_id, time FROM ranked WHERE rn <= :limit
            """
            rows = conn.execute(sql, {"track_id": track_id, "limit": limit}).fetchall()
            times: dict[int, list[int]] = {}
            for row in rows:
                times.setdefault(row["car_id"], []).append(row["time"])
            return times

    def get_best_races_for_car_on_track(self, track_id: int, car_id: int, limit: int = 10) -> list[Race]:
        with connect() as conn:
            sql = """
            SELECT * FROM races
            WHERE track_id = :track_id AND car_id = :car_id AND time > 0
            ORDER BY time ASC
            LIMIT :limit
            """
            rows = conn.execute(sql, {"track_id": track_id, "car_id": car_id, "limit": limit}).fetchall()
            return [self.parse(row) for row in rows]

    def get_recent_races_for_car_on_track(self, track_id: int, car_id: int, limit: int = 10,
                                          bad_timing: bool | None = None) -> list[Race]:
        with connect() as conn:
            sql = """
            SELECT * FROM races
            WHERE track_id = :track_id AND car_id = :car_id AND time > 0
            """
            params = {"track_id": track_id, "car_id": car_id, "limit": limit}
            if bad_timing is not None:
                sql += " AND bad_timing = :bad_timing"
                params["bad_timing"] = bad_timing
            sql += " ORDER BY created_at DESC LIMIT :limit"
            rows = conn.execute(sql, params).fetchall()
            return [self.parse(row) for row in rows]

class RacesService(Observable):
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
                map_name_ru=track.map_name_ru if track else "",
                map_icon=track.map_icon if track else "",
                track_name=track.name if track else "Unknown Track",
                track_name_ru=track.name_ru if track else "",
                track_icon=track.icon if track else "",
                car_name=car.name if car else "Unknown Car",
                car_brand=car.brand if car else "",
                car_model=(car.model or car.name) if car else "Unknown Car",
                car_class=car.car_class if car else "",
                car_rank=car.rank if car else 0,
                car_max_rank=car.max_rank if car else 0,
                car_icon=car.icon if car else ""
            ))
        return result

    def get_all(self, track_query: str, car_query: str, by_best_time: bool = False) -> list[RaceView]:
        return self.to_views(self.repo.get_all(track_query, car_query, by_best_time))

    def count(self, track_query: str, car_query: str) -> int:
        return self.repo.count(track_query, car_query)

    def get_aggregates(self, track_query: str, car_query: str, by_best_time: bool = False) -> list[RaceAggregate]:
        return self._to_aggregates(self.repo.get_aggregates(track_query, car_query, by_best_time))

    def get_aggregates_for_track(self, track_id: int) -> list[RaceAggregate]:
        return self._to_aggregates(self.repo.get_aggregates_for_track(track_id))

    def _to_aggregates(self, stats: list[dict]) -> list[RaceAggregate]:
        tracks = self.tracks.get_by_ids({s["track_id"] for s in stats})
        cars = self.cars.get_by_ids({s["car_id"] for s in stats})
        result = []
        for s in stats:
            track = tracks.get(s["track_id"])
            car = cars.get(s["car_id"])
            result.append(RaceAggregate(
                track_id=s["track_id"],
                map_name=track.map_name if track else "Unknown Map",
                map_name_ru=track.map_name_ru if track else "",
                map_icon=track.map_icon if track else "",
                track_name=track.name if track else "Unknown Track",
                track_name_ru=track.name_ru if track else "",
                track_icon=track.icon if track else "",
                car_id=s["car_id"],
                car_name=car.name if car else "Unknown Car",
                car_brand=car.brand if car else "",
                car_model=(car.model or car.name) if car else "Unknown Car",
                car_class=car.car_class if car else "",
                car_rank=car.rank if car else 0,
                car_max_rank=car.max_rank if car else 0,
                car_icon=car.icon if car else "",
                best_time=int(s["best_time"] or 0),
                avg_recent=int(s["avg_recent"] or 0),
                recent_count=s["recent_count"],
                avg_time=int(s["avg_time"] or 0),
                avg_fail=int(s["avg_fail"] or 0),
                timed_count=s["timed_count"],
                ok_count=s["ok_count"],
                fail_count=s["fail_count"],
                race_count=s["race_count"],
                dislike_count=s["dislike_count"] or 0
            ))
        return result

    def count_aggregates(self, track_query: str, car_query: str) -> int:
        return self.repo.count_aggregates(track_query, car_query)

    def get_recent_clean_races(self, track_id: int, car_id: int) -> list[Race]:
        return self.repo.get_recent_clean_races(track_id, car_id)

    @property
    def list_limit(self) -> int:
        return self.repo.LIMIT

    def save(self, item: RaceView):
        if item.track_id <= 0:
            item.track_id = self.tracks.save(TrackView(name=item.track_name, map_name=item.map_name))
        if item.car_id <= 0:
            item.car_id = self.cars.get_or_create(item.car_name, item.rank)
        elif item.rank > 0:
            self.cars.update_rank(item.car_id, item.rank)

        if item.id <= 0:
            self.repo.add(item)
        else:
            self.repo.update(item)
        self._notify()

    def delete(self, item: Race):
        self.repo.delete(item.id)
        self._notify()

    def get_car_suggestions_for_track(self, track_id: int) -> list[CarSuggestion]:
        stats = self.repo.get_car_stats_for_track(track_id)
        if not stats:
            return []

        car_ids = {s["car_id"] for s in stats}
        cars = self.cars.get_by_ids(car_ids)

        result = []
        for s in stats:
            car = cars.get(s["car_id"])
            result.append(CarSuggestion(
                car_id=s["car_id"],
                car_name=car.name if car else "Unknown Car",
                car_brand=car.brand if car else "",
                car_model=car.model if car else "",
                car_class=car.car_class if car else "",
                car_rank=car.rank if car else 0,
                car_favorite=car.favorite if car else False,
                car_icon=car.icon if car else "",
                avg_time=int(s["avg_time"]),
                race_count=s["race_count"]
            ))
        return result

    def get_recent_races_for_car_on_track(self, track_id: int, car_id: int,
                                          bad_timing: bool | None = None) -> list[Race]:
        return self.repo.get_recent_races_for_car_on_track(track_id, car_id, bad_timing=bad_timing)

    def get_best_races_for_car_on_track(self, track_id: int, car_id: int) -> list[Race]:
        return self.repo.get_best_races_for_car_on_track(track_id, car_id)

    def get_recent_clean_times_by_car(self, track_id: int, limit: int = 10) -> dict[int, list[int]]:
        return self.repo.get_recent_clean_times_by_car(track_id, limit)