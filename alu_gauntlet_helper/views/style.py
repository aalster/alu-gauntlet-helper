"""Asphalt Legends Unite inspired theme: deep blue gradients, navy cards,
yellow CTAs and times, cyan accents, bold italic uppercase headings."""
from PyQt6.QtGui import QFont, QPalette, QColor
from PyQt6.QtWidgets import QApplication

BG_TOP = "#1554C0"
BG_BOTTOM = "#082058"
CARD = "#161C5E"
CARD_HOVER = "#1E2674"
CARD_SELECTED = "#273090"
PANEL = "#0B1545"
INPUT_BG = "#0E1B4E"
BORDER = "#33418F"
CYAN = "#2BD2FF"
YELLOW = "#FFD60A"
YELLOW_HOVER = "#FFE552"
YELLOW_PRESSED = "#E8C200"
TIME_YELLOW = "#FFDD00"
TEXT = "#FFFFFF"
TEXT_MUTED = "#9DB2E6"
TEXT_FAINT = "#6F7FB5"
TEXT_DARK = "#10173F"
ERROR = "#FF6B6B"
FAVORITE = "#FF3B6B"

APP_STYLE = f"""
QMainWindow {{
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 {BG_TOP}, stop: 0.55 #0D3490, stop: 1 {BG_BOTTOM});
}}

QDialog, QMessageBox {{
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #123C97, stop: 1 {BG_BOTTOM});
}}

QLabel {{
    color: {TEXT};
    background: transparent;
}}

QTabWidget::pane {{
    border: none;
}}

QTabBar::tab {{
    background: transparent;
    color: {TEXT_MUTED};
    font-weight: bold;
    font-style: italic;
    padding: 9px 16px;
    margin-right: 4px;
    border-bottom: 3px solid transparent;
}}

QTabBar::tab:hover {{
    color: {TEXT};
}}

QTabBar::tab:selected {{
    color: {TEXT};
    border-bottom: 3px solid {YELLOW};
}}

QListWidget {{
    background-color: rgba(5, 12, 40, 110);
    border: none;
    border-radius: 8px;
    padding: 4px;
    outline: none;
}}

QListWidget::item {{
    background-color: {CARD};
    border: 1px solid transparent;
    border-radius: 6px;
    margin: 2px 4px;
}}

QListWidget::item:hover {{
    background-color: {CARD_HOVER};
}}

QListWidget::item:selected {{
    background-color: {CARD_SELECTED};
    border: 1px solid {CYAN};
}}

QListView {{
    background-color: {INPUT_BG};
    border: 1px solid {CYAN};
    border-radius: 4px;
    color: {TEXT};
    outline: none;
}}

QListView::item {{
    padding: 5px 8px;
    border-radius: 3px;
}}

QListView::item:selected, QListView::item:hover {{
    background-color: {CARD_SELECTED};
    color: {TEXT};
}}

QLineEdit, QTextEdit {{
    background-color: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 8px;
    color: {TEXT};
    selection-background-color: {CYAN};
    selection-color: {TEXT_DARK};
}}

QLineEdit:focus, QTextEdit:focus {{
    border: 1px solid {CYAN};
}}

QLineEdit:read-only {{
    color: {TEXT_MUTED};
}}

QPushButton {{
    background-color: {YELLOW};
    color: {TEXT_DARK};
    font-weight: bold;
    border: none;
    border-radius: 4px;
    padding: 7px 18px;
}}

QPushButton:hover {{
    background-color: {YELLOW_HOVER};
}}

QPushButton:pressed {{
    background-color: {YELLOW_PRESSED};
}}

QPushButton:disabled {{
    background-color: #3A4C86;
    color: #7C8BB8;
}}

QPushButton#secondary {{
    background-color: #1C2C74;
    color: {TEXT};
    border: 1px solid {BORDER};
}}

QPushButton#secondary:hover {{
    background-color: {CARD_SELECTED};
    border: 1px solid {CYAN};
}}

QCheckBox {{
    color: {TEXT};
    spacing: 8px;
}}

QCheckBox:disabled {{
    color: {TEXT_FAINT};
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER};
    border-radius: 3px;
    background-color: {INPUT_BG};
}}

QCheckBox::indicator:hover {{
    border: 1px solid {CYAN};
}}

QCheckBox::indicator:checked {{
    background-color: {CYAN};
    border: 1px solid {CYAN};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: #4A5CC0;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 5px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background: #4A5CC0;
}}

QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0;
    height: 0;
}}

QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}

QScrollArea {{
    background: transparent;
    border: none;
}}

QScrollArea > QWidget > QWidget {{
    background: transparent;
}}

QToolTip {{
    background-color: {INPUT_BG};
    color: {TEXT};
    border: 1px solid {CYAN};
    padding: 4px 8px;
}}

QMenu {{
    background-color: {INPUT_BG};
    color: {TEXT};
    border: 1px solid {BORDER};
}}

QMenu::item {{
    padding: 6px 24px;
}}

QMenu::item:selected {{
    background-color: {CARD_SELECTED};
}}
"""


def apply_style(app: QApplication):
    font = QFont()
    font.setFamilies(["Bahnschrift", "Segoe UI"])
    font.setPointSize(11)
    app.setFont(font)

    palette = app.palette()
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(TEXT_FAINT))
    app.setPalette(palette)

    app.setStyleSheet(APP_STYLE)
