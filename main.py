import sys

from PyQt6.QtWidgets import QApplication

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.initial_data import init_data
from alu_gauntlet_helper.utils.single_instance_lock import single_instance_lock
from alu_gauntlet_helper.views.main_window import MainWindow
from alu_gauntlet_helper.database import init_db


def main():
    start_minimized = "--minimized" in sys.argv

    window: MainWindow | None = None

    def show_window():
        if not window is None:
            window.show_window()

    lock = single_instance_lock(show_window)
    if not lock:
        print("Application already running.")
        sys.exit(0)


    init_db()

    settings = APP_CONTEXT.settings.get()
    if not settings.initial_data_loaded:
        init_data()
        settings.initial_data_loaded = True
        APP_CONTEXT.settings.save(settings)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = app.font()
    font.setPointSize(10)
    app.setFont(font)

    window = MainWindow()
    if window.tray_icon and settings.close_to_tray and (start_minimized or settings.start_minimized):
        window.hide()
    else:
        window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()