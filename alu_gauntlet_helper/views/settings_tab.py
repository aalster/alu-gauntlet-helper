from PyQt6.QtWidgets import (QCheckBox, QFormLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget)

from alu_gauntlet_helper.app_context import APP_CONTEXT


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

        self.capture_hotkey = QLineEdit()
        self.overlay_hotkey = QLineEdit()
        self.capture_monitor = QSpinBox()
        self.capture_monitor.setRange(1, 4)
        self.save_captures = QCheckBox("Save capture screenshots (data/captures)")
        self.capture_status = QLabel()

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.on_save)  # type: ignore

        self.form = QFormLayout()
        self.form.addWidget(self.show_tray_icon)
        self.form.addWidget(self.close_to_tray)
        self.form.addWidget(self.start_minimized)
        self.form.addRow("Capture hotkey", self.capture_hotkey)
        self.form.addRow("Overlay hotkey", self.overlay_hotkey)
        self.form.addRow("Capture monitor", self.capture_monitor)
        self.form.addWidget(self.save_captures)
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

    def refresh(self):
        settings = APP_CONTEXT.settings.get()
        self.show_tray_icon.setChecked(settings.show_tray_icon)
        self.close_to_tray.setChecked(settings.close_to_tray)
        self.start_minimized.setChecked(settings.start_minimized)
        self.capture_hotkey.setText(settings.capture_hotkey)
        self.overlay_hotkey.setText(settings.overlay_hotkey)
        self.capture_monitor.setValue(settings.capture_monitor)
        self.save_captures.setChecked(settings.save_captures)
        self.capture_status.setText("")

    def on_tray_changed(self):
        self.close_to_tray.setEnabled(self.show_tray_icon.isChecked())
        self.start_minimized.setEnabled(self.show_tray_icon.isChecked() and self.close_to_tray.isChecked())

    def on_save(self):
        settings = APP_CONTEXT.settings.get()
        settings.show_tray_icon = self.show_tray_icon.isChecked()
        settings.close_to_tray = self.close_to_tray.isChecked()
        settings.start_minimized = self.start_minimized.isChecked()
        settings.capture_hotkey = self.capture_hotkey.text().strip() or "f8"
        settings.overlay_hotkey = self.overlay_hotkey.text().strip() or "f9"
        settings.capture_monitor = self.capture_monitor.value()
        settings.save_captures = self.save_captures.isChecked()
        APP_CONTEXT.settings.save(settings)
        self.refresh()
        self.refresh_tray_icon(settings.show_tray_icon)
        if self.apply_capture_settings():
            self.capture_status.setText("Saved.")
        else:
            self.capture_status.setText("Хоткей не зареєструвався — спробуй іншу клавішу")
