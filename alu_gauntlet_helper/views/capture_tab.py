from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QAbstractItemView, QCheckBox, QFileDialog, QHBoxLayout,
                             QLabel, QListWidget, QMessageBox, QPushButton,
                             QVBoxLayout, QWidget)

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.challenge_session import RACE_COUNT, EffectiveRace
from alu_gauntlet_helper.services.races import RaceView
from alu_gauntlet_helper.utils.utils import format_time
from alu_gauntlet_helper.views import style
from alu_gauntlet_helper.views.components.common import (CarInfoWidget, ListItemWidget,
                                                         RankClassBadge, hbox,
                                                         res_to_pixmap, vbox)
from alu_gauntlet_helper.views.races_tab import RaceDialog

WARN_ICON = '<span style="color: #FFC107;">⚠</span> '


class CaptureRaceRow(ListItemWidget):
    """Картка гонки в стилі races-таба: чекбокс, трек, авто з бейджем рангу, час + Edit."""

    def __init__(self, race_number: int, e: EffectiveRace | None, track, car,
                 checked: bool, on_toggle, on_edit, parent=None):
        super().__init__(race_number, parent)
        self.race_number = race_number

        self.checkbox = QCheckBox(str(race_number))
        self.checkbox.setEnabled(e is not None)
        self.checkbox.setChecked(checked)
        # clicked — тільки від кліку юзера; програмний setChecked його не емітить
        self.checkbox.clicked.connect(lambda c: on_toggle(race_number, c))

        self.map_label = QLabel(track.map_name if track else "")
        self.map_label.setStyleSheet(f"color: {style.TEXT_MUTED}; font-size: 12px;")
        track_text = ""
        if track:
            track_text = (WARN_ICON if e.track_uncertain else "") + track.name
        self.track_label = QLabel(track_text)
        self.track_label.setStyleSheet("font-weight: bold;")

        if e is not None:
            if e.rank:
                rank_widget = RankClassBadge(e.rank, car.max_rank if car else 0,
                                             car.car_class if car else "")
            else:
                rank_widget = QLabel("")
            if car:
                model_text = (WARN_ICON if e.car_uncertain else "") + (car.model or car.name)
                self.car_info = CarInfoWidget(car.icon, car.brand, model_text, rank_widget)
            else:
                self.car_info = CarInfoWidget("", "", e.car_name or "", rank_widget)
        else:
            self.car_info = QLabel("")

        time_font = QFont()
        time_font.setBold(True)
        time_font.setPointSize(self.font().pointSize() + 4)

        self.time_label = QLabel(format_time(e.time) if e is not None and e.time else "")
        self.time_label.setStyleSheet(f"color: {style.TIME_YELLOW};")
        self.time_label.setFont(time_font)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.bad_timing_label = QLabel()
        if e is not None and e.bad_timing:
            self.bad_timing_label.setPixmap(res_to_pixmap("icons/thumbs-down.svg", 18))

        self.note_label = QLabel()
        if e is not None and e.note:
            self.note_label.setPixmap(res_to_pixmap("icons/notepad-text.svg", 18))
            self.note_label.setToolTip(e.note)

        self.edit_button = QPushButton("Edit")
        self.edit_button.setObjectName("secondary")
        self.edit_button.clicked.connect(lambda: on_edit(race_number))

        self.layout = QHBoxLayout(self)
        # half the default vertical padding to keep race rows compact
        margins = self.layout.contentsMargins()
        self.layout.setContentsMargins(margins.left(), margins.top() // 2, margins.right(), margins.bottom() // 2)
        self.layout.addWidget(self.checkbox, stretch=4)
        self.layout.addLayout(vbox([self.map_label, self.track_label], spacing=3), stretch=18)
        self.layout.addWidget(self.car_info, stretch=24)
        self.layout.addWidget(self.time_label, stretch=10)
        self.layout.addLayout(hbox([self.bad_timing_label, self.note_label], spacing=0), stretch=6)
        self.layout.addWidget(self.edit_button, stretch=0)
        self.setLayout(self.layout)


class CaptureTab(QWidget):
    """Стан сесії захоплення: рев'ю, редагування і збереження прямо в табі."""

    def __init__(self, recognize_file=None, toggle_overlay=None):
        super().__init__()
        self.recognize_file = recognize_file

        settings = APP_CONTEXT.settings.get()

        self.load_button = QPushButton("Load screenshot")
        self.load_button.setObjectName("secondary")
        self.load_button.clicked.connect(self.load_screenshot)

        self.overlay_button = QPushButton(f"Toggle Overlay ({settings.overlay_hotkey.upper()})")
        self.overlay_button.setObjectName("secondary")
        if toggle_overlay:
            self.overlay_button.clicked.connect(toggle_overlay)

        hint = QLabel(f"Press <b>{settings.capture_hotkey.upper()}</b> to capture screen")
        hint.setStyleSheet(f"color: {style.TEXT_MUTED};")

        top = QHBoxLayout()
        top.addWidget(self.load_button)
        top.addWidget(self.overlay_button)
        top.addWidget(hint)
        top.addStretch()

        # ручні стани чекбоксів {race_number: bool}; немає ключа — авторежим (чекнуто, коли є час)
        self.manual_checks: dict[int, bool] = {}

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list_widget.itemDoubleClicked.connect(
            lambda item: self.open_edit(item.data(Qt.ItemDataRole.UserRole)))

        self.save_button = QPushButton("Save selected")
        self.save_button.clicked.connect(self.save_selected)
        self.discard_button = QPushButton("Discard session")
        self.discard_button.setObjectName("secondary")
        self.discard_button.clicked.connect(self.discard)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.discard_button)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.list_widget)
        layout.addLayout(buttons)

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

        self.list_widget.clear()
        any_checked = False
        all_checked_complete = True
        for n in range(1, RACE_COUNT + 1):
            e = effective.get(n)
            track = tracks.get(e.track_id) if e and e.track_id else None
            car = cars.get(e.car_id) if e and e.car_id else None
            checked = self._is_checked(n, e)
            CaptureRaceRow(n, e, track, car, checked,
                           self.on_checkbox_toggled, self.open_edit).add_to_list(self.list_widget)
            if checked:
                any_checked = True
                if e is None or not e.is_complete:
                    all_checked_complete = False

        self.save_button.setEnabled(any_checked and all_checked_complete)
        self.discard_button.setEnabled(bool(effective))

    def on_checkbox_toggled(self, n: int, checked: bool):
        self.manual_checks[n] = checked  # після ручного кліку автологіка для гонки вимикається
        self.refresh()

    def load_screenshot(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load screenshot", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path and self.recognize_file:
            self.recognize_file(path)

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
        answer = QMessageBox.question(self, "Discard session",
                                      "Discard all captured races?")
        if answer == QMessageBox.StandardButton.Yes:
            APP_CONTEXT.challenge_session.clear()
