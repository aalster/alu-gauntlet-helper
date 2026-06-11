from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from alu_gauntlet_helper.models import RaceCapture
from alu_gauntlet_helper.utils.utils import format_time

RACE_COUNT = 5
MARGIN = 16


def build_overlay_lines(races: dict[int, RaceCapture],
                        track_names: dict[int, str],
                        car_names: dict[int, str],
                        status: str = "") -> list[str]:
    complete = sum(
        1 for c in races.values() if c.track and c.car and c.time
    )
    lines = [f"Gauntlet capture {complete}/5"]
    for n in range(1, RACE_COUNT + 1):
        capture = races.get(n)
        if capture is None:
            lines.append(f"{n} — немає даних")
            continue
        track = track_names.get(capture.track.value, "?") if capture.track else "?"
        car = car_names.get(capture.car.value, "?") if capture.car else "?"
        time_str = format_time(capture.time) if capture.time else "?"
        mark = "✓" if capture.track and capture.car and capture.time else "⚠"
        lines.append(f"{n} {mark} {track} · {car} · {time_str}")
    if status:
        lines.append(status)
    return lines


class OverlayWindow(QWidget):
    """Click-through панель статусу поверх гри (borderless fullscreen)."""

    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, True)
        self._screen_index = 1

        self.label = QLabel()
        self.label.setStyleSheet("""
            background-color: rgba(8, 10, 40, 215);
            color: white;
            font-size: 13px;
            padding: 10px 14px;
            border-radius: 8px;
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)

    def set_lines(self, lines: list[str]):
        self.label.setText("\n".join(lines))
        self.adjustSize()
        self._move_to_corner()

    def set_screen_index(self, index: int):
        """mss-індекс монітора (1-based); оверлей стає у кут цього екрана."""
        self._screen_index = index
        self._move_to_corner()

    def _move_to_corner(self):
        screens = QGuiApplication.screens()
        screen = screens[self._screen_index - 1] if 0 < self._screen_index <= len(screens) else QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        self.move(geo.right() - self.width() - MARGIN, geo.top() + MARGIN)

    def toggle(self):
        self.setVisible(not self.isVisible())
