import traceback
from typing import Any, Callable

from PyQt6.QtWidgets import QVBoxLayout, QLabel, QDialog, QPushButton, QHBoxLayout, QLayout, QMessageBox

from alu_gauntlet_helper import ui_lang


class EditDialog(QDialog):
    def __init__(self, action: Callable[[Any], int], parent=None,
                 delete_action: Callable[[], None] | None = None, delete_confirm: str = ""):
        super().__init__(parent)
        self.action = action
        self.delete_action = delete_action
        self.delete_confirm = delete_confirm
        self.setModal(True)
        self.setMinimumSize(300, 180)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #FF6B6B;")

        self.save_button = QPushButton(ui_lang.t("dialog.ok"))
        self.save_button.clicked.connect(self.accept)   # type: ignore
        self.cancel_button = QPushButton(ui_lang.t("dialog.cancel"))
        self.cancel_button.setObjectName("secondary")
        self.cancel_button.clicked.connect(self.reject) # type: ignore

        buttons_layout = QHBoxLayout()
        if delete_action is not None:
            self.delete_button = QPushButton(ui_lang.t("dialog.delete"))
            self.delete_button.setObjectName("destructive")
            self.delete_button.clicked.connect(self.on_delete) # type: ignore
            buttons_layout.addWidget(self.delete_button)
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

    def on_delete(self):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(ui_lang.t("dialog.delete_confirm_title"))
        box.setText(self.delete_confirm or ui_lang.t("dialog.delete_confirm_title"))
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        for btn in box.buttons():
            btn.setObjectName("secondary")
            btn.style().polish(btn)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return

        self.error_label.clear()
        try:
            self.delete_action()
        except Exception as e:
            traceback.print_exc()
            self.error_label.setText(str(e))
            return

        super().accept()

    def prepare_item(self):
        raise NotImplementedError
