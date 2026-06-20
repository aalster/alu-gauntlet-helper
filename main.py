import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.cars_sync import sync_bundled_cars
from alu_gauntlet_helper.services.initial_data import init_data, sync_track_icons
from alu_gauntlet_helper.utils.single_instance_lock import single_instance_lock
from alu_gauntlet_helper.utils.utils import app_dir_if_frozen
from alu_gauntlet_helper.views.main_window import MainWindow
from alu_gauntlet_helper.views.style import apply_style
from alu_gauntlet_helper.database import init_db


def main():
    app_dir = app_dir_if_frozen()
    if app_dir:
        # cwd = тека застосунку: всі відносні шляхи (app.db, data/, іконки в БД)
        # розв'язуються відносно exe; після цього cwd ніде не змінювати
        os.chdir(app_dir)

    start_minimized = "--minimized" in sys.argv

    window: MainWindow | None = None

    def show_window():
        if window is not None:
            window.show_window()

    lock = single_instance_lock(show_window)
    if not lock:
        print("Application already running.")
        sys.exit(0)


    init_db()

    settings = APP_CONTEXT.settings.get()
    from alu_gauntlet_helper import game_lang
    game_lang.set_game_language(settings.game_language)
    if not settings.initial_data_loaded:
        init_data()
        settings.initial_data_loaded = True
        APP_CONTEXT.settings.save(settings)

    # Монітор міг зникнути між запусками (відключили екран) — скидаємо на 1
    from alu_gauntlet_helper.capture.screen_grab import monitor_count
    if not 1 <= settings.capture_monitor <= monitor_count():
        settings.capture_monitor = 1
        APP_CONTEXT.settings.save(settings)

    sync_track_icons()
    sync_bundled_cars()

    from alu_gauntlet_helper.screen_recognition.ocr import configure_tesseract
    configure_tesseract()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    # без фейду/анімації при появі тултипів
    app.setEffectEnabled(Qt.UIEffect.UI_FadeTooltip, False)
    app.setEffectEnabled(Qt.UIEffect.UI_AnimateTooltip, False)
    apply_style(app)

    window = MainWindow()
    if window.tray_icon and settings.close_to_tray and (start_minimized or settings.start_minimized):
        window.hide()
    else:
        window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()