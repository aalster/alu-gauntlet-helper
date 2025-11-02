# gui/maps_tab.py
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QListWidget, QLineEdit, QListWidgetItem, QHBoxLayout, \
    QLabel

from alu_helper.app_context import APP_CONTEXT
from alu_helper.services.maps import Map
from alu_helper.views.components import EditDialog, ValidatedLineEdit


class MapDialog(EditDialog):
    def __init__(self, item: Map, action, parent=None):
        self.item = item
        self.name_edit = ValidatedLineEdit(item.name)

        super().__init__(action, parent)
        self.setWindowTitle("Edit Map" if item.id else "Add Map")

    def prepare_layout(self):
        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel("Name:"))
        form_layout.addWidget(self.name_edit)

        return form_layout

    def showEvent(self, event):
        super().showEvent(event)
        self.name_edit.setFocus()

    def prepare_item(self):
        name = self.name_edit.text().strip()
        if not name:
            self.name_edit.set_error()
            return None

        return Map(id=self.item.id, name=name)

class MapsTab(QWidget):
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
        for m in APP_CONTEXT.maps_service.get_all(self.query.text()):
            item = QListWidgetItem(m.name)
            item.setData(Qt.ItemDataRole.UserRole, m)
            self.list_widget.addItem(item)

    def on_add(self):
        map_item = Map(id=0, name=self.query.text().strip())
        dialog = MapDialog(item=map_item, action=APP_CONTEXT.maps_service.add)
        if dialog.exec():
            self.refresh()

    def on_edit(self, item: QListWidgetItem):
        map_item = item.data(Qt.ItemDataRole.UserRole)
        dialog = MapDialog(item=map_item, action=APP_CONTEXT.maps_service.update)
        if dialog.exec():
            self.refresh()
