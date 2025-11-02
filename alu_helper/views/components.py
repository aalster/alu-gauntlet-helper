from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QLabel, QDialog, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, QRegularExpression
from PyQt6.QtGui import QRegularExpressionValidator


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
        self.error_label.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.input)
        layout.addWidget(self.error_label)


    def text(self) -> str:
        return self.input.text().strip()

    def setFocus(self):
        self.input.setFocus()

    def set_text(self, text: str):
        self.input.setText(text)

    def set_error(self, message: str = ""):
        self.input.setStyleSheet("background-color: rgba(255, 0, 0, 0.1);")
        self.error_label.setText(message)
        self.error_label.setVisible(True)

    def clear_error(self):
        self.input.setStyleSheet("")
        self.error_label.clear()
        self.error_label.setVisible(False)



class EditDialog(QDialog):
    def __init__(self, action, parent=None):
        super().__init__(parent)
        self.action = action
        self.setModal(True)
        self.setFixedSize(300, 150)

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
        self.main_layout.addStretch(1)
        self.main_layout.addWidget(self.error_label)
        self.main_layout.addLayout(buttons_layout)
        self.setLayout(self.main_layout)

    def accept(self):
        self.error_label.clear()

        result = self.prepare_item()
        if result is None:
            return

        try:
            self.action(result)
        except Exception as e:
            self.error_label.setText(str(e))
            return

        super().accept()

    def prepare_item(self):
        raise NotImplementedError