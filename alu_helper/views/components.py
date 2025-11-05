import traceback
from typing import Callable

from PyQt6.QtCore import QRegularExpression, Qt, QTimer, QObject, QEvent
from PyQt6.QtGui import QRegularExpressionValidator, QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QLabel, QDialog, QPushButton, QHBoxLayout, QLayout, \
    QCompleter


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
        layout.addWidget(self.error_label)


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
        self.setMinimumSize(300, 150)

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

        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self.update_completer) # type: ignore

        self.input_.textChanged.connect(self.on_text_changed)
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
            item = QStandardItem(self.presentation(i))  # отображаемое имя
            item.setData(i, Qt.ItemDataRole.UserRole)  # сам объект
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

        self.input_.textEdited.connect(self.start) # type: ignore

    def start(self):
        self.timer.start(self.debounce_time)