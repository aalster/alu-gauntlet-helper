"""Вибірка «останні 10 успішних» має бути однією для агрегатів, тултипа
вкладки заїздів і підбору авто в асистенті: спершу відкидаються заїзди
з 👎 і без часу, потім беруться 10 останніх."""
import pytest

from alu_gauntlet_helper import database
from alu_gauntlet_helper.services.races import RacesRepository

TRACK, CAR = 1, 7


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_FILE", str(tmp_path / "test.db"))
    database.init_db()
    return RacesRepository()


def seed(races: list[tuple[int, int]]):
    """(time, bad_timing) у хронологічному порядку; created_at унікальний."""
    with database.connect() as conn:
        for i, (time, bad) in enumerate(races):
            conn.execute(
                "INSERT INTO races (track_id, car_id, time, bad_timing, created_at)"
                " VALUES (:t, :c, :time, :bad, :ts)",
                {"t": TRACK, "c": CAR, "time": time, "bad": bad,
                 "ts": f"2026-01-01 00:00:{i:02d}"})


# 12 чистих по 100 мс, потім 4 дизлайки по 999 і один чистий 200 (останній).
# Останні 10 успішних: 200 + 9×100 → avg 110, n = 10.
# Успішні серед 10 останніх (старий підхід): 200 + 5×100 → avg ≈ 117, n = 6.
MIXED = [(100, 0)] * 12 + [(999, 1)] * 4 + [(200, 0)]


def test_aggregates_use_last_ten_clean(repo):
    seed(MIXED)
    agg = repo.get_aggregates("", "")[0]
    assert agg["recent_count"] == 10
    assert agg["avg_recent"] == pytest.approx(110)


def test_aggregates_for_track_use_last_ten_clean(repo):
    seed(MIXED)
    agg = repo.get_aggregates_for_track(TRACK)[0]
    assert agg["recent_count"] == 10
    assert agg["avg_recent"] == pytest.approx(110)


def test_recent_clean_races_match_assistant_sample(repo):
    seed(MIXED)
    races = repo.get_recent_clean_races(TRACK, CAR)
    assert [r.time for r in races] == [200] + [100] * 9
    assert races == sorted(races, key=lambda r: r.created_at, reverse=True)
    assert [r.time for r in races] == repo.get_recent_clean_times_by_car(TRACK)[CAR]


def test_untimed_and_disliked_are_skipped(repo):
    seed([(0, 0), (300, 1), (100, 0)])
    agg = repo.get_aggregates_for_track(TRACK)[0]
    assert agg["recent_count"] == 1
    assert agg["avg_recent"] == 100
    assert [r.time for r in repo.get_recent_clean_races(TRACK, CAR)] == [100]
