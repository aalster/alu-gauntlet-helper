import threading
import traceback

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.capture.hotkey import GlobalHotkeyService
from alu_gauntlet_helper.capture.screen_grab import grab_screen, save_capture
from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.engine import RecognitionEngine
from alu_gauntlet_helper.screen_recognition.matching import TrackResolver, build_car_matcher
from alu_gauntlet_helper.screen_recognition.screens.challenge_accordion import ChallengeAccordionExtractor
from alu_gauntlet_helper.screen_recognition.screens.challenge_complete import ChallengeCompleteExtractor
from alu_gauntlet_helper.screen_recognition.screens.race_result import RaceResultExtractor
from alu_gauntlet_helper.views.overlay import OverlayWindow, build_overlay_lines

OVERLAY_HIDE_DELAY_MS = 80


class CaptureController(QObject):
    """Хоткей → скрін → розпізнавання (фоновий потік) → сесія → оверлей."""

    _capture_requested = pyqtSignal()
    _overlay_toggle_requested = pyqtSignal()
    _recognized = pyqtSignal(object)  # RecognitionResult | None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.overlay = OverlayWindow()
        self.hotkeys = GlobalHotkeyService()
        self._busy = False
        self._status = ""

        self._capture_requested.connect(self._on_capture_requested)
        self._overlay_toggle_requested.connect(self.overlay.toggle)
        self._recognized.connect(self._on_recognized)
        APP_CONTEXT.challenge_session.add_listener(self._refresh_overlay)

    def apply_settings(self) -> bool:
        """(Пере)реєструє хоткеї та tesseract зі збережених налаштувань. False — хоткей не став."""
        settings = APP_CONTEXT.settings.get()
        ocr.configure_tesseract(settings.tesseract_path)
        self.hotkeys.unregister_all()
        ok = self.hotkeys.register(settings.capture_hotkey, self._capture_requested.emit)
        self.hotkeys.register(settings.overlay_hotkey, self._overlay_toggle_requested.emit)
        self.overlay.set_screen_index(settings.capture_monitor)
        return ok

    def shutdown(self):
        APP_CONTEXT.challenge_session.remove_listener(self._refresh_overlay)
        self.hotkeys.unregister_all()

    # --- захоплення -----------------------------------------------------

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
            self._set_status("Помилка скріншота")
            return

        if settings.save_captures:
            save_capture(img)

        engine = self._build_engine()
        self._set_status("Розпізнаю…")
        threading.Thread(target=self._recognize_worker, args=(engine, img), daemon=True).start()

    def _recognize_worker(self, engine: RecognitionEngine, img):
        result = None
        try:
            if not ocr.is_available():
                print("Tesseract is not available")
            else:
                result = engine.recognize(img)
        except Exception:
            traceback.print_exc()
        try:
            self._recognized.emit(result)
        except RuntimeError:
            # QObject знищено під час завершення застосунку
            pass

    @staticmethod
    def _build_engine() -> RecognitionEngine:
        # словники будуються на кожне захоплення — завжди свіжі дані з БД
        track_resolver = TrackResolver(APP_CONTEXT.tracks_service.get_all_views())
        car_matcher = build_car_matcher(APP_CONTEXT.cars_service.get_all())
        # Порядок — за ціною перевірки-якоря на чужому екрані: race_result і
        # challenge_complete відсіюються за 1-3 OCR-виклики, акордеон — до 15.
        return RecognitionEngine([
            RaceResultExtractor(car_matcher),
            ChallengeCompleteExtractor(car_matcher),
            ChallengeAccordionExtractor(track_resolver, car_matcher),
        ])

    def _on_recognized(self, result):
        self._busy = False
        if result is None:
            self._set_status("Екран не розпізнано")
            return
        self._status = ""
        APP_CONTEXT.challenge_session.apply(result)  # listener оновить оверлей

    # --- оверлей ---------------------------------------------------------

    def _set_status(self, status: str):
        self._status = status
        self._refresh_overlay()

    def _refresh_overlay(self):
        session = APP_CONTEXT.challenge_session
        track_ids = {c.track.value for c in session.races.values() if c.track}
        car_ids = {c.car.value for c in session.races.values() if c.car}
        track_names = {t.id: t.name for t in APP_CONTEXT.tracks_service.get_by_ids(track_ids).values()}
        car_names = {c.id: c.name for c in APP_CONTEXT.cars_service.get_by_ids(car_ids).values()}

        status = self._status
        if not status and session.is_complete():
            status = "Готово — відкрий рев'ю у застосунку"
        self.overlay.set_lines(build_overlay_lines(session.races, track_names, car_names, status))
        if not self.overlay.isVisible():
            self.overlay.show()
