from PyQt6.QtWidgets import QTabWidget, QMainWindow

from alu_helper.views.cars_tab import CarsTab
from alu_helper.views.maps_tab import MapsTab
from alu_helper.views.races_tab import RacesTab
from alu_helper.views.tracks_tab import TracksTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ALU Helper")
        self.resize(500, 600)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.races_tab = RacesTab()
        self.tracks_tab = TracksTab()
        self.maps_tab = MapsTab()
        self.cars_tab = CarsTab()

        self.tabs.addTab(self.races_tab, "Races")
        self.tabs.addTab(self.tracks_tab, "Tracks")
        self.tabs.addTab(self.maps_tab, "Maps")
        self.tabs.addTab(self.cars_tab, "Cars")

        self.tabs.currentChanged.connect(self.tab_selected) # type: ignore

    def tab_selected(self, idx):
        tab = self.tabs.widget(idx)
        if tab.refresh:
            tab.refresh()