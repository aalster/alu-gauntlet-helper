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
from alu_gauntlet_helper.screen_recognition.matching import TrackResolver, build_car_matcher
from alu_gauntlet_helper.screen_recognition.screens.before_race import BeforeRaceExtractor
from alu_gauntlet_helper.screen_recognition.screens.challenge_accordion import ChallengeAccordionExtractor
from alu_gauntlet_helper.screen_recognition.screens.challenge_complete import ChallengeCompleteExtractor
from alu_gauntlet_helper.screen_recognition.screens.race_result import RaceResultExtractor
from alu_gauntlet_helper.services.challenge_session import LOW_CONFIDENCE, RACE_COUNT
from alu_gauntlet_helper.views.overlay import OverlayWindow, build_races_table, header_text

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
        APP_CONTEXT.challenge_session.add_listener(self._refresh_overlay)

    def apply_settings(self) -> bool:
        """(Пере)реєструє хоткеї та tesseract зі збережених налаштувань. False — хоткей не став."""
        settings = APP_CONTEXT.settings.get()
        ocr.configure_tesseract()
        self.hotkeys.unregister_all()
        ok = self.hotkeys.register(settings.capture_hotkey, self._capture_requested.emit)
        self.hotkeys.register(settings.overlay_hotkey, self._overlay_toggle_requested.emit)
        actions_keys = [k for k in settings.overlay_actions_hotkey.split("+") if k]
        self.hotkeys.register_hold(actions_keys, self._actions_enter_requested.emit, self._actions_exit_requested.emit)
        self.overlay.set_screen_index(settings.capture_monitor)
        self.overlay.set_opacity(settings.overlay_opacity)
        if settings.overlay_anchored:
            self.overlay.set_anchor(settings.overlay_anchor_x, settings.overlay_anchor_y,
                                    settings.overlay_anchor_right, settings.overlay_anchor_bottom)
        else:
            self.overlay.clear_position()
        return ok

    def shutdown(self):
        APP_CONTEXT.challenge_session.remove_listener(self._refresh_overlay)
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
        return False

    @staticmethod
    def _build_engine() -> RecognitionEngine:
        # словники будуються на кожне захоплення — завжди свіжі дані з БД
        track_resolver = TrackResolver(APP_CONTEXT.tracks_service.get_all_views())
        car_matcher = build_car_matcher(APP_CONTEXT.cars_service.get_all())
        # Порядок — за ціною перевірки-якоря на чужому екрані: race_result і
        # challenge_complete відсіюються за 1-3 OCR-виклики, before_race — за 1-2
        # (частки білого без OCR + одна цифра). Акордеон спершу пробує геометричний
        # гейт (C6, 0 OCR); на «своєму» екрані це ~9 викликів, інакше падає в
        # дорогий OCR-пошук (англ. before-екран) — тож лишається останнім.
        return RecognitionEngine([
            RaceResultExtractor(car_matcher),
            ChallengeCompleteExtractor(car_matcher),
            BeforeRaceExtractor(track_resolver, car_matcher),
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
        APP_CONTEXT.challenge_session.apply(result)  # listener оновить оверлей

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
        session = APP_CONTEXT.challenge_session
        effective = {n: e for n in range(1, RACE_COUNT + 1) if (e := session.effective(n)) is not None}
        track_ids = {e.track_id for e in effective.values() if e.track_id}
        car_ids = {e.car_id for e in effective.values() if e.car_id}
        track_names = {t.id: f"{t.display_map_name} - {t.display_name}" for t in APP_CONTEXT.tracks_service.get_by_ids(track_ids).values()}
        car_names = {c.id: c.name for c in APP_CONTEXT.cars_service.get_by_ids(car_ids).values()}

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
        self.overlay.update_content(
            header_text(effective),
            build_races_table(effective, track_names, car_names),
            status, hint, self._in_flight)
        if show and not self.overlay.isVisible():
            self.overlay.show()
