import numpy as np

from alu_gauntlet_helper.screen_recognition.regions import RelRect


def test_to_abs():
    r = RelRect(0.1, 0.2, 0.5, 0.25)
    assert r.to_abs(1000, 400) == (100, 80, 500, 100)


def test_crop():
    img = np.zeros((400, 1000, 3), dtype=np.uint8)
    cropped = RelRect(0.1, 0.2, 0.5, 0.25).crop(img)
    assert cropped.shape == (100, 500, 3)


def test_sub_region_is_relative_to_parent():
    panel = RelRect(0.1, 0.2, 0.4, 0.5)
    header = panel.sub(RelRect(0.0, 0.0, 1.0, 0.2))
    assert header.x == 0.1 and header.y == 0.2
    assert abs(header.w - 0.4) < 1e-9 and abs(header.h - 0.1) < 1e-9


def test_shifted():
    r = RelRect(0.1, 0.2, 0.4, 0.5).shifted(0.05, -0.02)
    assert abs(r.x - 0.15) < 1e-9 and abs(r.y - 0.18) < 1e-9
    assert r.w == 0.4 and r.h == 0.5
