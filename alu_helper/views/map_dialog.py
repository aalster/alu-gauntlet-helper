from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt

from alu_helper.services.maps import Map
from alu_helper.views.components import ValidatedLineEdit


class MapDialog(QDialog):
    result: Map

    def __init__(self, parent=None, item: Map = Map(id=0, name="")):
        super().__init__(parent)
        self.item = item

        self.setWindowTitle("Edit Map" if item.id else "Add Map")
        self.setModal(True)
        self.setFixedSize(300, 150)

        self.name_edit = ValidatedLineEdit(item.name)

        self.save_button = QPushButton("Ok")
        self.cancel_button = QPushButton("Cancel")

        self.save_button.clicked.connect(self.accept) # type: ignore
        self.cancel_button.clicked.connect(self.reject) # type: ignore

        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel("Name:"))
        form_layout.addWidget(self.name_edit)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(self.cancel_button)

        layout = QVBoxLayout()
        layout.addLayout(form_layout)
        layout.addStretch(1)
        layout.addLayout(buttons_layout)
        self.setLayout(layout)

    def accept(self):
        name = self.name_edit.text()
        if not name:
            self.name_edit.set_error()
            return

        self.result = Map(id=self.item.id, name=name)
        super().accept()

    def get_result(self) -> Map:
        return self.result
