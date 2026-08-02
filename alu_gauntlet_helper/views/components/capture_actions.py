from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QWidget

from alu_gauntlet_helper import ui_lang
from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.views.overlay import Spinner


class CaptureActionsWidget(QWidget):
    """Глобальні дії захоплення в куті вікна (corner widget таббара):
    статус, спінер і кнопки «Завантажити скріншот» / «Знімок» / «Оверлей».
    Статус «Розпізнавання…» показується самим спінером, без тексту."""

    def __init__(self, recognize_file=None, toggle_overlay=None, capture=None, parent=None):
        super().__init__(parent)
        self.setObjectName("captureActions")
        self.recognize_file = recognize_file

        self.status_label = QLabel()
        self.status_label.setObjectName("captureStatus")

        self.spinner = Spinner()

        settings = APP_CONTEXT.settings.get()
        self.load_button = QPushButton(ui_lang.t("capture.load_screenshot"))
        self.load_button.setObjectName("secondary")
        self.load_button.clicked.connect(self.load_screenshot)
        self.capture_button = QPushButton(
            ui_lang.t("capture.capture_screen").format(hotkey=settings.capture_hotkey.upper()))
        if capture:
            self.capture_button.clicked.connect(capture)
        # тогл: підсвічена, поки оверлей видимий (стан веде set_overlay_active
        # за сигналом видимості вікна, а не самим кліком)
        self.overlay_button = QPushButton(
            ui_lang.t("capture.toggle_overlay").format(hotkey=settings.overlay_hotkey.upper()))
        self.overlay_button.setObjectName("secondary")
        self.overlay_button.setCheckable(True)
        if toggle_overlay:
            self.overlay_button.clicked.connect(toggle_overlay)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 6, 2)
        layout.setSpacing(6)
        layout.addWidget(self.status_label)
        layout.addWidget(self.spinner)
        layout.addWidget(self.load_button)
        layout.addWidget(self.capture_button)
        layout.addWidget(self.overlay_button)

    def set_status(self, status: str):
        # порівнюємо з локалізованим префіксом («Розпізнавання (N)» теж ловиться),
        # а не з англійським літералом, як робив старий код у AssistantTab
        recognizing = bool(status) and status.startswith(ui_lang.t("status.recognizing"))
        if recognizing:
            self.spinner.start()
        else:
            self.spinner.stop()
        self.status_label.setText("" if recognizing else status)

    def set_overlay_active(self, active: bool):
        # програмний setChecked не емітить clicked — циклу з toggle_overlay немає
        self.overlay_button.setChecked(active)

    def load_screenshot(self):
        # можна вибрати кілька файлів — кожен стає в чергу розпізнавання,
        # воркер обробить їх по одному в порядку вибору
        paths, _ = QFileDialog.getOpenFileNames(
            self, ui_lang.t("capture.load_screenshot"), "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if self.recognize_file:
            for path in paths:
                self.recognize_file(path)
