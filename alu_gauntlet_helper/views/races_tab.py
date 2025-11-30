# gui/maps_tab.py
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIntValidator, QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QListWidget, QLineEdit, QListWidgetItem, QHBoxLayout, \
    QLabel, QCheckBox, QTextEdit, QFormLayout

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.races import RaceView
from alu_gauntlet_helper.services.tracks import TrackView
from alu_gauntlet_helper.utils.utils import format_time, time_format_regex, parse_time
from alu_gauntlet_helper.views.components.common import InputDebounce, CLEAR_ON_ESC_FILTER, vbox, res_to_pixmap, hbox, \
    ListItemWidget
from alu_gauntlet_helper.views.components.edit_dialog import EditDialog
from alu_gauntlet_helper.views.components.validated_line_edit import ValidatedLineEdit
from alu_gauntlet_helper.views.components.item_completer import ItemCompleter


class RaceDialog(EditDialog):
    def __init__(self, item: RaceView, action, parent=None):
        self.item = item

        self.track_edit = ValidatedLineEdit(f"{item.map_name} - {item.track_name}" if item.track_name else "")
        self.car_edit = ValidatedLineEdit(item.car_name)
        self.rank_edit = ValidatedLineEdit(str(item.rank) if item.rank else "")
        self.rank_edit.get_input().setValidator(QIntValidator(0, 10000))
        self.time_edit = ValidatedLineEdit(format_time(item.time), placeholder="mm:ss.xxx", regex=time_format_regex)
        self.bad_timing_checkbox = QCheckBox("Bad timing")
        self.bad_timing_checkbox.setChecked(item.bad_timing)
        self.note_edit = QTextEdit(item.note)

        self.tracks_completer = ItemCompleter(
            self.track_edit.get_input(),
            autocomplete=APP_CONTEXT.tracks_service.autocomplete,
            presentation=lambda i: f"{i.map_name} - {i.name}",
            allow_custom_text=False
        )
        self.tracks_completer.set_selected_item(TrackView(id=item.track_id, name=item.track_name, map_name=item.map_name))

        self.cars_completer = ItemCompleter(
            self.car_edit.get_input(),
            autocomplete=APP_CONTEXT.cars_service.autocomplete,
            presentation=lambda i: i.name,
            selected_listener=self.on_car_selected
        )

        super().__init__(action, parent)
        self.setWindowTitle("Edit Race" if item.id else "Add Race")

    def prepare_layout(self):
        form_layout = QFormLayout()
        form_layout.addRow("Track:", self.track_edit)
        form_layout.addRow("Car:", self.car_edit)
        form_layout.addRow("Rank:", self.rank_edit)
        form_layout.addRow("Time:", self.time_edit)
        form_layout.addWidget(self.bad_timing_checkbox)
        form_layout.addRow("Note:", self.note_edit)

        return form_layout

    def on_car_selected(self, car):
        self.rank_edit.set_text(str(car.rank) if car and car.rank >= 0 else "")

    def prepare_item(self):
        track_id = self.tracks_completer.get_selected_item().id if self.tracks_completer.get_selected_item() else 0
        car_id = self.cars_completer.get_selected_item().id if self.cars_completer.get_selected_item() else 0
        car_name = self.car_edit.text()
        rank = int(self.rank_edit.text()) if self.rank_edit.text() else 0
        time = parse_time(self.time_edit.text())
        bad_timing = self.bad_timing_checkbox.isChecked()
        note = self.note_edit.toPlainText()

        error = False
        if track_id <= 0:
            self.track_edit.set_error()
            error = True

        if not car_name:
            self.car_edit.set_error()
            error = True

        if not time:
            self.time_edit.set_error()
            error = True

        if error:
            return None
        return RaceView(id=self.item.id, track_id=track_id, car_id=car_id, car_name=car_name, rank=rank,
                        time=time, bad_timing=bad_timing, note=note)


class RaceListWidget(ListItemWidget):
    def __init__(self, race: RaceView, parent=None):
        super().__init__(race, parent)
        self.map_label = QLabel(race.map_name)
        self.track_label = QLabel(race.track_name)
        self.car_label = QLabel(race.car_name)
        self.rank_label = QLabel(str(race.rank))

        time_font = QFont()
        # time_font.setBold(True)
        time_font.setPointSize(self.font().pointSize() + 4)

        self.time_label = QLabel(format_time(race.time))
        self.time_label.setFont(time_font)
        self.created_at_label = QLabel(race.created_at.strftime("%d.%m.%Y %H:%M:%S"))

        self.bad_timing_label = QLabel()
        if race.bad_timing:
            self.bad_timing_label.setPixmap(res_to_pixmap("icons/dislike.png", 18))

        self.info_label = QLabel()
        if race.note:
            self.info_label.setPixmap(res_to_pixmap("icons/info.png", 18))
            self.info_label.setToolTip(race.note)

        self.layout = QHBoxLayout(self)
        self.layout.addLayout(vbox([self.map_label, self.track_label], spacing=0), stretch=20)
        self.layout.addLayout(vbox([self.car_label, self.rank_label], spacing=0), stretch=20)
        self.layout.addWidget(self.time_label, stretch=10)
        self.layout.addLayout(hbox([self.bad_timing_label, self.info_label], spacing=0), stretch=8)
        self.layout.addWidget(self.created_at_label, stretch=10)
        self.setLayout(self.layout)

class RacesTab(QWidget):
    def __init__(self):
        super().__init__()

        self.track_query = QLineEdit()
        self.track_query.setClearButtonEnabled(True)
        self.track_query.installEventFilter(CLEAR_ON_ESC_FILTER)
        self.track_query.setPlaceholderText("Filter by track")
        self.track_debounce = InputDebounce(self.track_query, on_change=self.refresh)

        self.car_query = QLineEdit()
        self.car_query.setClearButtonEnabled(True)
        self.car_query.installEventFilter(CLEAR_ON_ESC_FILTER)
        self.car_query.setPlaceholderText("Filter by car")
        self.car_debounce = InputDebounce(self.car_query, on_change=self.refresh)

        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.on_add) # type: ignore

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.on_edit) # type: ignore

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.track_query)
        top_layout.addWidget(self.car_query)
        top_layout.addWidget(self.add_button)

        layout = QVBoxLayout()
        layout.addLayout(top_layout)
        layout.addWidget(self.list_widget)
        self.setLayout(layout)
        self.refresh()

    def refresh(self):
        self.list_widget.clear()
        track_query = self.track_query.text().strip()
        car_query = self.car_query.text().strip()
        for i in APP_CONTEXT.races_service.get_all(track_query, car_query):
            RaceListWidget(i).add_to_list(self.list_widget)

    def on_add(self):
        if RaceDialog(item=RaceView(), action=APP_CONTEXT.races_service.save, parent=self).exec():
            self.refresh()

    def on_edit(self, item: QListWidgetItem):
        if RaceDialog(item=item.data(Qt.ItemDataRole.UserRole), action=APP_CONTEXT.races_service.save, parent=self).exec():
            self.refresh()
