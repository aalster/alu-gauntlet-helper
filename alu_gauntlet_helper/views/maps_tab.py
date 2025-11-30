# gui/maps_tab.py
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPixmap, QImage, QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QListWidget, QLineEdit, QListWidgetItem, QHBoxLayout, \
    QLabel, QFormLayout

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.maps import Map
from alu_gauntlet_helper.utils.utils import save_data_image, DATA_PATH_MAPS, pixmap_cover
from alu_gauntlet_helper.views.components import EditDialog, ValidatedLineEdit, CLEAR_ON_ESC_FILTER, ImageLineEdit


class MapDialog(EditDialog):
    def __init__(self, item: Map, action, parent=None):
        self.item = item
        self.name_edit = ValidatedLineEdit(item.name)
        icon = QImage(item.icon) if item.icon else None
        self.icon_edit = ImageLineEdit(icon)

        super().__init__(action, parent)
        self.setWindowTitle("Edit Map" if item.id else "Add Map")

    def prepare_layout(self):
        form_layout = QFormLayout()
        form_layout.addRow("Name:", self.name_edit)
        form_layout.addRow("Icon:", self.icon_edit)

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


class MapListWidget(QWidget):
    def __init__(self, item: Map, parent=None):
        super().__init__(parent)
        self.map_icon = QLabel()
        self.map_icon.setFixedSize(64, 64)
        self.map_icon.setStyleSheet("""
            border: 1px solid #aaa;
            background-color: #271A62;
        """)
        self.map_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if item.icon:
            self.map_icon.setPixmap(pixmap_cover(QPixmap(item.icon), w=self.map_icon.width(), h=self.map_icon.height()))
        self.map_label = QLabel(item.name)

        name_font = QFont()
        name_font.setPointSize(self.font().pointSize() + 4)
        self.map_label.setFont(name_font)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.setSpacing(8)
        self.layout.addWidget(self.map_icon)
        self.layout.addWidget(self.map_label, stretch=1)
        self.setLayout(self.layout)

class MapsTab(QWidget):
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
        for i in APP_CONTEXT.maps_service.autocomplete(self.query.text()):
            map_widget = MapListWidget(i)

            item = QListWidgetItem(self.list_widget)
            item.setData(Qt.ItemDataRole.UserRole, i)
            item.setSizeHint(map_widget.sizeHint())

            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, map_widget)

    def on_add(self):
        if MapDialog(item=Map(name=self.query.text().strip()), action=APP_CONTEXT.maps_service.save, parent=self).exec():
            self.refresh()

    def on_edit(self, item: QListWidgetItem):
        if MapDialog(item=item.data(Qt.ItemDataRole.UserRole), action=APP_CONTEXT.maps_service.save, parent=self).exec():
            self.refresh()
