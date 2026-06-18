import os
import time

import cv2
import mss
import numpy as np

CAPTURES_DIR = "data/captures"


def list_monitors() -> list[tuple[int, int]]:
    """Список (width, height) для кожного фізичного монітора.
    Без monitors[0], який у mss означає «усі екрани разом»."""
    with mss.mss() as sct:
        return [(m["width"], m["height"]) for m in sct.monitors[1:]]


def monitor_count() -> int:
    """Кількість фізичних моніторів."""
    with mss.mss() as sct:
        return len(sct.monitors) - 1


def grab_screen(monitor_index: int = 1) -> np.ndarray:
    """Скріншот монітора як BGR numpy array. monitors[0] — усі екрани разом."""
    with mss.mss() as sct:
        if not 1 <= monitor_index < len(sct.monitors):
            print(f"grab_screen: monitor {monitor_index} out of range ({len(sct.monitors) - 1} available), using 1")
            monitor_index = 1
        shot = sct.grab(sct.monitors[monitor_index])
        img = np.asarray(shot)[:, :, :3]  # BGRA -> BGR
        return np.ascontiguousarray(img)


def save_capture(img: np.ndarray, directory: str = CAPTURES_DIR, keep: int = 20) -> str:
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"capture_{time.time_ns()}.png")
    if not cv2.imwrite(path, img):
        print(f"save_capture: cv2.imwrite failed for {path}")
        return ""

    files = sorted(
        (os.path.join(directory, f) for f in os.listdir(directory) if f.endswith(".png")),
        key=os.path.getmtime,
    )
    for old in files[:-keep]:
        os.remove(old)
    return path
