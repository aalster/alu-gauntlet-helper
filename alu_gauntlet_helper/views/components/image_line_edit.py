from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QGuiApplication, QImage, QCursor
from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QFileDialog, QStyle

from alu_gauntlet_helper import ui_lang
from alu_gauntlet_helper.utils.utils import pixmap_cover
from alu_gauntlet_helper.views.components.common import add_contents


class ImageLineEdit(QWidget):
    def __init__(self, image: QImage | None = None):
        super().__init__()
        self._image = None

        self.preview = QLabel()
        self.preview.setFixedSize(240, 120)
        self.preview.setStyleSheet("border-radius: 4px; background-color: #271A62;")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.clear_button = QPushButton(self.preview)
        self.clear_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_LineEditClearButton))
        self.clear_button.setFixedSize(QSize(20, 20))
        self.clear_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.clear_button.setToolTip(ui_lang.t("image.clear"))
        self.clear_button.setStyleSheet("border: none; background: transparent; padding: 0;")
        padding = 2
        self.clear_button.move(self.preview.width() - self.clear_button.width() - padding, padding)
        self.clear_button.clicked.connect(self.clear) # type: ignore

        self.select_button = QPushButton(ui_lang.t("image.choose_file"))
        self.select_button.setObjectName("secondary")
        self.select_button.clicked.connect(self.pick_file) # type: ignore

        self.paste_button = QPushButton(ui_lang.t("image.paste"))
        self.paste_button.setObjectName("secondary")
        self.paste_button.clicked.connect(self.paste_image) # type: ignore

        self.select_button.setFixedWidth(self.preview.width())
        self.paste_button.setFixedWidth(self.preview.width())
        add_contents(QVBoxLayout(self), [self.preview, self.select_button, self.paste_button], spacing=6,
                     alignment=Qt.AlignmentFlag.AlignLeft)

        self.set_image(image)

    def clear(self):
        self.set_image(None)

    def paste_image(self):
        clipboard = QGuiApplication.clipboard()
        img = clipboard.image()
        if not img.isNull():
            self.set_image(img)
            return

        md = clipboard.mimeData()
        if md.hasUrls():
            for url in md.urls():
                try:
                    img = QImage(url.toLocalFile())
                    if not img.isNull():
                        self.set_image(img)
                        return
                except Exception:
                    pass

    def pick_file(self):
        path, _ = QFileDialog.getOpenFileName(self, ui_lang.t("image.choose_image"), "", ui_lang.t("common.images_filter"))
        if path:
            self.set_image(QImage(path))

    def set_image(self, img: QImage | None):
        self._image = img
        if img:
            self.preview.setPixmap(pixmap_cover(QPixmap.fromImage(img), w=self.preview.width(), h=self.preview.height()))
            self.clear_button.setVisible(True)
        else:
            self.preview.clear()
            self.clear_button.setVisible(False)

    def get_image(self) -> QImage | None:
        return self._image
