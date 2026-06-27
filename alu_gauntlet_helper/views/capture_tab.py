from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QAbstractItemView, QCheckBox, QFileDialog, QHBoxLayout,
                             QLabel, QListWidget, QMessageBox, QPushButton,
                             QVBoxLayout, QWidget)

from alu_gauntlet_helper import ui_lang
from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.challenge_session import RACE_COUNT, EffectiveRace
from alu_gauntlet_helper.services.races import RaceView
from alu_gauntlet_helper.utils.utils import format_time
from alu_gauntlet_helper.views.components.common import (CarInfoWidget, ListItemWidget,
                                                         RankClassBadge, TrackInfoWidget,
                                                         edit_icon_button, hbox, res_to_pixmap)
from alu_gauntlet_helper.views.overlay import Spinner
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

        track_text = ""
        if track:
            track_text = (WARN_ICON if e.track_uncertain else "") + track.display_name
        self.track_info = TrackInfoWidget(
            track.map_icon if track else "", track.icon if track else "",
            track.display_map_name if track else "", track_text)

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
        self.time_label.setObjectName("rowTimeLabel")
        self.time_label.setFont(time_font)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.bad_timing_label = QLabel()
        if e is not None and e.bad_timing:
            self.bad_timing_label.setPixmap(res_to_pixmap("icons/thumbs-down.svg", 18))

        self.note_label = QLabel()
        if e is not None and e.note:
            self.note_label.setPixmap(res_to_pixmap("icons/notepad-text.svg", 18))
            self.note_label.setToolTip(e.note)

        self.edit_button = edit_icon_button(lambda: on_edit(race_number))

        self.layout = QHBoxLayout(self)
        # half the default vertical padding to keep race rows compact
        margins = self.layout.contentsMargins()
        self.layout.setContentsMargins(margins.left(), margins.top() // 2, margins.right(), margins.bottom() // 2)
        self.layout.addWidget(self.checkbox, stretch=4)
        self.layout.addWidget(self.track_info, stretch=18)
        self.layout.addWidget(self.car_info, stretch=24)
        self.layout.addWidget(self.time_label, stretch=10)
        self.layout.addLayout(hbox([self.bad_timing_label, self.note_label], spacing=0), stretch=6)
        self.layout.addWidget(self.edit_button, stretch=0)
        self.setLayout(self.layout)


class CaptureTab(QWidget):
    """Стан сесії захоплення: рев'ю, редагування і збереження прямо в табі."""

    # стан кнопки Save (enabled) — дублюється кнопкою Save на оверлеї
    save_state_changed = pyqtSignal(bool)

    def __init__(self, recognize_file=None, toggle_overlay=None, capture=None,
                 cancel_pending=None):
        super().__init__()
        self.recognize_file = recognize_file
        self._cancel_pending = cancel_pending  # скасувати чергу капчура при Discard

        settings = APP_CONTEXT.settings.get()

        self.load_button = QPushButton(ui_lang.t("capture.load_screenshot"))
        self.load_button.setObjectName("secondary")
        self.load_button.clicked.connect(self.load_screenshot)

        self.capture_button = QPushButton(
            ui_lang.t("capture.capture_screen").format(hotkey=settings.capture_hotkey.upper()))
        if capture:
            self.capture_button.clicked.connect(capture)

        self.overlay_button = QPushButton(
            ui_lang.t("capture.toggle_overlay").format(hotkey=settings.overlay_hotkey.upper()))
        self.overlay_button.setObjectName("secondary")
        if toggle_overlay:
            self.overlay_button.clicked.connect(toggle_overlay)

        self.status_spinner = Spinner()  # крутиться поряд зі статусом під час розпізнавання
        self.status_label = QLabel()
        self.status_label.setObjectName("captureStatus")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        top = QHBoxLayout()
        top.addWidget(self.load_button)
        top.addWidget(self.capture_button)
        top.addWidget(self.overlay_button)
        top.addStretch()
        top.addWidget(self.status_spinner)
        top.addWidget(self.status_label)

        # ручні стани чекбоксів {race_number: bool}; немає ключа — авторежим (чекнуто, коли є час)
        self.manual_checks: dict[int, bool] = {}
        self._busy = False  # чи триває розпізнавання у фоні — тоді Discard активна навіть з порожнім списком

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)

        self.save_button = QPushButton(ui_lang.t("capture.save_selected"))
        self.save_button.clicked.connect(self.save_selected)
        self.discard_button = QPushButton(ui_lang.t("capture.discard_session"))
        self.discard_button.setObjectName("secondary")
        self.discard_button.clicked.connect(self.discard)

        self.warning_label = QLabel()
        self.warning_label.setTextFormat(Qt.TextFormat.RichText)
        self.warning_label.setWordWrap(True)
        self.warning_label.setVisible(False)

        buttons = QHBoxLayout()
        buttons.addWidget(self.warning_label, stretch=1)
        buttons.addStretch()
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.discard_button)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.list_widget)
        layout.addLayout(buttons)

        APP_CONTEXT.challenge_session.add_listener(self.refresh)
        self.refresh()

    def set_status(self, status: str):
        """Той самий статус, що й на оверлеї (Recognizing, …), праворуч від кнопок.
        Поки триває розпізнавання — поряд крутиться спінер."""
        if status.startswith("Recognizing"):
            self.status_spinner.start()
        else:
            self.status_spinner.stop()
        self.status_label.setText(status)

    def set_busy(self, busy: bool):
        """Розпізнавання у фоні: тримає Discard активною, щоб можна було скасувати
        чергу/in-flight ще до появи рядків у списку."""
        self._busy = busy
        self._update_buttons(self._effective_map())

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

        for n in range(1, RACE_COUNT + 1):
            e = effective.get(n)
            track = tracks.get(e.track_id) if e and e.track_id else None
            car = cars.get(e.car_id) if e and e.car_id else None
            row = CaptureRaceRow(n, e, track, car, self._is_checked(n, e),
                                 self.on_checkbox_toggled, self.open_edit)
            # рядки оновлюються на місці, без clear() — список не блимає і не стрибає
            if self.list_widget.count() < n:
                row.add_to_list(self.list_widget)
            else:
                row.replace_in_list(self.list_widget, n - 1)

        has_uncertain = any(e.track_uncertain or e.car_uncertain for e in effective.values())
        self.warning_label.setText(
            (WARN_ICON + ui_lang.t("capture.low_conf_warning")) if has_uncertain else "")
        self.warning_label.setVisible(has_uncertain)

        self._update_buttons(effective)

    def _update_buttons(self, effective: dict[int, EffectiveRace]):
        any_checked = False
        all_checked_complete = True
        for n in range(1, RACE_COUNT + 1):
            e = effective.get(n)
            if self._is_checked(n, e):
                any_checked = True
                if e is None or not e.is_complete:
                    all_checked_complete = False

        self.save_button.setEnabled(any_checked and all_checked_complete)
        self.save_state_changed.emit(self.save_button.isEnabled())
        self.discard_button.setEnabled(bool(effective) or self._busy)

    def on_checkbox_toggled(self, n: int, checked: bool):
        self.manual_checks[n] = checked  # після ручного кліку автологіка для гонки вимикається
        self._update_buttons(self._effective_map())  # сам чекбокс уже клікнуто — список не чіпаємо

    def load_screenshot(self):
        path, _ = QFileDialog.getOpenFileName(
            self, ui_lang.t("capture.load_screenshot"), "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path and self.recognize_file:
            self.recognize_file(path)

    def open_edit(self, n: int):
        e = APP_CONTEXT.challenge_session.effective(n)
        item = self._to_race_view(e) if e else RaceView()
        dialog = RaceDialog(item=item,
                            action=lambda r: APP_CONTEXT.challenge_session.set_draft(n, r),
                            parent=self, relaxed=True, title=ui_lang.t("capture.edit_race_n").format(n=n))
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
            map_name_ru=track.map_name_ru if track else "",
            track_name=track.name if track else "",
            track_name_ru=track.name_ru if track else "",
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
            QMessageBox.critical(self, ui_lang.t("capture.save_failed"), str(ex))
            return  # сесію не чистимо — можна виправити й повторити
        APP_CONTEXT.challenge_session.clear()

    def discard(self):
        box = QMessageBox(QMessageBox.Icon.Question, ui_lang.t("capture.discard_session"),
                          ui_lang.t("capture.discard_confirm"),
                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                          self)
        for btn in box.buttons():
            btn.setObjectName("secondary")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        if box.exec() == QMessageBox.StandardButton.Yes:
            if self._cancel_pending:
                self._cancel_pending()  # скинути чергу/in-flight, щоб не наповнили сесію назад
            APP_CONTEXT.challenge_session.clear()
