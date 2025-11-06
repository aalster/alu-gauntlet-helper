from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QCheckBox, QFormLayout

from alu_helper.app_context import APP_CONTEXT


class SettingsTab(QWidget):
    def __init__(self, refresh_tray_icon):
        super().__init__()
        self.refresh_tray_icon = refresh_tray_icon if refresh_tray_icon else lambda _: None

        self.show_tray_icon = QCheckBox()
        self.show_tray_icon.checkStateChanged.connect(self.refresh_close_to_tray) # type: ignore
        self.show_tray_icon.setText("Show tray icon")

        self.close_to_tray = QCheckBox()
        self.close_to_tray.setText("Close to tray")

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.on_save) # type: ignore

        self.form = QFormLayout()
        self.form.addWidget(self.show_tray_icon)
        self.form.addWidget(self.close_to_tray)

        self.bottom_layout = QHBoxLayout()
        self.bottom_layout.addStretch()
        self.bottom_layout.addWidget(self.save_button)

        layout = QVBoxLayout()
        layout.addLayout(self.form)
        layout.addLayout(self.bottom_layout)
        layout.addStretch()
        self.setLayout(layout)
        self.refresh()
        self.refresh_close_to_tray()

    def refresh(self):
        settings = APP_CONTEXT.settings.get()
        self.show_tray_icon.setChecked(settings.show_tray_icon)
        self.close_to_tray.setChecked(settings.close_to_tray)

    def refresh_close_to_tray(self):
        self.close_to_tray.setEnabled(self.show_tray_icon.isChecked())

    def on_save(self):
        settings = APP_CONTEXT.settings.get()
        settings.show_tray_icon = self.show_tray_icon.isChecked()
        settings.close_to_tray = self.close_to_tray.isEnabled() and self.close_to_tray.isChecked()
        APP_CONTEXT.settings.save(settings)
        self.refresh()
        self.refresh_tray_icon(settings.show_tray_icon)