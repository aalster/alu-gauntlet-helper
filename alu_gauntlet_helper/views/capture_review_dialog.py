from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QDialog, QGridLayout, QHBoxLayout, QLabel,
                             QMessageBox, QPushButton, QVBoxLayout)

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.races import RaceView
from alu_gauntlet_helper.utils.utils import format_time, parse_time, time_format_regex
from alu_gauntlet_helper.views.components.item_completer import ItemCompleter
from alu_gauntlet_helper.views.components.validated_line_edit import ValidatedLineEdit

LOW_CONFIDENCE = 0.85
WARN_STYLE = "background-color: rgba(255, 200, 0, 0.25);"


class ReviewRow:
    """Один рядок рев'ю: трек, авто, ранг, час + мініатюра джерела."""

    def __init__(self, race_number: int, capture):
        self.race_number = race_number
        self.capture = capture

        self.thumbnail = QLabel()
        self.thumbnail.setFixedSize(160, 64)
        self.thumbnail.setStyleSheet("background-color: #271A62;")
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if capture and capture.panel_image:
            pixmap = QPixmap()
            pixmap.loadFromData(capture.panel_image)
            self.thumbnail.setPixmap(pixmap.scaled(
                160, 64, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))

        self.track_edit = ValidatedLineEdit(placeholder="Track...")
        self.track_completer = ItemCompleter(
            self.track_edit.get_input(),
            autocomplete=APP_CONTEXT.tracks_service.autocomplete,
            presentation=lambda i: f"{i.map_name} - {i.name}",
            allow_custom_text=False,
        )

        self.car_edit = ValidatedLineEdit(placeholder="Car...")
        self.car_completer = ItemCompleter(
            self.car_edit.get_input(),
            autocomplete=APP_CONTEXT.cars_service.autocomplete,
            presentation=lambda i: i.name,
            allow_custom_text=False,
        )

        self.rank_edit = ValidatedLineEdit(placeholder="Rank", regex=r"^\d{0,5}$")
        self.time_edit = ValidatedLineEdit(placeholder="Time", regex=time_format_regex)

        self._prefill()

    @property
    def is_empty(self) -> bool:
        return self.capture is None

    def _prefill(self):
        if not self.capture:
            return
        if self.capture.track:
            tracks = APP_CONTEXT.tracks_service.get_by_ids({self.capture.track.value})
            track = tracks.get(self.capture.track.value)
            if track:
                self.track_edit.set_text(f"{track.map_name} - {track.name}")
                self.track_completer.set_selected_item(track)
            if self.capture.track.score < LOW_CONFIDENCE:
                self.track_edit.get_input().setStyleSheet(WARN_STYLE)

        car = None
        if self.capture.car:
            cars = APP_CONTEXT.cars_service.get_by_ids({self.capture.car.value})
            car = cars.get(self.capture.car.value)
            if car:
                self.car_edit.set_text(car.name)
                self.car_completer.set_selected_item(car)
            if self.capture.car.score < LOW_CONFIDENCE:
                self.car_edit.get_input().setStyleSheet(WARN_STYLE)

        rank = self.capture.rank
        if rank is None and car and car.rank:
            rank = car.rank  # фолбек: поточний ранг авто з БД
        if rank:
            self.rank_edit.set_text(str(rank))
        else:
            self.rank_edit.get_input().setStyleSheet(WARN_STYLE)
        if self.capture.time:
            self.time_edit.set_text(format_time(self.capture.time))

    def build_race(self) -> RaceView | None:
        """RaceView для збереження або None, якщо рядок невалідний (з підсвіткою помилок)."""
        track = self.track_completer.get_selected_item()
        car = self.car_completer.get_selected_item()
        time_ms = parse_time(self.time_edit.text())

        valid = True
        if not track:
            self.track_edit.set_error("Select track")
            valid = False
        if not car:
            self.car_edit.set_error("Select car")
            valid = False
        if time_ms <= 0:
            self.time_edit.set_error("Invalid time")
            valid = False
        if not valid:
            return None

        return RaceView(
            track_id=track.id,
            car_id=car.id,
            rank=int(self.rank_edit.text() or 0),
            time=time_ms,
        )


class CaptureReviewDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review captured races")
        self.setMinimumWidth(900)

        self.rows = [
            ReviewRow(n, APP_CONTEXT.challenge_session.races.get(n))
            for n in range(1, 6)
        ]

        grid = QGridLayout()
        for col, title in enumerate(["#", "Source", "Track", "Car", "Rank", "Time"]):
            grid.addWidget(QLabel(f"<b>{title}</b>"), 0, col)
        for i, row in enumerate(self.rows, start=1):
            grid.addWidget(QLabel(str(row.race_number)), i, 0)
            grid.addWidget(row.thumbnail, i, 1)
            grid.addWidget(row.track_edit, i, 2)
            grid.addWidget(row.car_edit, i, 3)
            grid.addWidget(row.rank_edit, i, 4)
            grid.addWidget(row.time_edit, i, 5)
        grid.setColumnStretch(2, 2)
        grid.setColumnStretch(3, 2)

        self.save_button = QPushButton("Save all")
        self.save_button.clicked.connect(self.on_save)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(cancel_button)
        buttons.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.addLayout(grid)
        layout.addLayout(buttons)

    def on_save(self):
        non_empty = [row for row in self.rows if not row.is_empty]
        if not non_empty:
            QMessageBox.warning(self, "Nothing to save", "No captured races in session.")
            return
        races = [row.build_race() for row in non_empty]
        if any(r is None for r in races):
            return  # невалідні рядки підсвічені set_error
        try:
            for race in races:
                APP_CONTEXT.races_service.save(race)
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))
            return  # сесію не чистимо — можна виправити й повторити
        APP_CONTEXT.challenge_session.clear()
        QMessageBox.information(self, "Saved", f"{len(races)} race(s) saved.")
        self.accept()
