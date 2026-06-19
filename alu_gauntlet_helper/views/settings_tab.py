import os

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFormLayout,
                             QHBoxLayout, QLabel, QPushButton, QSlider,
                             QVBoxLayout, QWidget)

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.capture.screen_grab import CAPTURES_DIR, list_monitors
from alu_gauntlet_helper.views.components.hotkey_edit import HotkeyEdit

# (підпис, значення для keyboard) — модифікатор активації керування оверлеєм
OVERLAY_ACTIONS_OPTIONS = [
    ("Ctrl + Alt", "ctrl+alt"),
    ("Ctrl + Shift", "ctrl+shift"),
]

HOTKEY_INPUT_WIDTH = 200  # хоткеї/комбо не розтягуємо на всю ширину форми


class SettingsTab(QWidget):
    def __init__(self, refresh_tray_icon, apply_capture_settings=None):
        super().__init__()
        self.refresh_tray_icon = refresh_tray_icon if refresh_tray_icon else lambda _: None
        self.apply_capture_settings = apply_capture_settings or (lambda: True)

        self.show_tray_icon = QCheckBox("Show tray icon")
        self.show_tray_icon.checkStateChanged.connect(self.on_tray_changed)  # type: ignore

        self.close_to_tray = QCheckBox("Close to tray")
        self.close_to_tray.checkStateChanged.connect(self.on_tray_changed)  # type: ignore

        self.start_minimized = QCheckBox("Start minimized")

        self.capture_hotkey = HotkeyEdit()
        self.overlay_hotkey = HotkeyEdit()
        self.overlay_actions = QComboBox()
        for label, value in OVERLAY_ACTIONS_OPTIONS:
            self.overlay_actions.addItem(label, value)
        for w in (self.capture_hotkey, self.overlay_hotkey, self.overlay_actions):
            w.setMaximumWidth(HOTKEY_INPUT_WIDTH)
        self.monitor_group = QButtonGroup(self)
        self.monitor_layout = self._build_monitor_selector()
        self.save_captures = QCheckBox("Save screenshots of unrecognized / low-confidence captures (data/captures)")
        self.open_captures_button = QPushButton("Open folder")
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

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.on_save)  # type: ignore

        self.form = QFormLayout()
        self.form.addWidget(self.show_tray_icon)
        self.form.addWidget(self.close_to_tray)
        self.form.addWidget(self.start_minimized)
        self.form.addRow("Capture hotkey", self.capture_hotkey)
        self.form.addRow("Overlay hotkey", self.overlay_hotkey)
        self.form.addRow("Overlay actions", self.overlay_actions)
        self.form.addRow("Overlay opacity", self.overlay_opacity_row)
        self.form.addRow("Capture monitor", self.monitor_layout)
        # порожній caption — щоб чекбокс став у колонку полів, врівень з іншими інпутами
        self.form.addRow("", self.open_captures_row)
        self.form.addWidget(self.capture_status)

        self.bottom_layout = QHBoxLayout()
        self.bottom_layout.addStretch()
        self.bottom_layout.addWidget(self.save_button)

        layout = QVBoxLayout()
        layout.addLayout(self.form)
        layout.addLayout(self.bottom_layout)
        layout.addStretch()
        self.setLayout(layout)
        self.refresh()
        self.on_tray_changed()

    def _build_monitor_selector(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(0)
        monitors = list_monitors() or [(0, 0)]
        for index, (width, height) in enumerate(monitors):
            # parent keeps the button alive: QButtonGroup.addButton() doesn't take ownership
            button = QPushButton(f"Monitor {index + 1}\n{width}×{height}", self)
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

    def on_tray_changed(self):
        self.close_to_tray.setEnabled(self.show_tray_icon.isChecked())
        self.start_minimized.setEnabled(self.show_tray_icon.isChecked() and self.close_to_tray.isChecked())

    def on_save(self):
        settings = APP_CONTEXT.settings.get()
        settings.show_tray_icon = self.show_tray_icon.isChecked()
        settings.close_to_tray = self.close_to_tray.isChecked()
        settings.start_minimized = self.start_minimized.isChecked()
        settings.capture_hotkey = self.capture_hotkey.value().strip() or "f8"
        settings.overlay_hotkey = self.overlay_hotkey.value().strip() or "f9"
        settings.overlay_actions_hotkey = self.overlay_actions.currentData() or "ctrl+alt"
        settings.capture_monitor = self.monitor_group.checkedId() if self.monitor_group.checkedId() != -1 else 1
        settings.save_captures = self.save_captures.isChecked()
        settings.overlay_opacity = self.overlay_opacity.value()
        APP_CONTEXT.settings.save(settings)
        self.refresh()
        self.refresh_tray_icon(settings.show_tray_icon)
        if self.apply_capture_settings():
            self.capture_status.setText("Saved.")
        else:
            self.capture_status.setText("Хоткей не зареєструвався — спробуй іншу клавішу")
