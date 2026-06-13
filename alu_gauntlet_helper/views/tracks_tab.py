# gui/tracks_tab.py
import os
from typing import Callable

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPixmap, QImage, QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QListWidget, QLineEdit, QListWidgetItem, QHBoxLayout, \
    QLabel, QFormLayout, QSplitter

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.views import style
from alu_gauntlet_helper.services.maps import Map
from alu_gauntlet_helper.services.tracks import TrackView
from alu_gauntlet_helper.utils.utils import save_data_image, DATA_PATH_MAPS, DATA_PATH_TRACKS, pixmap_cover
from alu_gauntlet_helper.views.components.common import CLEAR_ON_ESC_FILTER, ListItemWidget, enable_clear_button, \
    enable_search_icon, preserved_scroll, image_preview_html
from alu_gauntlet_helper.views.components.image_line_edit import ImageLineEdit
from alu_gauntlet_helper.views.components.edit_dialog import EditDialog
from alu_gauntlet_helper.views.components.validated_line_edit import ValidatedLineEdit
from alu_gauntlet_helper.views.components.item_completer import ItemCompleter


class MapDialog(EditDialog):
    def __init__(self, item: Map, action: Callable[[Map], int], parent=None):
        self.item = item
        self.name_edit = ValidatedLineEdit(item.name)
        icon = QImage(item.icon) if item.icon and os.path.exists(item.icon) else None
        self.icon_edit = ImageLineEdit(icon)

        super().__init__(action, parent)
        self.setWindowTitle("Edit Map" if item.id else "Add Map")

    def prepare_layout(self):
        form_layout = QFormLayout()
        form_layout.addRow("Name", self.name_edit)
        form_layout.addRow("Icon", self.icon_edit)

        return form_layout

    def prepare_item(self):
        name = self.name_edit.text()
        icon = self.icon_edit.get_image()
        icon_path = ""

        if not name:
            self.name_edit.set_error()
            return None

        if icon:
            icon_path = save_data_image(DATA_PATH_MAPS, icon)

        return Map(id=self.item.id, name=name, icon = icon_path)


class MapListWidget(ListItemWidget):
    def __init__(self, item: Map, parent=None):
        super().__init__(item, parent)
        self.map_icon = QLabel()
        self.map_icon.setFixedSize(64, 64)
        self.map_icon.setStyleSheet("""
            border-radius: 4px;
            background-color: #271A62;
        """)
        self.map_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if item.icon and os.path.exists(item.icon):
            self.map_icon.setPixmap(pixmap_cover(QPixmap(item.icon), w=self.map_icon.width(), h=self.map_icon.height()))
        self.map_label = QLabel(item.name.upper())

        name_font = QFont()
        name_font.setPointSize(self.font().pointSize() + 3)
        name_font.setBold(True)
        self.map_label.setFont(name_font)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.setSpacing(8)
        self.layout.addWidget(self.map_icon)
        self.layout.addWidget(self.map_label, stretch=1)
        self.setLayout(self.layout)


class TrackDialog(EditDialog):
    def __init__(self, item: TrackView, action: Callable[[TrackView], int], parent=None):
        self.item = item

        self.map_edit = ValidatedLineEdit(item.map_name)
        self.name_edit = ValidatedLineEdit(item.name)
        icon = QImage(item.icon) if item.icon and os.path.exists(item.icon) else None
        self.icon_edit = ImageLineEdit(icon)

        self.maps_completer = ItemCompleter(
            self.map_edit.get_input(),
            autocomplete=APP_CONTEXT.maps_service.autocomplete,
            presentation=lambda i: i.name
        )

        super().__init__(action, parent)
        self.setWindowTitle("Edit Track" if item.id else "Add Track")

    def prepare_layout(self):
        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel("Map"))
        form_layout.addWidget(self.map_edit)
        form_layout.addWidget(QLabel("Name"))
        form_layout.addWidget(self.name_edit)
        form_layout.addWidget(QLabel("Icon"))
        form_layout.addWidget(self.icon_edit)

        return form_layout

    def prepare_item(self):
        map_id = self.maps_completer.get_selected_item().id if self.maps_completer.get_selected_item() else 0
        map_name = self.map_edit.text()
        name = self.name_edit.text()
        icon = self.icon_edit.get_image()
        icon_path = ""

        error = False
        if not map_name:
            self.map_edit.set_error()
            error = True

        if not name:
            self.name_edit.set_error()
            error = True

        if error:
            return None

        if icon:
            icon_path = save_data_image(DATA_PATH_TRACKS, icon)

        # одне зображення для обох полів: повна іконка == превʼю (того самого файлу)
        return TrackView(id=self.item.id, map_id=map_id, map_name=map_name, name=name,
                         icon=icon_path, icon_preview=icon_path)


class TrackListWidget(ListItemWidget):
    def __init__(self, item: TrackView, parent=None):
        super().__init__(item, parent)
        self.track_icon = QLabel()
        self.track_icon.setFixedSize(64, 64)
        self.track_icon.setStyleSheet("""
            border-radius: 4px;
            background-color: #271A62;
        """)
        self.track_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        thumb = item.icon_preview if item.icon_preview and os.path.exists(item.icon_preview) else item.icon
        if thumb and os.path.exists(thumb):
            self.track_icon.setPixmap(pixmap_cover(QPixmap(thumb), w=self.track_icon.width(), h=self.track_icon.height()))
        if item.icon and os.path.exists(item.icon):
            preview = image_preview_html(item.icon)
            if preview:
                self.track_icon.setToolTip(preview)

        self.map_label = QLabel(item.map_name)
        self.map_label.setStyleSheet(f"color: {style.TEXT_MUTED}; font-size: 13px; font-weight: bold;")

        self.track_label = QLabel(item.name.upper())
        name_font = QFont()
        name_font.setPointSize(self.font().pointSize() + 3)
        name_font.setBold(True)
        self.track_label.setFont(name_font)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(3)
        text_layout.addStretch()
        text_layout.addWidget(self.map_label)
        text_layout.addWidget(self.track_label)
        text_layout.addStretch()

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.setSpacing(8)
        self.layout.addWidget(self.track_icon)
        self.layout.addLayout(text_layout, stretch=1)
        self.setLayout(self.layout)


class MapsPanel(QWidget):
    def __init__(self, on_changed: Callable[[], None] | None = None,
                 on_map_selected: Callable[[int | None], None] | None = None):
        super().__init__()
        self.on_changed = on_changed
        self.on_map_selected = on_map_selected
        self.selected_map_id: int | None = None

        self.query = QLineEdit()
        enable_search_icon(self.query)
        enable_clear_button(self.query)
        self.query.installEventFilter(CLEAR_ON_ESC_FILTER)
        self.query.textChanged.connect(self.refresh_debounce) # type: ignore

        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.on_add) # type: ignore

        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.on_item_clicked) # type: ignore
        self.list_widget.itemDoubleClicked.connect(self.on_edit) # type: ignore

        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self.on_search) # type: ignore

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.query)
        top_layout.addWidget(self.add_button)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(top_layout)
        layout.addWidget(self.list_widget)
        self.setLayout(layout)
        self.refresh()

    def refresh_debounce(self):
        self.debounce_timer.start(300)

    def refresh(self):
        with preserved_scroll(self.list_widget):
            self.list_widget.clear()
            for i in APP_CONTEXT.maps_service.autocomplete(self.query.text()):
                MapListWidget(i).add_to_list(self.list_widget)

        # restore selection after the list is rebuilt
        for row in range(self.list_widget.count()):
            list_item = self.list_widget.item(row)
            if list_item.data(Qt.ItemDataRole.UserRole).id == self.selected_map_id:
                list_item.setSelected(True)
                break

    def on_search(self):
        self.refresh()
        self.list_widget.scrollToTop()  # фільтр змінився — результати з початку

    def on_item_clicked(self, item: QListWidgetItem):
        map_ = item.data(Qt.ItemDataRole.UserRole)
        if self.selected_map_id == map_.id:
            self.selected_map_id = None
            self.list_widget.clearSelection()
        else:
            self.selected_map_id = map_.id

        if self.on_map_selected:
            self.on_map_selected(self.selected_map_id)

    def on_add(self):
        if MapDialog(item=Map(name=self.query.text().strip()), action=APP_CONTEXT.maps_service.save, parent=self).exec():
            self.refresh()
            if self.on_changed:
                self.on_changed()

    def on_edit(self, item: QListWidgetItem):
        if MapDialog(item=item.data(Qt.ItemDataRole.UserRole), action=APP_CONTEXT.maps_service.save, parent=self).exec():
            self.refresh()
            if self.on_changed:
                self.on_changed()


class TracksPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.map_id: int | None = None

        self.query = QLineEdit()
        enable_search_icon(self.query)
        enable_clear_button(self.query)
        self.query.installEventFilter(CLEAR_ON_ESC_FILTER)
        self.query.textChanged.connect(self.refresh_debounce) # type: ignore

        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.on_add) # type: ignore

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.on_edit) # type: ignore

        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self.on_search) # type: ignore

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.query)
        top_layout.addWidget(self.add_button)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(top_layout)
        layout.addWidget(self.list_widget)
        self.setLayout(layout)
        self.refresh()

    def refresh_debounce(self):
        self.debounce_timer.start(300)

    def set_map_filter(self, map_id: int | None):
        self.map_id = map_id
        self.on_search()

    def refresh(self):
        with preserved_scroll(self.list_widget):
            self.list_widget.clear()
            for t in APP_CONTEXT.tracks_service.autocomplete(self.query.text(), self.map_id):
                TrackListWidget(t).add_to_list(self.list_widget)

    def on_search(self):
        self.refresh()
        self.list_widget.scrollToTop()  # фільтр змінився — результати з початку

    def on_add(self):
        item = TrackView(name=self.query.text().strip())
        if self.map_id:
            map_ = APP_CONTEXT.maps_service.get_by_ids({self.map_id}).get(self.map_id)
            if map_:
                item.map_id = map_.id
                item.map_name = map_.name

        if TrackDialog(item=item, action=APP_CONTEXT.tracks_service.save, parent=self).exec():
            self.refresh()

    def on_edit(self, item: QListWidgetItem):
        if TrackDialog(item=item.data(Qt.ItemDataRole.UserRole), action=APP_CONTEXT.tracks_service.save, parent=self).exec():
            self.refresh()


class TracksTab(QWidget):
    def __init__(self):
        super().__init__()

        self.tracks_panel = TracksPanel()
        self.maps_panel = MapsPanel(on_changed=self.tracks_panel.refresh,
                                    on_map_selected=self.tracks_panel.set_map_filter)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.maps_panel)
        self.splitter.addWidget(self.tracks_panel)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setStretchFactor(0, 40)
        self.splitter.setStretchFactor(1, 60)
        self.splitter_sized = False

        layout = QHBoxLayout()
        layout.addWidget(self.splitter)
        self.setLayout(layout)

    def showEvent(self, event):
        super().showEvent(event)
        # the real width is unknown until the widget is shown, so the 40/60
        # default split is applied on the first show only
        if not self.splitter_sized:
            self.splitter_sized = True
            left = int(self.splitter.width() * 0.4)
            self.splitter.setSizes([left, self.splitter.width() - left])

    def refresh(self):
        self.maps_panel.refresh()
        self.tracks_panel.refresh()
