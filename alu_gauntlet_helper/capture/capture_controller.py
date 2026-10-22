import queue
import threading
import traceback

import cv2
import numpy as np
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from alu_gauntlet_helper import game_lang, ui_lang
from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.capture.hotkey import GlobalHotkeyService
from alu_gauntlet_helper.capture.screen_grab import grab_screen, save_capture
from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.engine import RecognitionEngine
from alu_gauntlet_helper.screen_recognition.map_icon_matcher import MapIconMatcher
from alu_gauntlet_helper.screen_recognition.matching import TrackResolver, build_car_matcher
from alu_gauntlet_helper.screen_recognition.screens.before_race import BeforeRaceExtractor
from alu_gauntlet_helper.screen_recognition.screens.challenge_accordion import ChallengeAccordionExtractor
from alu_gauntlet_helper.screen_recognition.screens.challenge_complete import ChallengeCompleteExtractor
from alu_gauntlet_helper.screen_recognition.screens.opponent_scout import OpponentScoutExtractor
from alu_gauntlet_helper.screen_recognition.screens.race_result import RaceResultExtractor
from alu_gauntlet_helper.screen_recognition.screens.training_lobby import TrainingLobbyExtractor
from alu_gauntlet_helper.screen_recognition.screens.training_result import TrainingResultExtractor
from alu_gauntlet_helper.services.challenge_session import (LOW_CONFIDENCE, RACE_COUNT,
                                                            visible_goals)
from alu_gauntlet_helper.services.training_session import TrainingSessionService
from alu_gauntlet_helper.views.components.chip_tooltip import goal_label
from alu_gauntlet_helper.views.overlay import (OverlayWindow, build_races_table,
                                               build_training_table, header_text)

OVERLAY_HIDE_DELAY_MS = 80


class CaptureController(QObject):
    """Хоткей → скрін → розпізнавання (фоновий потік) → сесія → оверлей."""

    _capture_requested = pyqtSignal()
    _overlay_toggle_requested = pyqtSignal()
    _actions_enter_requested = pyqtSignal()  # комбо натиснуто — увімкнути керування оверлеєм
    _actions_exit_requested = pyqtSignal()   # комбо відпущено — зафіксувати позицію й зберегти
    _recognized = pyqtSignal(object, int)  # (RecognitionResult | None, epoch покоління)
    status_changed = pyqtSignal(str)  # поточний статус для UI (той самий, що й на оверлеї)
    busy_changed = pyqtSignal(bool)   # чи триває розпізнавання у фоні (in_flight > 0)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.overlay = OverlayWindow()
        self.hotkeys = GlobalHotkeyService()
        self._busy = False  # True лише поки оверлей сховано й триває граб
        self._status = ""
        self._in_flight = 0  # скрінів у черзі/на розпізнаванні (лише UI-потік)
        self._epoch = 0  # «покоління» сесії: Discard інкрементує, застарілі результати ігноруємо

        # Один довгоживучий воркер серіалізує OCR: грабити можна під час
        # розпізнавання попередніх кадрів, але самі розпізнавання — по одному.
        self._queue: queue.Queue = queue.Queue()
        self._worker = threading.Thread(target=self._recognition_loop, daemon=True)
        self._worker.start()

        self._capture_requested.connect(self._on_capture_requested)
        self._overlay_toggle_requested.connect(self.toggle_overlay)
        self._actions_enter_requested.connect(self._enter_actions_mode)
        self._actions_exit_requested.connect(self._exit_actions_mode)
        self._recognized.connect(self._on_recognized)
        # ✕ на оверлеї — просто сховати (сесія лишається); Save вмикає MainWindow,
        # бо повністю дублює кнопку таба CAPTURE
        self.overlay.close_requested.connect(self.overlay.hide)
        self.overlay.capture_requested.connect(self.capture_now)
        # 👎 у рядку таблиці — фліп bad_timing у сесії; listener сам оновить оверлей
        self.overlay.dislike_toggled.connect(self._toggle_bad_timing)
        # режим 3/5 · 4/5 · 5/5 (Ctrl+Alt) — той самий, що й у табі асистента
        self.overlay.goal_selected.connect(self._set_goal)
        APP_CONTEXT.session_manager.add_listener(self._refresh_overlay)

    def apply_settings(self) -> bool:
        """(Пере)реєструє хоткеї та tesseract зі збережених налаштувань. False — хоткей не став."""
        settings = APP_CONTEXT.settings.get()
        ocr.configure_tesseract()
        self.hotkeys.unregister_all()
        # реєструємо всі три завжди (без short-circuit), щоб збій одного
        # не лишив інші непідключеними
        ok = self.hotkeys.register(settings.capture_hotkey, self._capture_requested.emit)
        ok = self.hotkeys.register(settings.overlay_hotkey, self._overlay_toggle_requested.emit) and ok
        actions_keys = [k for k in settings.overlay_actions_hotkey.split("+") if k]
        ok = self.hotkeys.register_hold(actions_keys, self._actions_enter_requested.emit,
                                        self._actions_exit_requested.emit) and ok
        self.overlay.set_screen_index(settings.capture_monitor)
        self.overlay.set_opacity(settings.overlay_opacity)
        if settings.overlay_anchored:
            self.overlay.set_anchor(settings.overlay_anchor_x, settings.overlay_anchor_y,
                                    settings.overlay_anchor_right, settings.overlay_anchor_bottom)
        else:
            self.overlay.clear_position()
        return ok

    def shutdown(self):
        APP_CONTEXT.session_manager.remove_listener(self._refresh_overlay)
        self.hotkeys.unregister_all()
        self._queue.put(None)  # sentinel — зупиняє воркер

    # --- захоплення -----------------------------------------------------

    def capture_now(self):
        """Програмний тригер захоплення — те саме, що й хоткей."""
        self._capture_requested.emit()

    def _on_capture_requested(self):
        if self._busy:
            return
        self._busy = True
        self.overlay.hide()  # щоб оверлей не потрапив у кадр
        QTimer.singleShot(OVERLAY_HIDE_DELAY_MS, self._do_grab)

    def _do_grab(self):
        settings = APP_CONTEXT.settings.get()
        try:
            img = grab_screen(settings.capture_monitor)
        except Exception:
            traceback.print_exc()
            self._busy = False
            self._set_status(ui_lang.t("status.screenshot_failed"))
            return

        # граб завершено — оверлей можна повертати й приймати наступні F8,
        # розпізнавання поставленого в чергу кадру триватиме у фоні.
        # Скрін зберігаємо вже після розпізнавання — лише якщо дані не
        # розпізнались або розпізнались з низькою впевненістю (див. _recognition_loop)
        self._busy = False
        self._enqueue(self._build_engine(), img, save_if_uncertain=settings.save_captures)

    def recognize_file(self, path: str):
        """Розпізнавання скріншота з файлу — той самий пайплайн, що й захоплення хоткеєм."""
        # cv2.imread мовчки падає на не-ASCII шляхах у Windows, тому imdecode
        img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            self._set_status(ui_lang.t("status.load_failed"))
            return
        self._enqueue(self._build_engine(), img)

    def _enqueue(self, engine: RecognitionEngine, img, save_if_uncertain: bool = False):
        """Ставить кадр у чергу розпізнавання й оновлює лічильник/оверлей (UI-потік)."""
        self._in_flight += 1
        self._queue.put((engine, img, save_if_uncertain, self._epoch))
        self._refresh_overlay(show=True)  # старт розпізнавання — оверлей показуємо

    def cancel_pending(self):
        """Скасовує всі кадри в черзі/на розпізнаванні (Discard session) — щоб вони
        не наповнили сесію назад. Кадр, що вже в роботі, дороблюється у фоні, але
        його результат відкидається в _on_recognized за «поколінням» (epoch)."""
        self._epoch += 1
        while True:  # викидаємо ще не взяті в роботу кадри
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        self._in_flight = 0
        self._status = ""
        self._refresh_overlay()

    def _recognition_loop(self):
        """Фоновий воркер: розпізнає кадри з черги по одному, у порядку захоплення."""
        while True:
            item = self._queue.get()
            if item is None:  # sentinel зі shutdown
                break
            engine, img, save_if_uncertain, epoch = item
            result = None
            try:
                if not ocr.is_available():
                    print("Tesseract is not available")
                else:
                    result = engine.recognize(img)
            except Exception:
                traceback.print_exc()
            # зберігаємо скрін лише тоді, коли є що ловити для рев'ю:
            # дані не розпізнались або хоч одне поле — з низькою впевненістю
            if save_if_uncertain and self._is_uncertain(result):
                try:
                    save_capture(img)
                except Exception:
                    traceback.print_exc()
            try:
                self._recognized.emit(result, epoch)
            except RuntimeError:
                # QObject знищено під час завершення застосунку
                pass

    @staticmethod
    def _is_uncertain(result) -> bool:
        """True, якщо скрін не розпізнано або якесь поле має score нижче порога ворнінга."""
        if result is None or not result.captures:
            return True
        for c in result.captures:
            if c.track and c.track.score < LOW_CONFIDENCE:
                return True
            if c.car and c.car.score < LOW_CONFIDENCE:
                return True
            if c.opponent_car and c.opponent_car.score < LOW_CONFIDENCE:
                return True
        return False

    @staticmethod
    def _build_engine() -> RecognitionEngine:
        # словники будуються на кожне захоплення — завжди свіжі дані з БД
        track_resolver = TrackResolver(APP_CONTEXT.tracks_service.get_all_views())
        car_matcher = build_car_matcher(APP_CONTEXT.cars_service.get_all())
        map_matcher = MapIconMatcher(APP_CONTEXT.maps_service.autocomplete(""))
        # Кожен екстрактор має дешевий піксельний гейт (0 OCR), що відсікає явно
        # чужі екрани до будь-якого OCR (див. docs/optimizing-recognition-speed.md,
        # «Піксельні гейти екранів»). Порядок — за залишковою ціною відмови на
        # кадрі, що проскочив гейт: race_result/challenge_complete дешеві,
        # акордеон із запасним OCR-пошуком найдорожчий — лишається останнім.
        # training_result — ПЕРЕД race_result: піксельний гейт race_result
        # пропускає екран результату тренування (яскрава плашка RACE RESULTS у
        # регіоні заголовка) і відсікає його лише дорогим OCR-якорем "RACE N".
        return RecognitionEngine([
            TrainingResultExtractor(car_matcher),
            RaceResultExtractor(car_matcher),
            ChallengeCompleteExtractor(car_matcher),
            TrainingLobbyExtractor(track_resolver),
            BeforeRaceExtractor(track_resolver, car_matcher),
            OpponentScoutExtractor(track_resolver, map_matcher),
            ChallengeAccordionExtractor(track_resolver, car_matcher),
        ])

    def _on_recognized(self, result, epoch):
        if epoch != self._epoch:
            return  # результат скасованої (Discard) сесії — ігноруємо
        self._in_flight = max(0, self._in_flight - 1)
        if result is None:
            # _set_status сам зробить refresh; "Recognizing" далі має пріоритет,
            # поки лишаються кадри в роботі
            self._set_status(ui_lang.t("status.not_recognized"))
            return
        self._status = ""
        if result.game_language:
            self._apply_game_language(result.game_language)
        APP_CONTEXT.session_manager.apply(result)  # listener оновить оверлей

    @staticmethod
    def _toggle_bad_timing(race_number: int):
        # 👎 з оверлея завжди стосується активної сесії
        APP_CONTEXT.session_manager.active.toggle_bad_timing(race_number)

    def _set_goal(self, goal: int):
        # режим живе в активній сесії челенджа; listener сесії оновить і оверлей,
        # і таб асистента
        session = APP_CONTEXT.session_manager.active
        if isinstance(session, TrainingSessionService):
            return
        if goal != session.goal:
            APP_CONTEXT.assistant.set_goal(session, goal)

    @staticmethod
    def _apply_game_language(language: str):
        """Авто-перемикання мови гри за розпізнаним екраном (симетрично EN↔RU):
        зберігаємо в налаштування й оновлюємо відображення назв по всьому застосунку."""
        if game_lang.current_game_language() == language:
            return
        settings = APP_CONTEXT.settings.get()
        settings.game_language = language
        APP_CONTEXT.settings.save(settings)
        game_lang.set_game_language(language)

    # --- оверлей ---------------------------------------------------------

    def toggle_overlay(self):
        if self.overlay.isVisible():
            self.overlay.hide()
        else:
            # перше ручне відкриття: оверлей ще порожній, тож спершу наповнюємо
            # рядками з сесії ("N — no data", коли даних немає); show=True покаже вікно
            self._refresh_overlay(show=True)

    def _enter_actions_mode(self):
        """Комбо затиснуто — увімкнути керування оверлеєм (перетягування + кнопки)."""
        if self.overlay.is_actions_mode():
            return
        if not self.overlay.isVisible():
            return  # схований оверлей за комбо не відкриваємо
        self.overlay.set_actions_mode(True)
        self._refresh_overlay()  # перерендерити (кнопки замість хоткеїв)

    def _exit_actions_mode(self):
        """Комбо відпущено — зафіксувати позицію й зберегти."""
        if not self.overlay.is_actions_mode():
            return
        ax, ay, anchor_right, anchor_bottom = self.overlay.compute_anchor()
        settings = APP_CONTEXT.settings.get()
        settings.overlay_anchored = True
        settings.overlay_anchor_x = ax
        settings.overlay_anchor_y = ay
        settings.overlay_anchor_right = anchor_right
        settings.overlay_anchor_bottom = anchor_bottom
        APP_CONTEXT.settings.save(settings)
        self.overlay.set_anchor(ax, ay, anchor_right, anchor_bottom)
        self.overlay.set_actions_mode(False)
        if self.overlay.isVisible():
            # повертаємо підказку замість Save; схований оверлей не показуємо
            self._refresh_overlay()

    def _set_status(self, status: str):
        self._status = status
        self._refresh_overlay()

    def _compute_status(self, session) -> str:
        # поки є кадри в роботі — "Recognizing"/"Recognizing (N)" має пріоритет;
        # транзитні повідомлення (помилки, "not recognized") показуються, коли черга порожня
        if self._in_flight == 1:
            return ui_lang.t("status.recognizing")
        if self._in_flight > 1:
            return ui_lang.t("status.recognizing_n").format(n=self._in_flight)
        if self._status:
            return self._status
        if session.is_complete():
            return ui_lang.t("status.done")
        return ""

    def _refresh_overlay(self, show: bool = False):
        # show=True лише у явних випадках (ручне відкриття чи старт розпізнавання);
        # як listener сесії викликається без аргументів — редагування/clear оверлей
        # не показують, лише оновлюють його вміст, якщо він уже видимий
        session = APP_CONTEXT.session_manager.active
        if isinstance(session, TrainingSessionService):
            self._refresh_training_overlay(session, show)
            return
        effective = {n: e for n in range(1, RACE_COUNT + 1) if (e := session.effective(n)) is not None}
        track_ids = {e.track_id for e in effective.values() if e.track_id}
        car_ids = {e.shown_car_id for e in effective.values() if e.shown_car_id}
        tracks = APP_CONTEXT.tracks_service.get_by_ids(track_ids)
        # назви нарізно: build_races_table сам складає «Карта - Трек» і вміє
        # фарбувати вибраний чипом трек cyan поруч із білою назвою карти
        track_names = {t.id: t.display_name for t in tracks.values()}
        track_maps = {t.id: t.display_map_name for t in tracks.values()}
        map_ids = {e.map_id for e in effective.values() if e.map_id}
        map_names = {m.id: m.display_name
                     for m in APP_CONTEXT.maps_service.get_by_ids(map_ids).values()}
        car_names = {c.id: c.name for c in APP_CONTEXT.cars_service.get_by_ids(car_ids).values()}
        # статистика «побито/шанс» показаного авто для незіграних гонок —
        # та сама умова, що й для бейджа на картці гонки в табі асистента
        beat_stats = {n: beat for n, e in effective.items()
                      if e.track_id and e.shown_car_id and e.opponent_time and not e.time
                      and (beat := APP_CONTEXT.assistant.beat_stats(
                          e.track_id, e.shown_car_id, e.opponent_time)) is not None}

        # оцінка зіграних заїздів «як проїхав» проти власного середнього того ж
        # авто на треку — лише для фактичного авто з БД (car_id), не для кастомного
        run_grades = {n: grade for n, e in effective.items()
                      if e.track_id and e.car_id > 0 and e.time
                      and (grade := APP_CONTEXT.assistant.run_grade(
                          e.track_id, e.car_id, e.time)) is not None}

        # лише ще досяжні/не перевищені режими — оверлей не захаращуємо
        # кнопками, які вже не мають сенсу (гонки без даних = пропущені)
        dists = APP_CONTEXT.assistant.goal_distributions(session)
        self.overlay.set_goals({goal: goal_label(goal, dists[goal] if dists else None)
                                for goal in visible_goals(*session.outcomes())},
                               session.goal)
        self._push_overlay(
            session,
            header_text(effective),
            build_races_table(effective, track_names, car_names, beat_stats,
                              track_maps=track_maps, map_names=map_names,
                              run_grades=run_grades),
            show)

    def _refresh_training_overlay(self, session: TrainingSessionService, show: bool):
        """Оверлей тренувальної сесії: останні заїзди з наскрізними номерами.
        Шансів/рекомендацій тут немає — лише трек, авто, час і 👎."""
        effective = {n: e for n in session.run_numbers()
                     if (e := session.effective(n)) is not None}
        track_ids = {e.track_id for e in effective.values() if e.track_id}
        tracks = APP_CONTEXT.tracks_service.get_by_ids(track_ids)
        track_names = {t.id: t.display_name for t in tracks.values()}
        track_maps = {t.id: t.display_map_name for t in tracks.values()}
        map_ids = {e.map_id for e in effective.values() if e.map_id}
        map_names = {m.id: m.display_name
                     for m in APP_CONTEXT.maps_service.get_by_ids(map_ids).values()}
        car_ids = {e.car_id for e in effective.values() if e.car_id}
        car_names = {c.id: c.name for c in APP_CONTEXT.cars_service.get_by_ids(car_ids).values()}
        # шеврон «як проїхав» — проти історії авто на треку з БД; заїзди самої
        # сесії ще не збережені, тож між собою не порівнюються
        run_grades = {n: grade for n, e in effective.items()
                      if e.track_id and e.car_id > 0 and e.time
                      and (grade := APP_CONTEXT.assistant.run_grade(
                          e.track_id, e.car_id, e.time)) is not None}
        self.overlay.set_goals(None)
        self._push_overlay(
            session, header_text({}),
            build_training_table(effective, track_names, car_names,
                                 track_maps=track_maps, map_names=map_names,
                                 run_grades=run_grades),
            show)

    def _push_overlay(self, session, header: str, table_html: str, show: bool):
        """Спільний хвіст оновлення оверлея: статус, підказка хоткеїв, показ."""
        status = self._compute_status(session)
        self.status_changed.emit(status)
        self.busy_changed.emit(self._in_flight > 0)
        settings = APP_CONTEXT.settings.get()
        # комбо показуємо як у налаштуваннях ("Ctrl + Alt"), а не великими літерами
        combo = " + ".join(p.capitalize() for p in settings.overlay_actions_hotkey.split("+") if p)
        hint = ui_lang.t("overlay.hint").format(
            capture=settings.capture_hotkey.upper(),
            hide=settings.overlay_hotkey.upper(),
            combo=combo)
        self.overlay.update_content(header, table_html, status, hint, self._in_flight)
        if show and not self.overlay.isVisible():
            self.overlay.show()
