# gui/maps_tab.py
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QListWidget, QLineEdit, QListWidgetItem, QHBoxLayout

from alu_helper.app_context import APP_CONTEXT
from alu_helper.services.maps import Map
from alu_helper.views.map_dialog import MapDialog


class MapsTab(QWidget):
    def __init__(self):
        super().__init__()

        self.query = QLineEdit()
        self.query.setClearButtonEnabled(True)
        self.query.setPlaceholderText("Filter by name")
        self.query.textEdited.connect(self.refresh_debounce) # type: ignore

        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.add) # type: ignore

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.edit) # type: ignore

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

    def add(self):
        map_item = Map(id=0, name=self.query.text().strip())
        dialog = MapDialog(item=map_item)
        if dialog.exec():
            new = dialog.get_result()
            APP_CONTEXT.maps_service.add(new)
            self.refresh()

    def edit(self, item: QListWidgetItem):
        map_item = item.data(Qt.ItemDataRole.UserRole)
        dialog = MapDialog(item=map_item)
        if dialog.exec():
            updated = dialog.get_result()
            APP_CONTEXT.maps_service.update(updated)
            item.setText(updated.name)
            item.setData(Qt.ItemDataRole.UserRole, updated)
