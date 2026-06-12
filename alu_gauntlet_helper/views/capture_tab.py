from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QHBoxLayout, QLabel, QMessageBox,
                             QPushButton, QVBoxLayout, QWidget)

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.challenge_session import RACE_COUNT, EffectiveRace
from alu_gauntlet_helper.services.races import RaceView
from alu_gauntlet_helper.utils.utils import format_time
from alu_gauntlet_helper.views import style
from alu_gauntlet_helper.views.components.common import res_to_pixmap
from alu_gauntlet_helper.views.races_tab import RaceDialog

WARN_ICON = '<span style="color: #FFC107;">⚠</span> '


class CaptureRaceRow(QWidget):
    """Рядок гонки: чекбокс вибору + ефективні значення + іконки bad_timing/note + Edit."""

    def __init__(self, race_number: int, on_toggle, on_edit):
        super().__init__()
        self.race_number = race_number

        self.checkbox = QCheckBox()
        # clicked — тільки від кліку юзера; програмний setChecked його не емітить
        self.checkbox.clicked.connect(lambda checked: on_toggle(race_number, checked))

        self.label = QLabel()
        self.label.setTextFormat(Qt.TextFormat.RichText)

        self.bad_timing_icon = QLabel()
        self.bad_timing_icon.setPixmap(res_to_pixmap("icons/dislike.png", 18))
        self.note_icon = QLabel()
        self.note_icon.setPixmap(res_to_pixmap("icons/info.png", 18))

        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(lambda: on_edit(race_number))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.checkbox)
        layout.addWidget(self.label, stretch=1)
        layout.addWidget(self.bad_timing_icon)
        layout.addWidget(self.note_icon)
        layout.addWidget(self.edit_button)

    def update_row(self, e: EffectiveRace | None, track_name: str, car_name: str, checked: bool):
        self.checkbox.setEnabled(e is not None)
        self.checkbox.setChecked(checked)
        self.bad_timing_icon.setVisible(bool(e and e.bad_timing))
        self.note_icon.setVisible(bool(e and e.note))
        self.note_icon.setToolTip(e.note if e else "")
        if e is None:
            self.label.setText(f"Race {self.race_number}: —")
            self.label.setStyleSheet(f"color: {style.TEXT_MUTED};")
            return
        parts = [
            (WARN_ICON if e.track_uncertain else "") + (track_name or "трек?"),
            (WARN_ICON if e.car_uncertain else "") + (car_name or "авто?"),
            f"rank {e.rank}" if e.rank else "ранг?",
            format_time(e.time) if e.time else "час?",
        ]
        self.label.setText(f"Race {self.race_number}: " + " · ".join(parts))
        self.label.setStyleSheet("")


class CaptureTab(QWidget):
    """Стан сесії захоплення: рев'ю, редагування і збереження прямо в табі."""

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

        # ручні стани чекбоксів {race_number: bool}; немає ключа — авторежим (чекнуто, коли є час)
        self.manual_checks: dict[int, bool] = {}

        self.rows = [CaptureRaceRow(n, self.on_checkbox_toggled, self.open_edit)
                     for n in range(1, RACE_COUNT + 1)]

        self.save_button = QPushButton("Save selected")
        self.save_button.clicked.connect(self.save_selected)
        self.discard_button = QPushButton("Discard session")
        self.discard_button.clicked.connect(self.discard)

        buttons = QHBoxLayout()
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.discard_button)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        for row in self.rows:
            layout.addWidget(row)
        layout.addLayout(buttons)
        layout.addStretch()

        APP_CONTEXT.challenge_session.add_listener(self.refresh)
        self.refresh()

    def _effective_map(self) -> dict[int, EffectiveRace]:
        session = APP_CONTEXT.challenge_session
        return {n: e for n in range(1, RACE_COUNT + 1) if (e := session.effective(n)) is not None}

    def _is_checked(self, n: int, e: EffectiveRace | None) -> bool:
        if e is None:
            return False
        if n in self.manual_checks:
            return self.manual_checks[n]
        return e.time > 0

    def refresh(self):
        effective = self._effective_map()
        if not effective:
            self.manual_checks = {}  # сесію скинуто — чекбокси назад в авторежим

        track_ids = {e.track_id for e in effective.values() if e.track_id}
        car_ids = {e.car_id for e in effective.values() if e.car_id}
        tracks = APP_CONTEXT.tracks_service.get_by_ids(track_ids)
        cars = APP_CONTEXT.cars_service.get_by_ids(car_ids)

        any_checked = False
        all_checked_complete = True
        for row in self.rows:
            n = row.race_number
            e = effective.get(n)
            track = tracks.get(e.track_id) if e and e.track_id else None
            car = cars.get(e.car_id) if e and e.car_id else None
            track_name = f"{track.map_name} - {track.name}" if track else ""
            car_name = car.name if car else (e.car_name if e else "")
            checked = self._is_checked(n, e)
            row.update_row(e, track_name, car_name, checked)
            if checked:
                any_checked = True
                if e is None or not e.is_complete:
                    all_checked_complete = False

        self.save_button.setEnabled(any_checked and all_checked_complete)
        self.discard_button.setEnabled(bool(effective))

    def on_checkbox_toggled(self, n: int, checked: bool):
        self.manual_checks[n] = checked  # після ручного кліку автологіка для гонки вимикається
        self.refresh()

    def open_edit(self, n: int):
        e = APP_CONTEXT.challenge_session.effective(n)
        item = self._to_race_view(e) if e else RaceView()
        dialog = RaceDialog(item=item,
                            action=lambda r: APP_CONTEXT.challenge_session.set_draft(n, r),
                            parent=self, relaxed=True, title=f"Edit Race {n}")
        if e and e.car_id:
            # RaceDialog не виставляє selected_item для авто з item.car_id (на відміну від треку),
            # без цього car_id губиться при незмінному полі — авто перерезолвиться за назвою
            car = APP_CONTEXT.cars_service.get_by_ids({e.car_id}).get(e.car_id)
            if car:
                dialog.cars_completer.set_selected_item(car)
        dialog.exec()  # set_draft → _notify → refresh

    @staticmethod
    def _to_race_view(e: EffectiveRace) -> RaceView:
        track = APP_CONTEXT.tracks_service.get_by_ids({e.track_id}).get(e.track_id) if e.track_id else None
        car = APP_CONTEXT.cars_service.get_by_ids({e.car_id}).get(e.car_id) if e.car_id else None
        return RaceView(
            track_id=e.track_id, car_id=e.car_id, rank=e.rank, time=e.time,
            bad_timing=e.bad_timing, note=e.note,
            map_name=track.map_name if track else "",
            track_name=track.name if track else "",
            car_name=car.name if car else e.car_name,
        )

    def save_selected(self):
        effective = self._effective_map()
        races = [
            RaceView(track_id=e.track_id, car_id=e.car_id, car_name=e.car_name,
                     rank=e.rank, time=e.time, bad_timing=e.bad_timing, note=e.note)
            for n, e in effective.items() if self._is_checked(n, e)
        ]
        try:
            for race in races:
                APP_CONTEXT.races_service.save(race)
        except Exception as ex:
            QMessageBox.critical(self, "Save failed", str(ex))
            return  # сесію не чистимо — можна виправити й повторити
        APP_CONTEXT.challenge_session.clear()

    def discard(self):
        APP_CONTEXT.challenge_session.clear()
