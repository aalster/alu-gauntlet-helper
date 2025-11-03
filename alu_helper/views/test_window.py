from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLineEdit, QListWidget

from alu_helper.app_context import APP_CONTEXT
from alu_helper.services.tracks import TrackView


class TestView(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()
        self.input = QLineEdit()
        self.button = QPushButton("Add Record")
        self.listbox = QListWidget()

        layout.addWidget(self.input)
        layout.addWidget(self.button)
        layout.addWidget(self.listbox)
        self.setLayout(layout)

        self.button.clicked.connect(self.on_add) # type: ignore
        self.load_records()

    def load_records(self):
        self.listbox.clear()
        for track in APP_CONTEXT.tracks_service.autocomplete(""):
            self.listbox.addItem(f"{track.id}: {track.name}")

    def on_add(self):
        name = self.input.text().strip()
        if not name:
            return
        APP_CONTEXT.tracks_service.add(TrackView(map_id=0, map_name="test", name=name))
        self.input.clear()
        self.load_records()
