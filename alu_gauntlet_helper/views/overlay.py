from html import escape

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from alu_gauntlet_helper.services.challenge_session import RACE_COUNT, EffectiveRace
from alu_gauntlet_helper.utils.utils import format_time

MARGIN = 16


def build_overlay_html(races: dict[int, EffectiveRace],
                       track_names: dict[int, str],
                       car_names: dict[int, str],
                       status: str = "",
                       hotkey_hint: str = "") -> str:
    """Будує rich-text (HTML) для оверлея: заголовок, таблиця 5 гонок, підказка та статус.

    Гонки рендеряться таблицею, тож колонки треку/авто/часу вирівняні попри пропорційний шрифт.
    """
    complete = sum(1 for e in races.values() if e.is_complete)
    header = f"<div style='font-weight:bold'>Gauntlet capture {complete}/5</div>"

    rows = []
    for n in range(1, RACE_COUNT + 1):
        e = races.get(n)
        if e is None:
            rows.append(
                f"<tr><td style='padding-right:8px'>{n}</td>"
                f"<td colspan='3' style='color:#9aa0c0'>no data</td></tr>"
            )
            continue
        track = track_names.get(e.track_id, "?") if e.track_id else "?"
        car = car_names.get(e.car_id, "?") if e.car_id else (e.car_name or "?")
        time_str = format_time(e.time) if e.time else "?"
        if e.is_complete:
            mark, mark_color = "✓", "#67d27a"
        else:
            mark, mark_color = "⚠", "#e6c34a"
        rows.append(
            f"<tr>"
            f"<td style='padding-right:8px'>{n}&nbsp;<span style='color:{mark_color}'>{mark}</span></td>"
            f"<td style='padding-right:12px'>{escape(track)}</td>"
            f"<td style='padding-right:12px'>{escape(car)}</td>"
            f"<td>{escape(time_str)}</td>"
            f"</tr>"
        )
    table = (
        "<table cellspacing='0' cellpadding='0' "
        "style='margin-top:8px;margin-bottom:8px'>" + "".join(rows) + "</table>"
    )

    footer = ""
    if status or hotkey_hint:
        footer = (
            "<table width='100%' cellspacing='0' cellpadding='0'><tr>"
            f"<td align='left' style='padding-right:24px'>{escape(status)}</td>"
            f"<td align='right' style='color:#9aa0c0'>{escape(hotkey_hint)}</td>"
            "</tr></table>"
        )

    return header + table + footer


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
        self.label.setTextFormat(Qt.TextFormat.RichText)
        self.label.setStyleSheet("""
            background-color: rgba(8, 10, 40, 215);
            color: white;
            font-size: 13px;
            padding: 12px 16px;
            border-radius: 8px;
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)

    def set_html(self, html: str):
        self.label.setText(html)
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
