# gui/cars_tab.py
import os
from typing import Callable

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QIntValidator, QImage, QFont, QIcon
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QListWidget, QLineEdit, QListWidgetItem, QHBoxLayout, \
    QLabel, QFormLayout, QComboBox, QButtonGroup

from alu_gauntlet_helper import ui_lang
from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.cars import Car
from alu_gauntlet_helper.views import style
from alu_gauntlet_helper.utils.utils import save_data_image, DATA_PATH_CARS, load_pixmap_cover, get_resource_path
from alu_gauntlet_helper.views.components.common import CLEAR_ON_ESC_FILTER, ListItemWidget, vbox, \
    enable_clear_button, enable_search_icon, RankClassBadge, preserved_scroll, set_lazy_image_tooltip, \
    edit_icon_button
from alu_gauntlet_helper.views.components.image_line_edit import ImageLineEdit
from alu_gauntlet_helper.views.components.edit_dialog import EditDialog
from alu_gauntlet_helper.views.components.validated_line_edit import ValidatedLineEdit


class CarDialog(EditDialog):
    def __init__(self, item: Car, action: Callable[[Car], int], parent=None):
        self.item = item
        self.brand_edit = ValidatedLineEdit(item.brand)
        self.model_edit = ValidatedLineEdit(item.model or item.name)
        self.rank_edit = ValidatedLineEdit(str(item.rank) if item.rank else "")
        self.rank_edit.get_input().setValidator(QIntValidator(0, 10000))
        if item.max_rank:
            rank_input = self.rank_edit.get_input()
            max_rank_label = QLabel(f"/ {item.max_rank}", rank_input)
            max_rank_label.setStyleSheet(f"color: {style.TEXT_MUTED}; background: transparent;")
            overlay = QHBoxLayout(rank_input)
            overlay.setContentsMargins(0, 0, 8, 0)
            overlay.addWidget(max_rank_label, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            rank_input.setTextMargins(0, 0, max_rank_label.sizeHint().width() + 12, 0)
        self.max_rank_button = QPushButton(ui_lang.t("cars.max"))
        self.max_rank_button.setObjectName("secondary")
        self.max_rank_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.max_rank_button.setEnabled(bool(item.max_rank))
        self.max_rank_button.clicked.connect(lambda: self.rank_edit.set_text(str(self.item.max_rank))) # type: ignore
        icon = QImage(item.icon) if item.icon and os.path.exists(item.icon) else None
        self.icon_edit = ImageLineEdit(icon)

        super().__init__(action, parent)
        self.setWindowTitle(ui_lang.t("dialog.edit_car") if item.id else ui_lang.t("dialog.add_car"))
        self.setMinimumHeight(400)

    def prepare_layout(self):
        form_layout = QFormLayout()
        form_layout.addRow(ui_lang.t("field.brand"), self.brand_edit)
        form_layout.addRow(ui_lang.t("field.model"), self.model_edit)
        rank_layout = QHBoxLayout()
        rank_layout.setSpacing(6)
        rank_layout.addWidget(self.rank_edit, stretch=1)
        rank_layout.addWidget(self.max_rank_button)
        form_layout.addRow(ui_lang.t("field.rank"), rank_layout)
        form_layout.addRow(ui_lang.t("field.icon"), self.icon_edit)

        return form_layout

    def prepare_item(self):
        brand = self.brand_edit.text().strip()
        model = self.model_edit.text().strip()
        rank = int(self.rank_edit.text()) if self.rank_edit.text() else 0
        icon = self.icon_edit.get_image()
        icon_path = ""

        if not model:
            self.model_edit.set_error()
            return None

        if icon:
            icon_path = save_data_image(DATA_PATH_CARS, icon)

        return Car(id=self.item.id, asec_id=self.item.asec_id, name=f"{brand} {model}".strip(),
                   brand=brand, model=model, car_class=self.item.car_class,
                   rank=rank, max_rank=self.item.max_rank, favorite=self.item.favorite, icon=icon_path)


class CarListWidget(ListItemWidget):
    def __init__(self, item: Car, on_favorite: Callable[[int], None] | None = None,
                 on_edit: Callable[[Car], None] | None = None, parent=None):
        super().__init__(item, parent)
        self.on_favorite = on_favorite
        self.car_icon = QLabel()
        self.car_icon.setFixedSize(128, 64)
        self.car_icon.setStyleSheet("""
            border-radius: 4px;
            background-color: #271A62;
        """)
        self.car_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if item.icon:
            pixmap = load_pixmap_cover(item.icon, w=self.car_icon.width(), h=self.car_icon.height())
            if pixmap:
                self.car_icon.setPixmap(pixmap)
            set_lazy_image_tooltip(self.car_icon, item.icon)

        self.brand_label = QLabel(item.brand.upper())
        self.brand_label.setStyleSheet(f"color: {style.TEXT_MUTED}; font-size: 13px; font-weight: bold;")

        self.model_label = QLabel((item.model or item.name).upper())
        name_font = QFont()
        name_font.setPointSize(self.font().pointSize() + 3)
        name_font.setBold(True)
        self.model_label.setFont(name_font)

        self.rank_badge = RankClassBadge(item.rank, item.max_rank, item.car_class)

        self.fav_button = QPushButton()
        self.fav_button.setFlat(True)
        self.fav_button.setFixedSize(32, 32)
        self.fav_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fav_button.clicked.connect(self.toggle_favorite) # type: ignore
        self.update_fav_button()

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(6, 6, 6, 6)
        self.layout.setSpacing(10)
        self.layout.addWidget(self.car_icon)
        self.layout.addLayout(vbox([self.brand_label, self.model_label], spacing=0), stretch=1)
        self.layout.addWidget(self.rank_badge, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.layout.addWidget(self.fav_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        if on_edit:
            self.layout.addWidget(edit_icon_button(lambda: on_edit(item)),
                                  alignment=Qt.AlignmentFlag.AlignVCenter)
        self.setLayout(self.layout)

    def update_fav_button(self):
        favorite = self.item.favorite
        self.fav_button.setText("♥" if favorite else "♡")
        color = style.FAVORITE if favorite else style.TEXT_FAINT
        self.fav_button.setStyleSheet(
            f"QPushButton {{ color: {color}; font-size: 24px; border: none; background: transparent; padding: 0; }}")

    def toggle_favorite(self):
        if self.on_favorite:
            self.on_favorite(self.item.id)
            # рядок оновлюється на місці — список не перебудовується і не міняє порядок
            self.item.favorite = not self.item.favorite
            self.update_fav_button()


class CarsTab(QWidget):
    def __init__(self):
        super().__init__()

        self.query = QLineEdit()
        enable_search_icon(self.query)
        enable_clear_button(self.query)
        self.query.installEventFilter(CLEAR_ON_ESC_FILTER)
        self.query.textChanged.connect(self.refresh_debounce) # type: ignore

        self.class_group = QButtonGroup(self)
        self.class_layout = QHBoxLayout()
        self.class_layout.setSpacing(0)
        classes = ["All", "D", "C", "B", "A", "S"]
        for index, car_class in enumerate(classes):
            # parent keeps the button alive: QButtonGroup.addButton() doesn't take ownership
            # текст кнопки локалізований лише для "All"; логічне значення класу
            # тримаємо в property, бо фільтр порівнює саме значення, а не підпис
            label = ui_lang.t("cars.filter_all") if car_class == "All" else car_class
            button = QPushButton(label, self)
            button.setProperty("car_class", car_class)
            button.setObjectName("segment")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setProperty("first", index == 0)
            button.setProperty("last", index == len(classes) - 1)
            self.class_group.addButton(button)
            self.class_layout.addWidget(button)
        self.class_group.buttons()[0].setChecked(True)
        self.class_group.buttonClicked.connect(self.on_filter_changed) # type: ignore

        self.sort_combo = QComboBox()
        sort_icon = QIcon(get_resource_path("icons/sort.svg"))
        self.sort_combo.addItem(sort_icon, ui_lang.t("cars.sort_default"))
        self.sort_combo.addItem(sort_icon, ui_lang.t("cars.sort_max_rank"))
        self.sort_combo.setToolTip(ui_lang.t("cars.sort_order"))
        self.sort_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sort_combo.currentIndexChanged.connect(self.on_filter_changed) # type: ignore

        self.add_button = QPushButton(ui_lang.t("common.add"))
        self.add_button.clicked.connect(self.on_add) # type: ignore

        self.list_widget = QListWidget()

        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self.on_filter_changed) # type: ignore

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.query)
        top_layout.addLayout(self.class_layout)
        top_layout.addWidget(self.sort_combo)
        top_layout.addWidget(self.add_button)

        layout = QVBoxLayout()
        layout.addLayout(top_layout)
        layout.addWidget(self.list_widget)
        self.setLayout(layout)
        self.refresh()

    def refresh_debounce(self):
        self.debounce_timer.start(300)

    def refresh(self):
        with preserved_scroll(self.list_widget):
            self.list_widget.clear()
            car_class = self.class_group.checkedButton().property("car_class")
            for i in APP_CONTEXT.cars_service.autocomplete(self.query.text(),
                                                           by_max_rank=self.sort_combo.currentIndex() == 1,
                                                           car_class="" if car_class == "All" else car_class):
                CarListWidget(i, on_favorite=self.on_favorite, on_edit=self.on_edit).add_to_list(self.list_widget)

    def on_filter_changed(self, *_):
        self.refresh()
        self.list_widget.scrollToTop()  # фільтр змінився — результати з початку

    def on_favorite(self, car_id: int):
        # без refresh(), щоб порядок не стрибав; пересортування — при повторному відкритті
        # вкладки (main_window.tab_selected робить refresh на кожне перемикання)
        APP_CONTEXT.cars_service.toggle_favorite(car_id)

    def on_add(self):
        if CarDialog(item=Car(name=self.query.text().strip()), action=APP_CONTEXT.cars_service.save, parent=self).exec():
            self.refresh()

    def on_edit(self, car: Car):
        if CarDialog(item=car, action=APP_CONTEXT.cars_service.save, parent=self).exec():
            self.refresh()
