"""Оцінка заїзду «як проїхав» проти власного середнього на треку/авто:
−2…+2 (плюс = швидше). Пороги фіксовані (0.2 с / 0.5 с), але на треках із
широким розкидом моїх часів розтягуються пропорційно робастній σ (MAD)."""
from alu_gauntlet_helper.services.assistant import (RUN_EQUAL_MS, RUN_STRONG_MS,
                                                    grade_run)
from tests.test_assistant import service


def test_no_history_gives_none():
    assert grade_run(20000, []) is None


def test_fixed_thresholds_on_small_sample():
    hist = [20000, 20000]  # avg 20000, σ не рахується (n < 3)
    assert grade_run(20000, hist) == 0
    assert grade_run(20000 - RUN_EQUAL_MS, hist) == 0       # рівно на межі — ще «≈»
    assert grade_run(20000 - RUN_EQUAL_MS - 1, hist) == 1
    assert grade_run(20000 - RUN_STRONG_MS, hist) == 1      # межа — ще одинарний
    assert grade_run(20000 - RUN_STRONG_MS - 1, hist) == 2
    assert grade_run(20000 + 300, hist) == -1
    assert grade_run(20000 + 600, hist) == -2


def test_reference_is_mean_of_history():
    assert grade_run(19700, [19000, 19100, 21000]) == 0    # avg 19700


def test_wide_spread_stretches_thresholds():
    # median 20000, MAD 500 → σ≈741: «≈» до 370 мс, подвійний — понад 1112 мс
    hist = [19000, 20000, 21000, 19500, 20500]  # avg 20000
    assert grade_run(19700, hist) == 0     # за фіксованими було б +1
    assert grade_run(19000, hist) == 1     # за фіксованими було б +2
    assert grade_run(18800, hist) == 2
    assert grade_run(21200, hist) == -2


def test_single_outlier_does_not_stretch_thresholds():
    # MAD ігнорує один «чистий, але повільний» заїзд: σ≈148 → діють підлоги
    hist = [19000, 19100, 21000]  # avg 19700
    assert grade_run(19300, hist) == 1
    assert grade_run(19100, hist) == 2


def test_service_grades_against_car_history():
    svc = service({501: [19000, 19100, 21000], 502: [30000]})
    assert svc.run_grade(7, 501, 19100) == 2
    assert svc.run_grade(7, 502, 30100) == 0
    assert svc.run_grade(7, 999, 19100) is None
