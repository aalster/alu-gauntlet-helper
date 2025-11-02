from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from alu_helper.services.maps import Map
from alu_helper.views.components import ValidatedLineEdit, EditDialog


class MapDialog(EditDialog):

    def __init__(self, item: Map, action, parent=None):
        super().__init__(action, parent)
        self.item = item

        self.setWindowTitle("Edit Map" if item.id else "Add Map")

        self.name_edit = ValidatedLineEdit(item.name)

        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel("Name:"))
        form_layout.addWidget(self.name_edit)

        self.main_layout.insertLayout(0, form_layout)

    def showEvent(self, event):
        super().showEvent(event)
        self.name_edit.setFocus()

    def prepare_item(self):
        name = self.name_edit.text().strip()
        if not name:
            self.name_edit.set_error()
            return None

        return Map(id=self.item.id, name=name)
