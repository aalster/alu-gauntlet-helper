import os

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFormLayout,
                             QFrame, QHBoxLayout, QLabel, QPushButton, QSlider,
                             QVBoxLayout, QWidget)

from alu_gauntlet_helper import game_lang, ui_lang
from alu_gauntlet_helper.views import style
from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.capture.screen_grab import CAPTURES_DIR, list_monitors
from alu_gauntlet_helper.views.components.hotkey_edit import HotkeyEdit

# (підпис, значення для keyboard) — модифікатор активації керування оверлеєм
OVERLAY_ACTIONS_OPTIONS = [
    ("Ctrl + Alt", "ctrl+alt"),
    ("Ctrl + Shift", "ctrl+shift"),
]

# (підпис, значення) — мова контенту гри (назви карт/треків); підпис — мовою напису
GAME_LANGUAGE_OPTIONS = [
    ("English", game_lang.EN),
    ("Русский", game_lang.RU),
]

# (підпис, значення) — мова інтерфейсу застосунку; підпис — мовою напису
UI_LANGUAGE_OPTIONS = [
    ("English", ui_lang.EN),
    ("Українська", ui_lang.UK),
]

HOTKEY_INPUT_WIDTH = 200  # хоткеї/комбо не розтягуємо на всю ширину форми
CARDS_MAX_WIDTH = 640  # на широкому вікні рядки карток не розтягуємо на весь екран


class SettingsTab(QWidget):
    def __init__(self, refresh_tray_icon, apply_capture_settings=None):
        super().__init__()
        self.refresh_tray_icon = refresh_tray_icon if refresh_tray_icon else lambda _: None
        self.apply_capture_settings = apply_capture_settings or (lambda: True)

        self.show_tray_icon = QCheckBox(ui_lang.t("settings.show_tray"))
        self.show_tray_icon.checkStateChanged.connect(self.on_tray_changed)  # type: ignore

        self.close_to_tray = QCheckBox(ui_lang.t("settings.close_to_tray"))
        self.close_to_tray.checkStateChanged.connect(self.on_tray_changed)  # type: ignore

        self.start_minimized = QCheckBox(ui_lang.t("settings.start_minimized"))

        self.app_language = QComboBox()
        for label, value in UI_LANGUAGE_OPTIONS:
            self.app_language.addItem(label, value)
        # фіксована ширина: у спільному рядку з підказкою комбо інакше стискається
        # до ширини вмісту; 200 = HOTKEY_INPUT_WIDTH, як в інших полів-комбо
        self.app_language.setFixedWidth(HOTKEY_INPUT_WIDTH)
        self.app_language_hint = QLabel(ui_lang.t("settings.app_language_hint"))
        self.app_language_hint.setStyleSheet(f"color: {style.TEXT_MUTED};")
        # підказку про перезапуск ставимо в тому ж рядку, праворуч від комбо
        self.app_language_row = QHBoxLayout()
        self.app_language_row.addWidget(self.app_language)
        self.app_language_row.addWidget(self.app_language_hint)
        self.app_language_row.addStretch()

        self.game_language = QComboBox()
        for label, value in GAME_LANGUAGE_OPTIONS:
            self.game_language.addItem(label, value)
        self.game_language.setMaximumWidth(HOTKEY_INPUT_WIDTH)

        self.capture_hotkey = HotkeyEdit()
        self.overlay_hotkey = HotkeyEdit()
        # одна комбінація не може виконувати дві дії; порівнюємо з поточним
        # (можливо незбереженим) значенням сусіднього інпута
        self.capture_hotkey.validator = (
            lambda combo: ui_lang.t("hotkey.duplicate")
            if combo == self.overlay_hotkey.value() else None)
        self.overlay_hotkey.validator = (
            lambda combo: ui_lang.t("hotkey.duplicate")
            if combo == self.capture_hotkey.value() else None)
        self.overlay_actions = QComboBox()
        for label, value in OVERLAY_ACTIONS_OPTIONS:
            self.overlay_actions.addItem(label, value)
        for w in (self.capture_hotkey, self.overlay_hotkey, self.overlay_actions):
            w.setMaximumWidth(HOTKEY_INPUT_WIDTH)
        self.monitor_group = QButtonGroup(self)
        self.monitor_layout = self._build_monitor_selector()
        self.save_captures = QCheckBox(ui_lang.t("settings.save_captures"))
        self.open_captures_button = QPushButton(ui_lang.t("settings.open_folder"))
        self.open_captures_button.setObjectName("secondary")
        self.open_captures_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_captures_button.clicked.connect(self.on_open_captures_dir)  # type: ignore
        self.open_captures_row = QHBoxLayout()
        self.open_captures_row.addWidget(self.save_captures)
        self.open_captures_row.addWidget(self.open_captures_button)
        self.open_captures_row.addStretch()

        self.overlay_opacity = QSlider(Qt.Orientation.Horizontal)
        self.overlay_opacity.setRange(20, 100)  # нижче 20% оверлей майже не видно
        self.overlay_opacity.setMaximumWidth(HOTKEY_INPUT_WIDTH)
        self.overlay_opacity_value = QLabel()
        self.overlay_opacity.valueChanged.connect(
            lambda v: self.overlay_opacity_value.setText(f"{v}%"))
        self.overlay_opacity_row = QHBoxLayout()
        self.overlay_opacity_row.addWidget(self.overlay_opacity)
        self.overlay_opacity_row.addWidget(self.overlay_opacity_value)
        self.overlay_opacity_row.addStretch()

        self.capture_status = QLabel()

        self.save_button = QPushButton(ui_lang.t("settings.save"))
        self.save_button.clicked.connect(self.on_save)  # type: ignore
        self.reset_button = QPushButton(ui_lang.t("settings.reset"))
        self.reset_button.setObjectName("secondary")
        self.reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_button.clicked.connect(self.on_reset)  # type: ignore

        app_card, app_form = self._card(ui_lang.t("settings.section_app"))
        app_form.addRow(ui_lang.t("settings.app_language"), self.app_language_row)
        app_form.addRow(ui_lang.t("settings.game_language"), self.game_language)
        app_form.addRow(self.show_tray_icon)
        app_form.addRow(self.close_to_tray)
        app_form.addRow(self.start_minimized)

        capture_card, capture_form = self._card(ui_lang.t("settings.section_capture"))
        capture_form.addRow(ui_lang.t("settings.capture_hotkey"),
                            self._hotkey_row(self.capture_hotkey))
        capture_form.addRow(ui_lang.t("settings.capture_monitor"), self.monitor_layout)
        capture_form.addRow(self.open_captures_row)

        overlay_card, overlay_form = self._card(ui_lang.t("settings.section_overlay"))
        overlay_form.addRow(ui_lang.t("settings.overlay_hotkey"),
                            self._hotkey_row(self.overlay_hotkey))
        overlay_form.addRow(ui_lang.t("settings.overlay_actions"), self.overlay_actions)
        overlay_form.addRow(ui_lang.t("settings.overlay_opacity"), self.overlay_opacity_row)

        # статус ліворуч від кнопки, а не всередині форми — щоб лейаут не стрибав
        self.bottom_layout = QHBoxLayout()
        self.bottom_layout.addStretch()
        self.bottom_layout.addWidget(self.capture_status)
        self.bottom_layout.addWidget(self.reset_button)
        self.bottom_layout.addWidget(self.save_button)

        column = QVBoxLayout()
        # без цього лейаут column_widget додає власні дефолтні поля поверх
        # полів зовнішнього лейаута таба — контент відступає вдвічі більше,
        # ніж на інших табах
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(10)
        column.addWidget(app_card)
        column.addWidget(capture_card)
        column.addWidget(overlay_card)
        column.addLayout(self.bottom_layout)
        column.addStretch()
        column_widget = QWidget()
        column_widget.setMaximumWidth(CARDS_MAX_WIDTH)
        column_widget.setLayout(column)

        # обгортка з addStretch притискає колонку вліво, коли вікно ширше за неї
        row = QHBoxLayout()
        row.addWidget(column_widget)
        row.addStretch()
        layout = QVBoxLayout()
        layout.addLayout(row)
        self.setLayout(layout)
        self.refresh()
        self.on_tray_changed()

    @staticmethod
    def _hotkey_row(edit: HotkeyEdit) -> QHBoxLayout:
        """Інпут хоткея + лейбл помилки праворуч: текст помилки не вміщається
        в інпут шириною HOTKEY_INPUT_WIDTH, тому показуємо його зовні."""
        error_label = QLabel()
        error_label.setStyleSheet(f"color: {style.ERROR};")
        edit.error_changed.connect(error_label.setText)
        row = QHBoxLayout()
        row.addWidget(edit)
        row.addWidget(error_label)
        row.addStretch()
        return row

    @staticmethod
    def _card(title: str) -> tuple[QFrame, QFormLayout]:
        card = QFrame()
        card.setObjectName("settingsCard")
        header = QLabel(title)
        header.setObjectName("settingsCardTitle")
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(10)
        layout.addWidget(header)
        layout.addLayout(form)
        return card, form

    def _build_monitor_selector(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(0)
        monitors = list_monitors() or [(0, 0)]
        for index, (width, height) in enumerate(monitors):
            # parent keeps the button alive: QButtonGroup.addButton() doesn't take ownership
            button = QPushButton(
                ui_lang.t("settings.monitor_btn").format(
                    index=index + 1, width=width, height=height),
                self)
            button.setObjectName("segment")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setProperty("first", index == 0)
            button.setProperty("last", index == len(monitors) - 1)
            self.monitor_group.addButton(button, index + 1)  # id = монітор (1-based)
            layout.addWidget(button)
        layout.addStretch()
        return layout

    def refresh(self):
        settings = APP_CONTEXT.settings.get()
        self.show_tray_icon.setChecked(settings.show_tray_icon)
        self.close_to_tray.setChecked(settings.close_to_tray)
        self.start_minimized.setChecked(settings.start_minimized)
        app_lang_idx = self.app_language.findData(settings.app_language)
        self.app_language.setCurrentIndex(app_lang_idx if app_lang_idx >= 0 else 0)
        lang_idx = self.game_language.findData(settings.game_language)
        self.game_language.setCurrentIndex(lang_idx if lang_idx >= 0 else 0)
        self.capture_hotkey.set_value(settings.capture_hotkey)
        self.overlay_hotkey.set_value(settings.overlay_hotkey)
        actions_idx = self.overlay_actions.findData(settings.overlay_actions_hotkey)
        self.overlay_actions.setCurrentIndex(actions_idx if actions_idx >= 0 else 0)
        button = self.monitor_group.button(settings.capture_monitor) or self.monitor_group.button(1)
        if button is not None:
            button.setChecked(True)
        self.save_captures.setChecked(settings.save_captures)
        self.overlay_opacity.setValue(settings.overlay_opacity)
        self.overlay_opacity_value.setText(f"{settings.overlay_opacity}%")
        self.capture_status.setText("")

    def on_open_captures_dir(self):
        # тека створюється лише при першому збереженні скріна — гарантуємо її наявність,
        # щоб кнопка працювала навіть коли скрінів ще не було
        path = os.path.abspath(CAPTURES_DIR)
        os.makedirs(path, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def on_reset(self):
        # відкат незбережених змін до останніх збережених значень
        self.refresh()

    def on_tray_changed(self):
        self.close_to_tray.setEnabled(self.show_tray_icon.isChecked())
        self.start_minimized.setEnabled(self.show_tray_icon.isChecked() and self.close_to_tray.isChecked())

    def on_save(self):
        settings = APP_CONTEXT.settings.get()
        settings.show_tray_icon = self.show_tray_icon.isChecked()
        settings.close_to_tray = self.close_to_tray.isChecked()
        settings.start_minimized = self.start_minimized.isChecked()
        settings.app_language = self.app_language.currentData() or ui_lang.EN
        settings.game_language = self.game_language.currentData() or game_lang.EN
        settings.capture_hotkey = self.capture_hotkey.value().strip() or "f8"
        settings.overlay_hotkey = self.overlay_hotkey.value().strip() or "f9"
        settings.overlay_actions_hotkey = self.overlay_actions.currentData() or "ctrl+alt"
        settings.capture_monitor = self.monitor_group.checkedId() if self.monitor_group.checkedId() != -1 else 1
        settings.save_captures = self.save_captures.isChecked()
        settings.overlay_opacity = self.overlay_opacity.value()
        APP_CONTEXT.settings.save(settings)
        # застосовуємо мову гри одразу: інші вкладки оновляться при перемиканні
        game_lang.set_game_language(settings.game_language)
        self.refresh()
        self.refresh_tray_icon(settings.show_tray_icon)
        if self.apply_capture_settings():
            self.capture_status.setStyleSheet(f"color: {style.TEXT_MUTED};")
            self.capture_status.setText(ui_lang.t("settings.saved"))
        else:
            self.capture_status.setStyleSheet(f"color: {style.ERROR};")
            self.capture_status.setText(ui_lang.t("settings.hotkey_failed"))
