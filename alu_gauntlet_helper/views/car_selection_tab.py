from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QHBoxLayout, QLabel, QListWidgetItem, QScrollArea, QFrame, QPushButton, QDialog

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.races import CarSuggestion, Race
from alu_gauntlet_helper.utils.utils import format_time, load_pixmap_cover
from alu_gauntlet_helper.views.components.common import ListItemWidget
from alu_gauntlet_helper.views.components.item_completer import ItemCompleter
from alu_gauntlet_helper.views.components.validated_line_edit import ValidatedLineEdit


class RaceHistoryDialog(QDialog):
    def __init__(self, car_name: str, races: list[Race], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Race History - {car_name}")
        self.setMinimumSize(350, 250)

        self.list_widget = QListWidget()
        for race in races:
            date_str = race.created_at.strftime("%Y-%m-%d %H:%M:%S") if race.created_at else "—"
            rank_str = f"Rank {race.rank}" if race.rank else "—"
            time_str = format_time(race.time)
            item = QListWidgetItem(f"{date_str}    {rank_str}    {time_str}")
            self.list_widget.addItem(item)

        layout = QVBoxLayout()
        layout.addWidget(self.list_widget)
        self.setLayout(layout)


class CarSuggestionWidget(ListItemWidget):
    def __init__(self, item: CarSuggestion, track_id: int, parent=None):
        super().__init__(item, parent)
        self.car_id = item.car_id
        self.car_name = item.car_name
        self.track_id = track_id

        self.car_icon = QLabel()
        self.car_icon.setFixedSize(96, 48)
        self.car_icon.setStyleSheet("""
            border: 1px solid #aaa;
            background-color: #271A62;
        """)
        self.car_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if item.car_icon:
            pixmap = load_pixmap_cover(item.car_icon, w=self.car_icon.width(), h=self.car_icon.height())
            if pixmap:
                self.car_icon.setPixmap(pixmap)

        self.brand_label = QLabel(item.car_brand)
        self.brand_label.setStyleSheet("color: #888; font-size: 11px;")
        if not item.car_brand:
            # hide() only - setVisible(True) on a not-yet-parented widget pops up a window
            self.brand_label.hide()

        self.car_label = QLabel(item.car_model or item.car_name)
        self.car_label.setWordWrap(True)

        rank_parts = []
        if item.car_favorite:
            rank_parts.append("♥")
        if item.car_class:
            rank_parts.append(f"Class {item.car_class}")
        if item.car_rank:
            rank_parts.append(f"Rank: {item.car_rank}")
        self.rank_label = QLabel(" · ".join(rank_parts))
        self.rank_label.setStyleSheet("color: #888; font-size: 12px;")

        self.time_label = QLabel(format_time(item.avg_time))
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.race_count_button = QPushButton(f"{item.race_count} races")
        self.race_count_button.setStyleSheet("""
            QPushButton {
                padding: 2px 8px;
            }
        """)
        self.race_count_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.race_count_button.clicked.connect(self.show_race_history)

        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        left_layout.addWidget(self.brand_label)
        left_layout.addWidget(self.car_label)
        left_layout.addWidget(self.rank_label)

        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self.time_label)
        right_layout.addWidget(self.race_count_button, alignment=Qt.AlignmentFlag.AlignRight)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.setSpacing(4)
        self.layout.addWidget(self.car_icon)
        self.layout.addLayout(left_layout, stretch=1)
        self.layout.addLayout(right_layout)
        self.setLayout(self.layout)

    def show_race_history(self):
        races = APP_CONTEXT.races_service.get_recent_races_for_car_on_track(self.track_id, self.car_id)
        RaceHistoryDialog(self.car_name, races, self).exec()

    def set_dimmed(self, dimmed: bool):
        self.brand_label.setEnabled(not dimmed)
        self.car_label.setEnabled(not dimmed)
        self.time_label.setEnabled(not dimmed)
        self.car_icon.setEnabled(not dimmed)
        self.race_count_button.setEnabled(not dimmed)


class RaceColumn(QWidget):
    def __init__(self, race_number: int, on_car_selected: Callable[[int, int | None], None], get_selected_cars: Callable[[], dict[int, int]], parent=None):
        super().__init__(parent)
        self.setMinimumWidth(300)
        self.race_number = race_number
        self.selected_track = None
        self.selected_car_id: int | None = None
        self.on_car_selected = on_car_selected
        self.get_selected_cars = get_selected_cars

        self.header_label = QLabel(f"Race {race_number}")
        header_font = QFont()
        header_font.setBold(True)
        self.header_label.setFont(header_font)
        self.header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.track_edit = ValidatedLineEdit(placeholder="Select track...")
        self.track_edit.get_input().setClearButtonEnabled(True)
        self.track_edit.get_input().textChanged.connect(self.on_track_text_changed)
        self.track_completer = ItemCompleter(
            self.track_edit.get_input(),
            autocomplete=APP_CONTEXT.tracks_service.autocomplete,
            presentation=lambda i: f"{i.map_name} - {i.name}",
            allow_custom_text=False,
            selected_listener=self.on_track_selected
        )

        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.show_status("Select a track")

        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.addWidget(self.header_label)
        layout.addWidget(self.track_edit)
        layout.addWidget(self.list_widget)
        self.setLayout(layout)

    def show_status(self, text: str):
        self.list_widget.clear()
        item = QListWidgetItem()
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        label = QLabel(text)
        label.setStyleSheet("color: #888; font-style: italic;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setContentsMargins(8, 16, 8, 16)
        item.setSizeHint(label.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, label)

    def on_track_text_changed(self, text: str):
        if not text:
            self.selected_track = None
            self.selected_car_id = None
            self.on_car_selected(self.race_number, None)
            self.show_status("Select a track")

    def on_track_selected(self, track):
        self.selected_track = track
        self.selected_car_id = None
        self.on_car_selected(self.race_number, None)
        self.refresh_suggestions()

    def on_item_clicked(self, item: QListWidgetItem):
        widget = self.list_widget.itemWidget(item)
        if not isinstance(widget, CarSuggestionWidget):
            return

        car_id = widget.car_id
        selected_cars = self.get_selected_cars()

        if car_id in selected_cars and selected_cars[car_id] != self.race_number:
            self.on_car_selected(selected_cars[car_id], None)

        if self.selected_car_id == car_id:
            self.selected_car_id = None
            self.on_car_selected(self.race_number, None)
        else:
            self.selected_car_id = car_id
            self.on_car_selected(self.race_number, car_id)

    def refresh_suggestions(self):
        self.list_widget.clear()

        if not self.selected_track or self.selected_track.id <= 0:
            self.show_status("Select a track")
            return

        suggestions = APP_CONTEXT.races_service.get_car_suggestions_for_track(self.selected_track.id)

        if not suggestions:
            self.show_status("No race data")
            return

        for suggestion in suggestions:
            CarSuggestionWidget(suggestion, self.selected_track.id).add_to_list(self.list_widget)

        self.update_dimming()

    def update_dimming(self):
        selected_cars = self.get_selected_cars()

        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if isinstance(widget, CarSuggestionWidget):
                is_selected_elsewhere = widget.car_id in selected_cars and selected_cars[widget.car_id] != self.race_number
                is_selected_here = widget.car_id == self.selected_car_id
                widget.set_dimmed(is_selected_elsewhere)
                item.setSelected(is_selected_here)

    def refresh(self):
        if self.selected_track:
            self.refresh_suggestions()

    def clear_selection_for_car(self, car_id: int):
        if self.selected_car_id == car_id:
            self.selected_car_id = None


class CarSelectionTab(QWidget):
    RACE_COUNT = 5

    def __init__(self):
        super().__init__()

        self.columns: list[RaceColumn] = []
        self.selected_cars: dict[int, int] = {}

        columns_container = QWidget()
        columns_layout = QHBoxLayout(columns_container)
        columns_layout.setSpacing(8)
        columns_layout.setContentsMargins(0, 0, 0, 0)

        for i in range(self.RACE_COUNT):
            column = RaceColumn(i + 1, self.on_car_selected, self.get_selected_cars)
            self.columns.append(column)
            columns_layout.addWidget(column)

        scroll_area = QScrollArea()
        scroll_area.setWidget(columns_container)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll_area)
        self.setLayout(layout)

    def get_selected_cars(self) -> dict[int, int]:
        return self.selected_cars

    def on_car_selected(self, race_number: int, car_id: int | None):
        cars_to_remove = [cid for cid, rn in self.selected_cars.items() if rn == race_number]
        for cid in cars_to_remove:
            del self.selected_cars[cid]

        if car_id is not None:
            if car_id in self.selected_cars:
                old_race = self.selected_cars[car_id]
                self.columns[old_race - 1].clear_selection_for_car(car_id)
            self.selected_cars[car_id] = race_number

        for column in self.columns:
            column.update_dimming()

    def refresh(self):
        for column in self.columns:
            column.refresh()
