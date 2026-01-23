import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QHBoxLayout, QLabel, QFormLayout

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.races import CarSuggestion
from alu_gauntlet_helper.utils.utils import format_time, pixmap_cover
from alu_gauntlet_helper.views.components.common import ListItemWidget
from alu_gauntlet_helper.views.components.item_completer import ItemCompleter
from alu_gauntlet_helper.views.components.validated_line_edit import ValidatedLineEdit


class CarSuggestionWidget(ListItemWidget):
    def __init__(self, item: CarSuggestion, parent=None):
        super().__init__(item, parent)

        self.car_icon = QLabel()
        self.car_icon.setFixedSize(64, 64)
        self.car_icon.setStyleSheet("""
            border: 1px solid #aaa;
            background-color: #271A62;
        """)
        self.car_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if item.car_icon and os.path.exists(item.car_icon):
            self.car_icon.setPixmap(pixmap_cover(QPixmap(item.car_icon), w=self.car_icon.width(), h=self.car_icon.height()))

        self.car_label = QLabel(item.car_name)
        name_font = QFont()
        name_font.setPointSize(self.font().pointSize() + 4)
        self.car_label.setFont(name_font)

        self.rank_label = QLabel(f"Rank: {item.car_rank}" if item.car_rank else "")
        self.rank_label.setStyleSheet("color: #888;")

        self.time_label = QLabel(format_time(item.avg_time))
        time_font = QFont()
        time_font.setPointSize(self.font().pointSize() + 4)
        self.time_label.setFont(time_font)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.race_count_label = QLabel(f"({item.race_count} races)")
        self.race_count_label.setStyleSheet("color: #888;")
        self.race_count_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)
        left_layout.addWidget(self.car_label)
        left_layout.addWidget(self.rank_label)

        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(2)
        right_layout.addWidget(self.time_label)
        right_layout.addWidget(self.race_count_label)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.setSpacing(8)
        self.layout.addWidget(self.car_icon)
        self.layout.addLayout(left_layout, stretch=1)
        self.layout.addLayout(right_layout)
        self.setLayout(self.layout)


class CarSelectionTab(QWidget):
    def __init__(self):
        super().__init__()

        self.selected_track = None

        self.track_edit = ValidatedLineEdit(placeholder="Select track...")
        self.track_completer = ItemCompleter(
            self.track_edit.get_input(),
            autocomplete=APP_CONTEXT.tracks_service.autocomplete,
            presentation=lambda i: f"{i.map_name} - {i.name}",
            allow_custom_text=False,
            selected_listener=self.on_track_selected
        )

        self.info_label = QLabel("Select a track to see car suggestions")
        self.info_label.setStyleSheet("color: #888; font-style: italic;")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.list_widget = QListWidget()

        form_layout = QFormLayout()
        form_layout.addRow("Track:", self.track_edit)

        layout = QVBoxLayout()
        layout.addLayout(form_layout)
        layout.addWidget(self.info_label)
        layout.addWidget(self.list_widget)
        self.setLayout(layout)

    def on_track_selected(self, track):
        self.selected_track = track
        self.refresh_suggestions()

    def refresh_suggestions(self):
        self.list_widget.clear()

        if not self.selected_track or self.selected_track.id <= 0:
            self.info_label.setText("Select a track to see car suggestions")
            self.info_label.show()
            return

        suggestions = APP_CONTEXT.races_service.get_car_suggestions_for_track(self.selected_track.id)

        if not suggestions:
            self.info_label.setText("No race data for this track")
            self.info_label.show()
            return

        self.info_label.hide()
        for suggestion in suggestions:
            CarSuggestionWidget(suggestion).add_to_list(self.list_widget)

    def refresh(self):
        if self.selected_track:
            self.refresh_suggestions()
