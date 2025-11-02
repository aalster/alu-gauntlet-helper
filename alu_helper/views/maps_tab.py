# gui/maps_tab.py
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QListWidget, QLineEdit, QListWidgetItem

from alu_helper.app_context import APP_CONTEXT
from alu_helper.views.map_dialog import MapDialog


class MapsTab(QWidget):
    def __init__(self):
        super().__init__()

        self.query = QLineEdit()
        self.list_widget = QListWidget()

        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self.refresh) # type: ignore

        self.query.textEdited.connect(self.refresh_debounce) # type: ignore

        self.list_widget.itemDoubleClicked.connect(self.edit) # type: ignore

        layout = QVBoxLayout()
        layout.addWidget(self.query)
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

    def edit(self, item: QListWidgetItem):
        map_item = item.data(Qt.ItemDataRole.UserRole)
        dialog = MapDialog(item=map_item)
        if dialog.exec():
            updated = dialog.get_result()
            APP_CONTEXT.maps_service.update(updated)
            item.setText(updated.name)
            item.setData(Qt.ItemDataRole.UserRole, updated)
