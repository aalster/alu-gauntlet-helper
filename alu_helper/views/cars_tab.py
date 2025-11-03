# gui/maps_tab.py
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QListWidget, QLineEdit, QListWidgetItem, QHBoxLayout, \
    QLabel

from alu_helper.app_context import APP_CONTEXT
from alu_helper.services.cars import Car
from alu_helper.views.components import EditDialog, ValidatedLineEdit


class CarDialog(EditDialog):
    def __init__(self, item: Car, action, parent=None):
        self.item = item
        self.name_edit = ValidatedLineEdit(item.name)
        self.rank_edit = ValidatedLineEdit(str(item.rank) if item.rank else "")
        self.rank_edit.get_input().setValidator(QIntValidator(0, 10000))

        super().__init__(action, parent)
        self.setWindowTitle("Edit Map" if item.id else "Add Map")

    def prepare_layout(self):
        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel("Name:"))
        form_layout.addWidget(self.name_edit)
        form_layout.addWidget(QLabel("Rank:"))
        form_layout.addWidget(self.rank_edit)

        return form_layout

    def showEvent(self, event):
        super().showEvent(event)
        self.name_edit.setFocus()

    def prepare_item(self):
        name = self.name_edit.text()
        if not name:
            self.name_edit.set_error()
            return None

        rank = int(self.rank_edit.text()) if self.rank_edit.text() else 0

        return Car(id=self.item.id, name=name, rank=rank)

class CarsTab(QWidget):
    def __init__(self):
        super().__init__()

        self.query = QLineEdit()
        self.query.setClearButtonEnabled(True)
        self.query.setPlaceholderText("Filter by name")
        self.query.textEdited.connect(self.refresh_debounce) # type: ignore

        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.on_add) # type: ignore

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.on_edit) # type: ignore

        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self.refresh) # type: ignore

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.query)
        top_layout.addWidget(self.add_button)

        layout = QVBoxLayout()
        layout.addLayout(top_layout)
        layout.addWidget(self.list_widget)
        self.setLayout(layout)
        self.refresh()

    def refresh_debounce(self):
        self.debounce_timer.start(300)

    def refresh(self):
        self.list_widget.clear()
        for i in APP_CONTEXT.cars_service.autocomplete(self.query.text()):
            item = QListWidgetItem(f"{i.id}: {i.name} {i.rank}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.list_widget.addItem(item)

    def on_add(self):
        item = Car(id=0, name=self.query.text().strip(), rank=0)
        dialog = CarDialog(item=item, action=APP_CONTEXT.cars_service.add)
        if dialog.exec():
            self.refresh()

    def on_edit(self, item: QListWidgetItem):
        item = item.data(Qt.ItemDataRole.UserRole)
        dialog = CarDialog(item=item, action=APP_CONTEXT.cars_service.update)
        if dialog.exec():
            self.refresh()
