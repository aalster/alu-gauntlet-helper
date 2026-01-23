# gui/tracks_tab.py
import os
from typing import Callable

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QListWidget, QLineEdit, QListWidgetItem, QHBoxLayout, \
    QLabel

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.tracks import TrackView
from alu_gauntlet_helper.utils.utils import pixmap_cover
from alu_gauntlet_helper.views.components.common import CLEAR_ON_ESC_FILTER, ListItemWidget
from alu_gauntlet_helper.views.components.edit_dialog import EditDialog
from alu_gauntlet_helper.views.components.validated_line_edit import ValidatedLineEdit
from alu_gauntlet_helper.views.components.item_completer import ItemCompleter


class TrackDialog(EditDialog):
    def __init__(self, item: TrackView, action: Callable[[TrackView], int], parent=None):
        self.item = item

        self.map_edit = ValidatedLineEdit(item.map_name)
        self.name_edit = ValidatedLineEdit(item.name)

        self.maps_completer = ItemCompleter(
            self.map_edit.get_input(),
            autocomplete=APP_CONTEXT.maps_service.autocomplete,
            presentation=lambda i: i.name
        )

        super().__init__(action, parent)
        self.setWindowTitle("Edit Track" if item.id else "Add Track")

    def prepare_layout(self):
        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel("Map:"))
        form_layout.addWidget(self.map_edit)
        form_layout.addWidget(QLabel("Name:"))
        form_layout.addWidget(self.name_edit)

        return form_layout

    def prepare_item(self):
        map_id = self.maps_completer.get_selected_item().id if self.maps_completer.get_selected_item() else 0
        map_name = self.map_edit.text()
        name = self.name_edit.text()

        error = False
        if not map_name:
            self.map_edit.set_error()
            error = True

        if not name:
            self.name_edit.set_error()
            error = True

        if error:
            return None

        return TrackView(id=self.item.id, map_id=map_id, map_name=map_name, name=name)


class TrackListWidget(ListItemWidget):
    def __init__(self, item: TrackView, parent=None):
        super().__init__(item, parent)
        self.map_icon = QLabel()
        self.map_icon.setFixedSize(64, 64)
        self.map_icon.setStyleSheet("""
            border: 1px solid #aaa;
            background-color: #271A62;
        """)
        self.map_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if item.map_icon and os.path.exists(item.map_icon):
            self.map_icon.setPixmap(pixmap_cover(QPixmap(item.map_icon), w=self.map_icon.width(), h=self.map_icon.height()))

        self.map_label = QLabel(item.map_name)

        self.track_label = QLabel(item.name)
        name_font = QFont()
        name_font.setPointSize(self.font().pointSize() + 4)
        self.track_label.setFont(name_font)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)
        text_layout.addStretch()
        text_layout.addWidget(self.map_label)
        text_layout.addWidget(self.track_label)
        text_layout.addStretch()

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.setSpacing(8)
        self.layout.addWidget(self.map_icon)
        self.layout.addLayout(text_layout, stretch=1)
        self.setLayout(self.layout)


class TracksTab(QWidget):
    def __init__(self):
        super().__init__()

        self.query = QLineEdit()
        self.query.setClearButtonEnabled(True)
        self.query.installEventFilter(CLEAR_ON_ESC_FILTER)
        self.query.setPlaceholderText("Filter by name")
        self.query.textChanged.connect(self.refresh_debounce) # type: ignore

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
        for t in APP_CONTEXT.tracks_service.autocomplete(self.query.text()):
            TrackListWidget(t).add_to_list(self.list_widget)

    def on_add(self):
        if TrackDialog(item=TrackView(name=self.query.text().strip()), action=APP_CONTEXT.tracks_service.save, parent=self).exec():
            self.refresh()

    def on_edit(self, item: QListWidgetItem):
        if TrackDialog(item=item.data(Qt.ItemDataRole.UserRole), action=APP_CONTEXT.tracks_service.save, parent=self).exec():
            self.refresh()
