# gui/maps_tab.py
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QListWidget, QLineEdit, QListWidgetItem, QHBoxLayout, \
    QLabel, QCompleter

from alu_helper.app_context import APP_CONTEXT
from alu_helper.models import TrackEditModel
from alu_helper.services.maps import Map
from alu_helper.services.tracks import Track
from alu_helper.views.components import EditDialog, ValidatedLineEdit


class TrackDialog(EditDialog):
    def __init__(self, item: TrackEditModel, action, parent=None):
        self.item = item

        self.map_edit = ValidatedLineEdit(item.name)
        self.name_edit = ValidatedLineEdit(item.name)

        self.maps_completer = QCompleter([])
        self.maps_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.maps_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.maps_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.maps_completer.activated.connect(self.on_maps_completer_activated)
        self.map_edit.get_input().setCompleter(self.maps_completer)

        super().__init__(action, parent)
        self.setWindowTitle("Edit Track" if item.id else "Add Track")

        self.map_debounce_timer = QTimer(self)
        self.map_debounce_timer.setSingleShot(True)
        self.map_debounce_timer.timeout.connect(self.update_maps_completer) # type: ignore
        self.map_edit.get_input().textChanged.connect(self.on_map_text_changed)

    def prepare_layout(self):
        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel("Map:"))
        form_layout.addWidget(self.map_edit)
        form_layout.addWidget(QLabel("Name:"))
        form_layout.addWidget(self.name_edit)

        return form_layout

    def showEvent(self, event):
        super().showEvent(event)
        self.map_edit.setFocus()

    def on_map_text_changed(self, text):
        self.map_debounce_timer.start(300)

    def on_maps_completer_activated(self, text):
        self.map_edit.get_input().setText(text)
        self.map_debounce_timer.stop()

    def update_maps_completer(self):
        query = self.map_edit.text()
        maps = [m.name for m in APP_CONTEXT.maps_service.get_all(query)]
        self.maps_completer.model().setStringList(maps)
        if maps and query:
            self.maps_completer.complete()
        else:
            self.maps_completer.popup().hide()

    def prepare_item(self):
        name = self.name_edit.text().strip()
        if not name:
            self.name_edit.set_error()
            return None

        map_name = self.map_edit.text().strip()
        if not map_name:
            self.map_edit.set_error()
            return None

        return TrackEditModel(id=self.item.id, map_id=0, map_name=map_name, name=name)


class TracksTab(QWidget):
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
        for t in APP_CONTEXT.tracks_service.get_all(self.query.text()):
            item = QListWidgetItem(f"{t.map_id}: {t.name}")
            item.setData(Qt.ItemDataRole.UserRole, t)
            self.list_widget.addItem(item)

    def on_add(self):
        track = TrackEditModel(id=0, map_id=0, map_name="AAAA", name=self.query.text().strip())
        dialog = TrackDialog(item=track, action=APP_CONTEXT.tracks_service.add)
        if dialog.exec():
            self.refresh()

    def on_edit(self, item: QListWidgetItem):
        track_view = item.data(Qt.ItemDataRole.UserRole)
        track = TrackEditModel(id=track_view.id, map_id=track_view.map_id, map_name=track_view.map_name, name=track_view.name)
        dialog = TrackDialog(item=track, action=APP_CONTEXT.tracks_service.update)
        if dialog.exec():
            self.refresh()
