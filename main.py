import sys

from PyQt6.QtWidgets import QApplication

from alu_helper.views.main_window import MainWindow
from alu_helper.database import init_db
init_db()

app = QApplication(sys.argv)
app.setStyle("Fusion")
font = app.font()
font.setPointSize(10)
app.setFont(font)

window = MainWindow()
window.show()
sys.exit(app.exec())
