import traceback
from typing import Any, Callable

from PyQt6.QtWidgets import QVBoxLayout, QLabel, QDialog, QPushButton, QHBoxLayout, QLayout


class EditDialog(QDialog):
    def __init__(self, action: Callable[[Any], int], parent=None):
        super().__init__(parent)
        self.action = action
        self.setModal(True)
        self.setMinimumSize(300, 180)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #FF6B6B;")

        self.save_button = QPushButton("Ok")
        self.save_button.clicked.connect(self.accept)   # type: ignore
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("secondary")
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
