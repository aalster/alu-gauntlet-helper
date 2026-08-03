from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QAbstractItemView, QHBoxLayout, QLabel, QListWidget,
                             QListWidgetItem, QMessageBox, QPushButton,
                             QStackedWidget, QTabBar, QVBoxLayout, QWidget)

from alu_gauntlet_helper import ui_lang
from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.challenge_session import (RACE_COUNT, ChallengeSessionService,
                                                            EffectiveRace)
from alu_gauntlet_helper.services.races import RaceView
from alu_gauntlet_helper.views import style
from alu_gauntlet_helper.views.components.common import WARN_ICON, ListItemWidget
from alu_gauntlet_helper.views.components.race_card import RaceCard
from alu_gauntlet_helper.views.components.vs_suggestion import VsSuggestionWidget
from alu_gauntlet_helper.views.races_tab import RaceDialog


class SessionView(QWidget):
    """Одна сесія челенджа: ряд з 5 карток гонок (з чекбоксом збереження, авто
    і моїм результатом прямо в картці) + список пропозицій вибраної гонки +
    низ (шанс перемоги, Авто, Save/Discard)."""

    save_state_changed = pyqtSignal(bool)

    def __init__(self, session: ChallengeSessionService, cancel_pending=None, parent=None):
        super().__init__(parent)
        self.session = session
        self._cancel_pending = cancel_pending
        self.selected_race = 1
        self.manual_checks: dict[int, bool] = {}
        self._busy = False

        # --- ряд карток гонок ---
        self.cards = [RaceCard(n, self.on_checkbox_toggled, self.open_edit)
                      for n in range(1, RACE_COUNT + 1)]
        cards_row = QHBoxLayout()
        cards_row.setSpacing(6)
        for card in self.cards:
            card.clicked.connect(self.select_race)
            cards_row.addWidget(card, stretch=1)

        # --- панель вибраної гонки ---
        self.suggestions = QListWidget()
        # SingleSelection: селекція item-а і є підсвіткою вибраного авто гонки
        # (з NoSelection setSelected ігнорується і підсвітка не працює)
        self.suggestions.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.suggestions.itemClicked.connect(self.on_suggestion_clicked)

        # --- низ ---
        # шанс перемоги: крупна кольорова цифра + підпис праворуч
        chance_font = QFont()
        chance_font.setBold(True)
        chance_font.setPointSize(self.font().pointSize() + 4)
        self.win_chance_value = QLabel("")
        self.win_chance_value.setFont(chance_font)
        self.win_chance_label = QLabel(ui_lang.t("assistant.win_chance"))
        self.win_chance_label.setVisible(False)
        self.warning_label = QLabel()
        self.warning_label.setTextFormat(Qt.TextFormat.RichText)
        self.warning_label.setWordWrap(True)
        self.warning_label.setVisible(False)

        self.auto_button = QPushButton(ui_lang.t("assistant.auto_pick"))
        self.auto_button.setObjectName("secondary")
        self.auto_button.clicked.connect(self.auto_pick)
        self.save_button = QPushButton(ui_lang.t("capture.save_selected"))
        self.save_button.clicked.connect(self.save_selected)
        self.discard_button = QPushButton(ui_lang.t("capture.discard_session"))
        self.discard_button.setObjectName("secondary")
        self.discard_button.clicked.connect(self.discard)

        bottom = QHBoxLayout()
        bottom.addWidget(self.warning_label, stretch=1)
        bottom.addWidget(self.win_chance_value)
        bottom.addWidget(self.win_chance_label)
        bottom.addStretch()
        bottom.addWidget(self.auto_button)
        bottom.addWidget(self.save_button)
        bottom.addWidget(self.discard_button)

        layout = QVBoxLayout(self)
        # відступи між трьома блоками (картки, рекомендації, футер) = паддінгу
        # таба (дефолтним маржинам цього layout) — рівний ритм по всій вкладці
        layout.setSpacing(layout.contentsMargins().left())
        layout.addLayout(cards_row)
        layout.addWidget(self.suggestions, stretch=1)
        layout.addLayout(bottom)

        self.refresh()

    # --- дані ---------------------------------------------------------------

    def _effective_map(self) -> dict[int, EffectiveRace]:
        return {n: e for n in range(1, RACE_COUNT + 1)
                if (e := self.session.effective(n)) is not None}

    def set_busy(self, busy: bool):
        self._busy = busy
        self._update_buttons(self._effective_map())

    def refresh(self):
        effective = self._effective_map()
        if not effective:
            self.manual_checks = {}

        track_ids = {e.track_id for e in effective.values() if e.track_id}
        cars_ids = {e.shown_car_id for e in effective.values() if e.shown_car_id}
        tracks = APP_CONTEXT.tracks_service.get_by_ids(track_ids)
        cars = APP_CONTEXT.cars_service.get_by_ids(cars_ids)

        for card in self.cards:
            n = card.race_number
            e = effective.get(n)
            track = tracks.get(e.track_id) if e and e.track_id else None
            # показане авто: фактичне (модалка/OCR) з e.car_id, інакше —
            # рекомендоване з окремого шару (e.suggested_car_id, з бейджем)
            shown_id = e.shown_car_id if e else 0
            car = cars.get(shown_id) if shown_id else None
            suggested = bool(e) and not e.has_car and e.suggested_car_id > 0
            beat = None
            if e and e.track_id and shown_id and e.opponent_time and not e.time:
                beat = APP_CONTEXT.assistant.beat_stats(e.track_id, shown_id, e.opponent_time)
            card.update_card(e, track, car, beat, checked=self._is_checked(n, e),
                             selected=(n == self.selected_race), suggested=suggested)

        self._refresh_suggestions(effective)

        chance = APP_CONTEXT.assistant.win_chance(self.session)
        if chance is not None:
            pct = round(chance * 100)
            color = (style.WIN_BRIGHT if pct > 75
                     else style.RANK_DOWN if pct > 50 else style.LOSS_BRIGHT)
            self.win_chance_value.setText(f"{pct}%")
            self.win_chance_value.setStyleSheet(f"color: {color};")
        else:
            self.win_chance_value.setText("")
        self.win_chance_label.setVisible(chance is not None)

        has_uncertain = any(e.track_uncertain or e.car_uncertain for e in effective.values())
        self.warning_label.setText(
            (WARN_ICON + ui_lang.t("capture.low_conf_warning")) if has_uncertain else "")
        self.warning_label.setVisible(has_uncertain)
        self._update_buttons(effective)

    def _refresh_suggestions(self, effective):
        self.suggestions.clear()
        e = effective.get(self.selected_race)
        if e is None or e.track_id <= 0:
            self._show_status(ui_lang.t("assistant.no_track_selected"))
            return
        opp = e.opponent_time or None
        items = APP_CONTEXT.assistant.aggregates_vs(e.track_id, opp)
        if not items:
            self._show_status(ui_lang.t("assistant.no_suggestions"))
            return
        # авто, зайняті іншими гонками (фактичні або рекомендовані)
        used_elsewhere = {ee.shown_car_id for m, ee in effective.items()
                          if m != self.selected_race and ee.shown_car_id}
        current = e.shown_car_id
        for agg, vs in items:
            w = VsSuggestionWidget(agg, vs, has_opponent_time=bool(opp))
            w.add_to_list(self.suggestions)
            w.set_dimmed(vs.car_id in used_elsewhere and vs.car_id != current)
        # виділити авто ЦІЄЇ гонки селекцією item-а
        for i in range(self.suggestions.count()):
            widget = self.suggestions.itemWidget(self.suggestions.item(i))
            if isinstance(widget, VsSuggestionWidget):
                self.suggestions.item(i).setSelected(widget.car_id == current)

    def _show_status(self, text: str):
        item = QListWidgetItem()
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        label = QLabel(text)
        label.setStyleSheet(f"color: {style.TEXT_MUTED};")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setContentsMargins(8, 16, 8, 16)
        # без ensurePolished sizeHint рахується ДО застосування QSS — item
        # отримує висоту в кілька пікселів (як у car_selection_tab.show_status)
        label.ensurePolished()
        hint = label.sizeHint()
        hint.setHeight(hint.height() + ListItemWidget.ITEM_CHROME_HEIGHT)
        item.setSizeHint(hint)
        self.suggestions.addItem(item)
        self.suggestions.setItemWidget(item, label)

    # --- дії ----------------------------------------------------------------

    def select_race(self, n: int):
        self.selected_race = n
        self.refresh()

    def on_suggestion_clicked(self, item: QListWidgetItem):
        widget = self.suggestions.itemWidget(item)
        if not isinstance(widget, VsSuggestionWidget):
            return
        e = self.session.effective(self.selected_race)
        # авто заїзду вже відоме (модалка/OCR) — рекомендації не клікаються;
        # refresh скидає селекцію, яку Qt встиг намалювати від самого кліку,
        # назад на фактичне авто
        if e is not None and e.has_car:
            self.refresh()
            return
        # авто, фактично проїхане в іншій гонці, вже витрачене — клік ігноруємо
        for m in range(1, RACE_COUNT + 1):
            if m == self.selected_race:
                continue
            em = self.session.effective(m)
            if em and em.car_id == widget.car_id and em.time > 0:
                self.refresh()
                return
        # повторний клік — зняти рекомендацію; клік по чужій/вільній — сюди
        current = e.suggested_car_id if e else 0
        self.session.set_assigned(self.selected_race,
                                  None if widget.car_id == current else widget.car_id)

    def auto_pick(self):
        APP_CONTEXT.assistant.auto_pick(self.session, force=True)

    def _is_checked(self, n: int, e: EffectiveRace | None) -> bool:
        if e is None:
            return False
        if n in self.manual_checks:
            return self.manual_checks[n]
        return e.time > 0

    def on_checkbox_toggled(self, n: int, checked: bool):
        self.manual_checks[n] = checked
        self._update_buttons(self._effective_map())

    def _update_buttons(self, effective):
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

    def open_edit(self, n: int):
        e = self.session.effective(n)
        item = self._to_race_view(e) if e else RaceView()
        # Guard: dialog.exec() крутить вкладений event loop — фоновий скан може
        # закрити цю сесію (Save/Discard в іншому табі); у застарілу сесію драфт не пишемо.
        dialog = RaceDialog(item=item,
                            action=lambda r: (self.session in APP_CONTEXT.session_manager.sessions
                                              and self.session.set_draft(n, r)),
                            parent=self, relaxed=True,
                            title=ui_lang.t("capture.edit_race_n").format(n=n))
        if e and e.car_id:
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
            return
        APP_CONTEXT.session_manager.close(self.session)

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


class AssistantTab(QWidget):
    """Таб асистента: таби сесій (видимі при >1) + SessionView активної/вибраної
    сесії. Кнопки захоплення й статус живуть у CaptureActionsWidget — кутовому
    віджеті таббара головного вікна."""

    save_state_changed = pyqtSignal(bool)

    def __init__(self, cancel_pending=None):
        super().__init__()
        self._cancel_pending = cancel_pending

        self.session_bar = QTabBar()
        self.session_bar.setExpanding(False)
        self.session_bar.currentChanged.connect(self._on_session_tab_changed)
        self.session_bar.hide()
        self.stack = QStackedWidget()
        self._views: list[SessionView] = []

        layout = QVBoxLayout(self)
        # нульові власні відступи: вкладений SessionView має свій QVBoxLayout з
        # дефолтними маржинами — без обнулення вони додавались би й паддінг таба
        # виходив удвічі більший, ніж в інших табів
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.session_bar)
        layout.addWidget(self.stack, stretch=1)

        APP_CONTEXT.session_manager.add_listener(self.refresh)
        self.refresh()

    # --- синхронізація зі списком сесій -------------------------------------

    def refresh(self):
        manager = APP_CONTEXT.session_manager
        sessions = manager.sessions
        if [v.session for v in self._views] != sessions:
            self._rebuild_views(sessions)
        for view in self._views:
            view.refresh()
        self._refresh_tab_titles()
        self._emit_save_state()

    def _rebuild_views(self, sessions):
        self.session_bar.blockSignals(True)
        was = self.stack.currentWidget()
        keep = {id(v.session): v for v in self._views}
        self._views = []
        while self.stack.count():
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            if w.session not in sessions:
                w.deleteLater()
        while self.session_bar.count():
            self.session_bar.removeTab(0)
        spawned_new = False
        for session in sessions:
            view = keep.get(id(session))
            if view is None:
                # конектимо лише новостворені view — перевикористані вже законектені
                # з попередньої перебудови, повторний connect дав би дубль-виклики
                view = SessionView(session, cancel_pending=self._cancel_pending)
                view.save_state_changed.connect(self._emit_save_state)
                spawned_new = True
            self._views.append(view)
            self.stack.addWidget(view)
            self.session_bar.addTab("")
        self.session_bar.setVisible(len(sessions) > 1)
        # Спека §2: «нова сесія стає активною, UI перемикається на неї» — якщо
        # цього циклу зʼявилась хоч одна нова сесія (конфлікт відщепив стару й
        # додав нову), показуємо саме її (вона завжди остання). Інакше — сесії
        # лише зникали (Save/Discard), тож лишаємо видиму без змін, якщо вона
        # ще жива, або останню, якщо саме вона й зникла.
        if spawned_new:
            current = self._views[-1]
        else:
            current = was if was in self._views else self._views[-1]
        self.stack.setCurrentWidget(current)
        self.session_bar.setCurrentIndex(self._views.index(current))
        self.session_bar.blockSignals(False)

    def _refresh_tab_titles(self):
        for i, view in enumerate(self._views):
            s = view.session
            if s is APP_CONTEXT.session_manager.active:
                title = ui_lang.t("assistant.session_current")
            else:
                title = ui_lang.t("assistant.session_paused").format(
                    time=s.created_at.strftime("%H:%M"), n=s.timed_count)
            self.session_bar.setTabText(i, title)

    def _on_session_tab_changed(self, idx: int):
        if 0 <= idx < self.stack.count():
            self.stack.setCurrentIndex(idx)
            self._emit_save_state()

    def _current_view(self) -> SessionView | None:
        w = self.stack.currentWidget()
        return w if isinstance(w, SessionView) else None

    def _emit_save_state(self):
        self.save_state_changed.emit(self.save_enabled())

    def save_enabled(self) -> bool:
        """Стан кнопки Save поточної (видимої) сесії — делегат до SessionView,
        бо власного save_button у AssistantTab більше немає (Task 10)."""
        view = self._current_view()
        return bool(view) and view.save_button.isEnabled()

    # --- контракт MainWindow (як у старого CaptureTab) -----------------------

    def set_busy(self, busy: bool):
        for view in self._views:
            view.set_busy(busy)

    def save_selected(self):
        view = self._current_view()
        if view:
            view.save_selected()
