from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QLabel
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
