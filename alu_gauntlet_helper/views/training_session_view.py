from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (QCheckBox, QHBoxLayout, QLabel, QListWidget,
                             QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout,
                             QWidget)

from alu_gauntlet_helper import ui_lang
from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.challenge_session import EffectiveRace
from alu_gauntlet_helper.services.races import RaceView
from alu_gauntlet_helper.services.training_session import TrainingSessionService
from alu_gauntlet_helper.utils.utils import format_time, get_resource_path
from alu_gauntlet_helper.views import style
from alu_gauntlet_helper.views.components.common import (WARN_ICON, CarInfoWidget,
                                                         ListItemWidget, RankClassBadge,
                                                         TrackInfoWidget, as_column,
                                                         edit_icon_button, hbox,
                                                         res_to_pixmap)
from alu_gauntlet_helper.views.races_tab import RaceDialog


class TrainingRunWidget(ListItemWidget):
    """Рядок заїзду тренування — як рядок вкладки «Заїзди» (без групування),
    але без колонки треку (він у шапці сесії) і з чекбоксом збереження."""

    def __init__(self, number: int, e: EffectiveRace, car, checked: bool,
                 on_toggle, on_dislike, on_edit, parent=None):
        super().__init__(e, parent)
        self.number = number

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(checked)
        # clicked — тільки від кліку юзера, програмний setChecked його не емітить
        self.checkbox.clicked.connect(lambda c: on_toggle(number, c))

        number_font = QFont()
        number_font.setBold(True)
        self.number_label = QLabel(str(number))
        self.number_label.setFont(number_font)
        self.number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # двозначні номери не повинні зсувати колонки сусідніх рядків
        self.number_label.setMinimumWidth(
            self.number_label.fontMetrics().horizontalAdvance("00"))

        badge = RankClassBadge(0, 0, car.car_class if car else "")
        warn = WARN_ICON if e.car_uncertain else ""
        self.car_info = CarInfoWidget(car.icon if car else "",
                                      car.brand if car else "",
                                      (warn + car.model) if car else (e.car_name or "?"),
                                      badge)

        time_font = QFont()
        time_font.setBold(True)
        time_font.setPointSize(self.font().pointSize() + 4)
        self.time_label = QLabel(format_time(e.time) or "—")
        self.time_label.setObjectName("rowTimeLabel")
        self.time_label.setFont(time_font)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setContentsMargins(12, 0, 12, 0)

        # 👎 — прямий перемикач «некоректний час», як на оверлеї
        self.dislike_button = QPushButton()
        self.dislike_button.setObjectName("iconToggle")
        self.dislike_button.setIcon(QIcon(get_resource_path("icons/thumbs-down.svg")))
        self.dislike_button.setIconSize(QSize(18, 18))
        self.dislike_button.setCheckable(True)
        self.dislike_button.setChecked(e.bad_timing)
        self.dislike_button.setToolTip(ui_lang.t("races.bad_timing"))
        self.dislike_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dislike_button.setFixedSize(30, 30)
        self.dislike_button.clicked.connect(lambda: on_dislike(number))

        # слот 18×18 резервується завжди — як у списку заїздів
        self.info_label = QLabel()
        self.info_label.setFixedSize(18, 18)
        if e.note:
            self.info_label.setPixmap(res_to_pixmap("icons/notepad-text.svg", 18))
            self.info_label.setToolTip(e.note)

        self.layout = QHBoxLayout(self)
        margins = self.layout.contentsMargins()
        self.layout.setContentsMargins(margins.left(), margins.top() // 2,
                                       margins.right(), margins.bottom() // 2)
        self.layout.addWidget(self.checkbox)
        self.layout.addWidget(as_column(self.number_label), stretch=8)
        self.layout.addWidget(as_column(self.car_info), stretch=140,
                              alignment=Qt.AlignmentFlag.AlignVCenter)
        self.layout.addWidget(self.time_label)
        icons = QWidget()
        icons.setLayout(hbox([self.dislike_button, self.info_label], spacing=8))
        self.layout.addWidget(icons)
        self.layout.addStretch(50)
        self.layout.addWidget(edit_icon_button(lambda: on_edit(number)))
        self.setLayout(self.layout)


class TrainingSessionView(QWidget):
    """Сесія тренування: шапка з треком (він один на сесію) + список заїздів,
    що росте, + низ (Save/Discard). Контракт для AssistantTab — той самий, що
    в SessionView (session, refresh, set_busy, save_selected, save_button)."""

    save_state_changed = pyqtSignal(bool)

    def __init__(self, session: TrainingSessionService, cancel_pending=None, parent=None):
        super().__init__(parent)
        self.session = session
        self._cancel_pending = cancel_pending
        self.manual_checks: dict[int, bool] = {}
        self._busy = False

        # --- шапка: трек сесії ---
        self.header_row = QHBoxLayout()
        self.header_row.setContentsMargins(0, 0, 0, 0)
        self.track_info: TrackInfoWidget = TrackInfoWidget("", "", "", "")
        self.header_row.addWidget(self.track_info)
        self.header_row.addStretch()

        # --- список заїздів ---
        self.runs_list = QListWidget()
        self.runs_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)

        # --- низ ---
        self.warning_label = QLabel()
        self.warning_label.setTextFormat(Qt.TextFormat.RichText)
        self.warning_label.setWordWrap(True)
        self.warning_label.setVisible(False)

        self.save_button = QPushButton(ui_lang.t("capture.save_selected"))
        self.save_button.clicked.connect(self.save_selected)
        self.discard_button = QPushButton(ui_lang.t("capture.discard_session"))
        self.discard_button.setObjectName("secondary")
        self.discard_button.clicked.connect(self.discard)

        bottom = QHBoxLayout()
        bottom.addWidget(self.warning_label, stretch=1)
        bottom.addStretch()
        bottom.addWidget(self.discard_button)
        bottom.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.setSpacing(layout.contentsMargins().left())
        layout.addLayout(self.header_row)
        layout.addWidget(self.runs_list, stretch=1)
        layout.addLayout(bottom)

        self.refresh()

    # --- дані ---------------------------------------------------------------

    def _effective_map(self) -> dict[int, EffectiveRace]:
        return {n: e for n in self.session.run_numbers()
                if (e := self.session.effective(n)) is not None}

    def track_title(self) -> str:
        """«Карта - Трек» для заголовка таба; без треку — заглушка/карта."""
        if self.session.track:
            track = APP_CONTEXT.tracks_service.get_by_ids(
                {self.session.track.value}).get(self.session.track.value)
            if track:
                return f"{track.display_map_name} - {track.display_name}"
        if self.session.map:
            map_ = APP_CONTEXT.maps_service.get_by_ids(
                {self.session.map.value}).get(self.session.map.value)
            if map_:
                return map_.display_name
        return ui_lang.t("training.unknown_track")

    def set_busy(self, busy: bool):
        self._busy = busy
        self._update_buttons(self._effective_map())

    def refresh(self):
        effective = self._effective_map()
        if not effective:
            self.manual_checks = {}

        self._refresh_header()
        self._refresh_runs(effective)

        has_uncertain = any(e.track_uncertain or e.car_uncertain for e in effective.values())
        self.warning_label.setText(
            (WARN_ICON + ui_lang.t("capture.low_conf_warning")) if has_uncertain else "")
        self.warning_label.setVisible(has_uncertain)
        self._update_buttons(effective)

    def _refresh_header(self):
        track = None
        if self.session.track:
            track = APP_CONTEXT.tracks_service.get_by_ids(
                {self.session.track.value}).get(self.session.track.value)
        # TrackInfoWidget не оновлюється — замінюємо, як на картці гонки
        old = self.track_info
        if track:
            warn = WARN_ICON if self.session.track.score < 0.85 else ""
            self.track_info = TrackInfoWidget(track.map_icon, track.icon,
                                              track.display_map_name,
                                              warn + track.display_name)
        else:
            self.track_info = TrackInfoWidget("", "", "",
                                              ui_lang.t("training.no_track_hint"))
        self.header_row.replaceWidget(old, self.track_info)
        old.deleteLater()

    def _refresh_runs(self, effective: dict[int, EffectiveRace]):
        self.runs_list.clear()
        if not effective:
            item = QListWidgetItem()
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            label = QLabel(ui_lang.t("training.no_runs"))
            label.setStyleSheet(f"color: {style.TEXT_MUTED};")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setContentsMargins(8, 16, 8, 16)
            label.ensurePolished()
            hint = label.sizeHint()
            hint.setHeight(hint.height() + ListItemWidget.ITEM_CHROME_HEIGHT)
            item.setSizeHint(hint)
            self.runs_list.addItem(item)
            self.runs_list.setItemWidget(item, label)
            return
        car_ids = {e.car_id for e in effective.values() if e.car_id}
        cars = APP_CONTEXT.cars_service.get_by_ids(car_ids)
        for n, e in sorted(effective.items()):
            car = cars.get(e.car_id) if e.car_id else None
            TrainingRunWidget(n, e, car, checked=self._is_checked(n, e),
                              on_toggle=self.on_checkbox_toggled,
                              on_dislike=self.session.toggle_bad_timing,
                              on_edit=self.open_edit).add_to_list(self.runs_list)
        # найсвіжіший заїзд — унизу списку: тримаємо його на видноті
        self.runs_list.scrollToBottom()

    # --- дії ----------------------------------------------------------------

    def _is_checked(self, n: int, e: EffectiveRace | None) -> bool:
        if e is None:
            return False
        if n in self.manual_checks:
            return self.manual_checks[n]
        return e.is_complete

    def on_checkbox_toggled(self, n: int, checked: bool):
        self.manual_checks[n] = checked
        self._update_buttons(self._effective_map())

    def _update_buttons(self, effective: dict[int, EffectiveRace]):
        any_checked = False
        all_checked_complete = True
        for n, e in effective.items():
            if self._is_checked(n, e):
                any_checked = True
                if not e.is_complete:
                    all_checked_complete = False
        self.save_button.setEnabled(any_checked and all_checked_complete)
        self.save_state_changed.emit(self.save_button.isEnabled())
        self.discard_button.setEnabled(bool(effective) or self.session.track is not None
                                       or self._busy)

    def open_edit(self, n: int):
        e = self.session.effective(n)
        if e is None:
            return
        item = self._to_race_view(e)
        # Guard: dialog.exec() крутить вкладений event loop — фоновий скан може
        # закрити цю сесію; у застарілу сесію драфт не пишемо.
        dialog = RaceDialog(item=item,
                            action=lambda r: (self.session in APP_CONTEXT.session_manager.sessions
                                              and self.session.set_draft(n, r)),
                            parent=self, relaxed=True,
                            title=ui_lang.t("training.run_n").format(n=n))
        if e.car_id:
            car = APP_CONTEXT.cars_service.get_by_ids({e.car_id}).get(e.car_id)
            if car:
                dialog.cars_completer.set_selected_item(car)
        dialog.exec()

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
        to_save = {n: e for n, e in effective.items() if self._is_checked(n, e)}
        if not to_save:
            return
        try:
            for e in to_save.values():
                APP_CONTEXT.races_service.save(RaceView(
                    track_id=e.track_id, car_id=e.car_id, car_name=e.car_name,
                    rank=e.rank, time=e.time, bad_timing=e.bad_timing, note=e.note))
        except Exception as ex:
            QMessageBox.critical(self, ui_lang.t("capture.save_failed"), str(ex))
            return
        # збережені заїзди зникають зі списку; сесія з треком живе далі —
        # можна їхати ще (несумісний скан потім сам її замінить/відщепить)
        for n in to_save:
            self.manual_checks.pop(n, None)
        self.session.remove_runs(list(to_save))

    def discard(self):
        box = QMessageBox(QMessageBox.Icon.Question, ui_lang.t("capture.discard_session"),
                          ui_lang.t("capture.discard_confirm"),
                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, self)
        for btn in box.buttons():
            btn.setObjectName("secondary")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        if box.exec() == QMessageBox.StandardButton.Yes:
            if self._cancel_pending and self.session is APP_CONTEXT.session_manager.active:
                self._cancel_pending()
            APP_CONTEXT.session_manager.close(self.session)
