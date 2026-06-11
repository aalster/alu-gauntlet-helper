from PyQt6.QtCore import Qt, QEvent, QSize
from PyQt6.QtGui import QPixmap, QGuiApplication, QImage, QCursor
from PyQt6.QtWidgets import QWidget, QLineEdit, QLabel, QPushButton, QHBoxLayout, QFileDialog, QStyle

from alu_gauntlet_helper.utils.utils import pixmap_cover
from alu_gauntlet_helper.views.components.common import add_contents, vbox


class ImageLineEdit(QWidget):
    def __init__(self, image: QImage | None = None):
        super().__init__()
        self._image = None

        self.preview = QLabel()
        self.preview.setFixedSize(80, 80)
        self.preview.setStyleSheet("border-radius: 4px; background-color: #271A62;")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.clear_button = QPushButton(self.preview)
        self.clear_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_LineEditClearButton))
        self.clear_button.setFixedSize(QSize(20, 20))
        self.clear_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.clear_button.setToolTip("Clear")
        self.clear_button.setStyleSheet("border: none; background: transparent; padding: 0;")
        padding = 2
        self.clear_button.move(self.preview.width() - self.clear_button.width() - padding, padding)
        self.clear_button.clicked.connect(self.clear) # type: ignore

        self.line = QLineEdit()
        self.line.setReadOnly(True)
        self.line.setPlaceholderText("Paste from clipboard")
        self.line.installEventFilter(self)

        self.select_button = QPushButton("Choose file")
        self.select_button.clicked.connect(self.pick_file) # type: ignore

        or_label = QLabel("Or")
        or_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        right_vbox = vbox([self.line, or_label, self.select_button], spacing=0)
        add_contents(QHBoxLayout(self), [self.preview, right_vbox])

        self.set_image(image)

    def eventFilter(self, obj, event):
        if obj is self.line and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_V and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                self.paste_image()
                return True
        return super().eventFilter(obj, event)

    def clear(self):
        self.set_image(None)
        self.line.clear()

    def paste_image(self):
        clipboard = QGuiApplication.clipboard()
        img = clipboard.image()
        if not img.isNull():
            self.set_image(img)
            self.line.setText("From clipboard")
            return

        md = clipboard.mimeData()
        if md.hasUrls():
            for url in md.urls():
                try:
                    img = QImage(url.toLocalFile())
                    if not img.isNull():
                        self.set_image(img)
                        self.line.setText("From clipboard")
                        return
                except Exception:
                    pass

    def pick_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose Image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.set_image(QImage(path))
            self.line.setText(path)

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
