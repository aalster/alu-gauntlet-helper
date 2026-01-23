# gui/cars_tab.py
import os
from typing import Callable

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QIntValidator, QPixmap, QImage, QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QListWidget, QLineEdit, QListWidgetItem, QHBoxLayout, \
    QLabel, QFormLayout

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.cars import Car
from alu_gauntlet_helper.utils.utils import save_data_image, DATA_PATH_CARS, pixmap_cover
from alu_gauntlet_helper.views.components.common import CLEAR_ON_ESC_FILTER, ListItemWidget
from alu_gauntlet_helper.views.components.image_line_edit import ImageLineEdit
from alu_gauntlet_helper.views.components.edit_dialog import EditDialog
from alu_gauntlet_helper.views.components.validated_line_edit import ValidatedLineEdit


class CarDialog(EditDialog):
    def __init__(self, item: Car, action: Callable[[Car], int], parent=None):
        self.item = item
        self.name_edit = ValidatedLineEdit(item.name)
        self.rank_edit = ValidatedLineEdit(str(item.rank) if item.rank else "")
        self.rank_edit.get_input().setValidator(QIntValidator(0, 10000))
        icon = QImage(item.icon) if item.icon and os.path.exists(item.icon) else None
        self.icon_edit = ImageLineEdit(icon)

        super().__init__(action, parent)
        self.setWindowTitle("Edit Car" if item.id else "Add Car")

    def prepare_layout(self):
        form_layout = QFormLayout()
        form_layout.addRow("Name:", self.name_edit)
        form_layout.addRow("Rank:", self.rank_edit)
        form_layout.addRow("Icon:", self.icon_edit)

        return form_layout

    def prepare_item(self):
        name = self.name_edit.text()
        rank = int(self.rank_edit.text()) if self.rank_edit.text() else 0
        icon = self.icon_edit.get_image()
        icon_path = ""

        if not name:
            self.name_edit.set_error()
            return None

        if icon:
            icon_path = save_data_image(DATA_PATH_CARS, icon)

        return Car(id=self.item.id, name=name, rank=rank, icon=icon_path)


class CarListWidget(ListItemWidget):
    def __init__(self, item: Car, parent=None):
        super().__init__(item, parent)
        self.car_icon = QLabel()
        self.car_icon.setFixedSize(64, 64)
        self.car_icon.setStyleSheet("""
            border: 1px solid #aaa;
            background-color: #271A62;
        """)
        self.car_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if item.icon and os.path.exists(item.icon):
            self.car_icon.setPixmap(pixmap_cover(QPixmap(item.icon), w=self.car_icon.width(), h=self.car_icon.height()))

        self.car_label = QLabel(item.name)
        name_font = QFont()
        name_font.setPointSize(self.font().pointSize() + 4)
        self.car_label.setFont(name_font)

        self.rank_label = QLabel(f"Rank: {item.rank}" if item.rank else "")
        self.rank_label.setStyleSheet("color: #888;")
        self.rank_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.setSpacing(8)
        self.layout.addWidget(self.car_icon)
        self.layout.addWidget(self.car_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.layout.addStretch(1)
        self.layout.addWidget(self.rank_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.setLayout(self.layout)


class CarsTab(QWidget):
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
        for i in APP_CONTEXT.cars_service.autocomplete(self.query.text()):
            CarListWidget(i).add_to_list(self.list_widget)

    def on_add(self):
        if CarDialog(item=Car(name=self.query.text().strip()), action=APP_CONTEXT.cars_service.save, parent=self).exec():
            self.refresh()

    def on_edit(self, item: QListWidgetItem):
        if CarDialog(item=item.data(Qt.ItemDataRole.UserRole), action=APP_CONTEXT.cars_service.save, parent=self).exec():
            self.refresh()
