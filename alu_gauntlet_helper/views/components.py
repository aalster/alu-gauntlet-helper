import traceback
from typing import Callable

from PyQt6.QtCore import QRegularExpression, Qt, QTimer, QObject, QEvent, QSize
from PyQt6.QtGui import QRegularExpressionValidator, QStandardItemModel, QStandardItem, QPixmap, QGuiApplication, \
    QImage, QIcon, QAction, QCursor
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QLabel, QDialog, QPushButton, QHBoxLayout, QLayout, \
    QCompleter, QFileDialog, QToolButton, QApplication, QStyle

from alu_gauntlet_helper.utils.utils import get_resource_path, pixmap_cover


class ValidatedLineEdit(QWidget):
    def __init__(self, text: str = "", placeholder: str = "", regex: str | None = None):
        super().__init__()

        self.input = QLineEdit(text)
        self.input.setPlaceholderText(placeholder)
        if regex:
            self.input.setValidator(QRegularExpressionValidator(QRegularExpression(regex)))
        self.input.textChanged.connect(self.clear_error) # type: ignore

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red; font-size: 11px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.input)
        # layout.addWidget(self.error_label)


    def get_input(self) -> QLineEdit:
        return self.input

    def text(self) -> str:
        return self.input.text().strip()

    def setFocus(self):
        self.input.setFocus()

    def set_text(self, text: str):
        self.input.setText(text)

    def set_error(self, message: str = ""):
        self.input.setStyleSheet("background-color: rgba(255, 0, 0, 0.1);")
        self.error_label.setText(message)

    def clear_error(self):
        self.input.setStyleSheet("")
        self.error_label.clear()



class EditDialog(QDialog):
    def __init__(self, action, parent=None):
        super().__init__(parent)
        self.action = action
        self.setModal(True)
        self.setMinimumSize(300, 180)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red;")

        self.save_button = QPushButton("Ok")
        self.save_button.clicked.connect(self.accept)   # type: ignore
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject) # type: ignore

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(self.cancel_button)

        self.main_layout = QVBoxLayout()
        self.main_layout.addLayout(self.prepare_layout())
        self.main_layout.addStretch(1)
        self.main_layout.addWidget(self.error_label)
        self.main_layout.addLayout(buttons_layout)
        self.setLayout(self.main_layout)

    def prepare_layout(self) -> QLayout:
        raise NotImplementedError

    def accept(self):
        self.error_label.clear()

        result = self.prepare_item()
        if result is None:
            return

        try:
            self.action(result)
        except Exception as e:
            traceback.print_exc()
            self.error_label.setText(str(e))
            return

        super().accept()

    def prepare_item(self):
        raise NotImplementedError

class FocusWatcher(QObject):

    def __init__(self, on_focus_in = None, on_focus_out = None):
        super().__init__()
        self.on_focus_in = on_focus_in
        self.on_focus_out = on_focus_out

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.FocusIn and self.on_focus_in:
            self.on_focus_in()
        elif event.type() == QEvent.Type.FocusOut and self.on_focus_out:
            self.on_focus_out()
        return False

class ItemCompleter(QCompleter):
    selected_item = None

    def __init__(self, input_: QLineEdit, autocomplete, presentation, allow_custom_text=True, selected_listener=None, parent=None):
        super().__init__(parent)
        self.input_ = input_
        self.autocomplete = autocomplete
        self.presentation = presentation
        self.selected_listener = selected_listener

        self._model = QStandardItemModel(self)
        self.setModel(self._model)
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterMode(Qt.MatchFlag.MatchContains)
        self.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.activated.connect(self.on_completer_activated) # type: ignore
        self.highlighted.connect(self.on_completer_activated) # type: ignore

        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self.update_completer) # type: ignore

        self.input_.textEdited.connect(self.on_text_changed)
        if not allow_custom_text:
            self.input_.editingFinished.connect(self.on_editing_finished)
        self.input_.setCompleter(self)

        # self.input_watcher = FocusWatcher(on_focus_in=self.update_completer)
        # self.input_.installEventFilter(self.input_watcher)

    def set_selected_item(self, item):
        self.selected_item = item

    def get_selected_item(self):
        return self.selected_item

    def on_editing_finished(self):
        if not self.selected_item:
            self.input_.clear()

    def on_text_changed(self, _):
        self.selected_item = None
        if self.selected_listener:
            self.selected_listener(None)
        self.debounce_timer.start(300)

    def on_completer_activated(self, text):
        self.input_.setText(text)
        self.debounce_timer.stop()

        index = self.popup().currentIndex()
        if index.isValid():
            self.selected_item = index.data(Qt.ItemDataRole.UserRole)
            if self.selected_listener:
                self.selected_listener(self.selected_item)

    def update_completer(self):
        try:
            query = self.input_.text().strip()
        except RuntimeError:
            return

        items = self.autocomplete(query)

        self._model.clear()
        for i in items:
            item = QStandardItem(self.presentation(i))
            item.setData(i, Qt.ItemDataRole.UserRole)
            self._model.appendRow(item)

        if items:
            self.complete()
        else:
            self.popup().hide()

class InputDebounce:
    def __init__(self, input_: QLineEdit, on_change: Callable, debounce_time: int = 300):
        self.input_ = input_
        self.debounce_time = debounce_time

        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(on_change) # type: ignore

        self.input_.textChanged.connect(self.start) # type: ignore

    def start(self):
        self.timer.start(self.debounce_time)

class ClearOnEscEventFilter(QObject):
    def eventFilter(self, obj, event):
        if isinstance(obj, QLineEdit) and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                obj.clear()
                return True
        return super().eventFilter(obj, event)

CLEAR_ON_ESC_FILTER = ClearOnEscEventFilter()

class ImageLineEdit(QWidget):
    def __init__(self, image: QImage | None = None):
        super().__init__()
        self._image = None

        self.preview = QLabel()
        self.preview.setFixedSize(80, 80)
        self.preview.setStyleSheet("border: 1px solid #aaa;")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.clear_button = QPushButton(self.preview)
        self.clear_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_LineEditClearButton))
        self.clear_button.setFixedSize(QSize(20, 20))
        self.clear_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.clear_button.setToolTip("Clear")
        self.clear_button.setStyleSheet("border: none")
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


def add_contents(layout, items, spacing=None, alignment=None):
    layout.setContentsMargins(0, 0, 0, 0)
    if spacing is not None:
        layout.setSpacing(spacing)

    kwargs = {}
    if alignment is not None:
        kwargs['alignment'] = alignment

    for item in items:
        if isinstance(item, QLayout):
            layout.addLayout(item, **kwargs)
        else:
            layout.addWidget(item, **kwargs)
    return layout

def vbox(items, spacing=None, alignment=None) -> QVBoxLayout:
    return add_contents(QVBoxLayout(), items, spacing=spacing, alignment=alignment)

def hbox(items, spacing=None, alignment=None) -> QHBoxLayout:
    return add_contents(QHBoxLayout(), items, spacing=spacing, alignment=alignment)

def res_to_pixmap(path: str, size: int | None = None):
    q_pixmap = QPixmap(get_resource_path(path))
    if size:
        q_pixmap = q_pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return q_pixmap