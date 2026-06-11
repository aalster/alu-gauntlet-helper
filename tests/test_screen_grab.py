import numpy as np

from alu_gauntlet_helper.capture.screen_grab import grab_screen, save_capture


def test_grab_screen_returns_bgr_image():
    img = grab_screen(1)
    assert isinstance(img, np.ndarray)
    assert img.ndim == 3 and img.shape[2] == 3
    assert img.shape[0] > 100 and img.shape[1] > 100


def test_save_capture_rotates(tmp_path):
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    path = ""
    for _ in range(25):
        path = save_capture(img, directory=str(tmp_path), keep=20)
    assert path.endswith(".png")
    assert len(list(tmp_path.glob("*.png"))) == 20
