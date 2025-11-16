import cv2
import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QCheckBox, QFormLayout, QLabel, QFileDialog

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.utils.utils import pixmap_to_bytes
from alu_gauntlet_helper.screen_recognition.recognition import find_rectangles, find_race_boxes


class RecognizeRacesTab(QWidget):
    def __init__(self):
        super().__init__()

        self.preview_label = QLabel("Preview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.preview_label.setStyleSheet("""
            border: 1px solid #ccc;
            background: #f8f8f8;
        """)

        self.load_button = QPushButton("Выбрать картинку")
        self.load_button.clicked.connect(self.load_image)

        layout = QVBoxLayout()
        layout.addWidget(self.preview_label)
        layout.addWidget(self.load_button)
        self.setLayout(layout)

    def load_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose screenshot",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )

        if not file_path:
            return

        with open(file_path, "rb") as f:
            image_bytes = f.read()

        pixmap = QPixmap()
        pixmap.loadFromData(image_bytes)

        thumbnail = pixmap.scaled(
            1024,
            1024,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.preview_label.setPixmap(thumbnail)
        print(find_race_boxes(pixmap_to_bytes(thumbnail)))
