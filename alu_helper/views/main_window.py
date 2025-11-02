from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLineEdit, QListWidget, QTabWidget, QMainWindow

from alu_helper.views.maps_tab import MapsTab
from alu_helper.views.test_window import TestView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ALU Helper")
        self.resize(500, 600)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.test_view = TestView()
        self.maps_tab = MapsTab()

        self.tabs.addTab(self.test_view, "Test")
        self.tabs.addTab(self.maps_tab, "Maps")
