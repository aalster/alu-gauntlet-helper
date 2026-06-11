from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.utils.utils import format_time
from alu_gauntlet_helper.views import style
from alu_gauntlet_helper.views.capture_review_dialog import CaptureReviewDialog


class CaptureTab(QWidget):
    """Стан сесії захоплення + рев'ю/скидання."""

    def __init__(self):
        super().__init__()

        settings = APP_CONTEXT.settings.get()
        hint = QLabel(
            f"У грі натисни <b>{settings.capture_hotkey.upper()}</b> на екрані результатів "
            f"челенджа (розгорнувши гонку), щоб захопити дані. "
            f"<b>{settings.overlay_hotkey.upper()}</b> — показати/сховати оверлей."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {style.TEXT_MUTED};")

        self.race_labels = [QLabel() for _ in range(5)]

        self.review_button = QPushButton("Review && Save")
        self.review_button.clicked.connect(self.open_review)
        self.discard_button = QPushButton("Discard session")
        self.discard_button.clicked.connect(self.discard)

        buttons = QHBoxLayout()
        buttons.addWidget(self.review_button)
        buttons.addWidget(self.discard_button)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        for label in self.race_labels:
            layout.addWidget(label)
        layout.addLayout(buttons)
        layout.addStretch()

        APP_CONTEXT.challenge_session.add_listener(self.refresh)
        self.refresh()

    def refresh(self):
        session = APP_CONTEXT.challenge_session
        track_ids = {c.track.value for c in session.races.values() if c.track}
        car_ids = {c.car.value for c in session.races.values() if c.car}
        tracks = APP_CONTEXT.tracks_service.get_by_ids(track_ids)
        cars = APP_CONTEXT.cars_service.get_by_ids(car_ids)

        for n, label in enumerate(self.race_labels, start=1):
            capture = session.races.get(n)
            if capture is None:
                label.setText(f"Race {n}: —")
                label.setStyleSheet(f"color: {style.TEXT_MUTED};")
                continue
            track = tracks.get(capture.track.value) if capture.track else None
            car = cars.get(capture.car.value) if capture.car else None
            parts = [
                f"{track.map_name} - {track.name}" if track else "трек?",
                car.name if car else "авто?",
                f"rank {capture.rank}" if capture.rank else "ранг?",
                format_time(capture.time) if capture.time else "час?",
            ]
            label.setText(f"Race {n}: " + " · ".join(parts))
            label.setStyleSheet("")

        has_data = bool(session.races)
        self.review_button.setEnabled(has_data)
        self.discard_button.setEnabled(has_data)

    def open_review(self):
        CaptureReviewDialog(self).exec()

    def discard(self):
        APP_CONTEXT.challenge_session.clear()
