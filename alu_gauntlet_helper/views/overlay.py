from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from alu_gauntlet_helper.services.challenge_session import RACE_COUNT, EffectiveRace
from alu_gauntlet_helper.utils.utils import format_time

MARGIN = 16


def build_overlay_lines(races: dict[int, EffectiveRace],
                        track_names: dict[int, str],
                        car_names: dict[int, str],
                        status: str = "",
                        hotkey_hint: str = "") -> list[str]:
    complete = sum(1 for e in races.values() if e.is_complete)
    lines = [f"Gauntlet capture {complete}/5"]
    for n in range(1, RACE_COUNT + 1):
        e = races.get(n)
        if e is None:
            lines.append(f"{n} — no data")
            continue
        track = track_names.get(e.track_id, "?") if e.track_id else "?"
        car = car_names.get(e.car_id, "?") if e.car_id else (e.car_name or "?")
        time_str = format_time(e.time) if e.time else "?"
        mark = "✓" if e.is_complete else "⚠"
        lines.append(f"{n} {mark} {track} · {car} · {time_str}")
    if hotkey_hint:
        lines.append(hotkey_hint)
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
