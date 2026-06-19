from html import escape

from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QSizePolicy,
                             QStackedWidget, QVBoxLayout, QWidget)

from alu_gauntlet_helper.services.challenge_session import RACE_COUNT, EffectiveRace
from alu_gauntlet_helper.utils.utils import format_time
from alu_gauntlet_helper.views.style import (BORDER, CARD_SELECTED, CYAN, TEXT,
                                             TEXT_DARK, YELLOW, YELLOW_HOVER,
                                             YELLOW_PRESSED)

MARGIN = 16
UNCERTAIN_COLOR = "#FFC107"  # ненадійні (low-confidence) поля підсвічуються амбер


def _cell(text: str, uncertain: bool) -> str:
    """Текст комірки; ненадійне значення підсвічується амбер."""
    safe = escape(text)
    if uncertain:
        return f"<span style='color:{UNCERTAIN_COLOR}'>{safe}</span>"
    return safe


def header_text(races: dict[int, EffectiveRace]) -> str:
    """Текст заголовка оверлея (звичайний QLabel, не HTML)."""
    complete = sum(1 for e in races.values() if e.is_complete)
    return f"Gauntlet capture {complete}/{RACE_COUNT}"


def build_races_table(races: dict[int, EffectiveRace],
                      track_names: dict[int, str],
                      car_names: dict[int, str]) -> str:
    """Будує rich-text (HTML) таблицю 5 гонок.

    Лише таблиця залишена в HTML: колонки треку/авто/часу так вирівнюються
    попри пропорційний шрифт; заголовок і footer — окремі віджети.
    """
    rows = []
    for n in range(1, RACE_COUNT + 1):
        e = races.get(n)
        if e is None:
            rows.append(
                f"<tr><td style='padding-right:8px'>{n}</td>"
                f"<td colspan='3' style='color:#9aa0c0'>no data</td></tr>"
            )
            continue
        track = track_names.get(e.track_id, "?") if e.track_id else "?"
        car = car_names.get(e.car_id, "?") if e.car_id else (e.car_name or "?")
        time_str = format_time(e.time) if e.time else "?"
        if e.is_complete:
            mark, mark_color = "✓", "#67d27a"
        else:
            mark, mark_color = "⚠", "#e6c34a"
        track_cell = _cell(track, e.track_uncertain)
        car_cell = _cell(car, e.car_uncertain)
        rows.append(
            f"<tr>"
            f"<td style='padding-right:8px'>{n}&nbsp;<span style='color:{mark_color}'>{mark}</span></td>"
            f"<td style='padding-right:12px'>{track_cell}</td>"
            f"<td style='padding-right:12px'>{car_cell}</td>"
            f"<td>{escape(time_str)}</td>"
            f"</tr>"
        )
    return "<table cellspacing='0' cellpadding='0'>" + "".join(rows) + "</table>"


# фон-картка оверлея. Рамка завжди присутня (2px), але прозора — щоб розмір
# не змінювався при вмиканні режиму переміщення, інакше прив'язаний край «стрибав» би
_CARD_STYLE = (
    "#overlayCard {"
    "  background-color: rgba(8, 10, 40, 215);"
    "  border-radius: 8px;"
    "  border: 2px solid transparent;"
    "}"
)
_CARD_MOVE_BORDER = "#overlayCard { border-color: #67d27a; }"  # у режимі переміщення фарбуємо рамку

_TEXT_STYLE = "color: white; font-size: 13px; background: transparent;"
_HEADER_STYLE = _TEXT_STYLE + " font-weight: bold;"
_HINT_STYLE = "color: #9aa0c0; font-size: 13px; background: transparent;"

# контроли оверлея (Save · ручка · ✕). Кольори — з теми застосунку (style.py):
# Save = primary (жовта), решта = secondary.
TOOLBAR_SPACING = 4
_SECONDARY_BG = "#1C2C74"  # фон secondary-кнопок застосунку
# Save — як primary-кнопка застосунку ("Save selected" у табі), disabled — приглушена
_SAVE_STYLE = (
    f"QPushButton {{ background-color: {YELLOW}; color: {TEXT_DARK};"
    f" font-weight: bold; border: 1px solid transparent; border-radius: 4px; padding: 4px 14px; }}"
    f"QPushButton:hover {{ background-color: {YELLOW_HOVER}; }}"
    f"QPushButton:pressed {{ background-color: {YELLOW_PRESSED}; }}"
    f"QPushButton:disabled {{ background-color: #3A4C86; color: #7C8BB8; }}"
)
# Close — як secondary-кнопка застосунку (темно-синя, рамка, cyan при наведенні)
_CLOSE_STYLE = (
    f"QPushButton {{ background-color: {_SECONDARY_BG}; color: {TEXT};"
    f" border: 1px solid {BORDER}; border-radius: 4px; padding: 4px 9px;"
    f" font-weight: bold; }}"
    f"QPushButton:hover {{ background-color: {CARD_SELECTED}; border: 1px solid {CYAN}; }}"
)
# ручка переміщення — той самий secondary-вигляд (QLabel, тож стилі inline)
_HANDLE_STYLE = (
    f"background-color: {_SECONDARY_BG}; color: {TEXT};"
    f" border: 1px solid {BORDER}; border-radius: 4px;"
    f" padding: 4px 7px; font-weight: bold;"
)
_HANDLE_HOVER_STYLE = _HANDLE_STYLE + f" border: 1px solid {CYAN};"


class _DragHandle(QLabel):
    """Кнопка справа вгорі: лише за неї можна перетягувати оверлей."""

    def __init__(self, overlay: "OverlayWindow"):
        super().__init__("✥", overlay)
        self._overlay = overlay
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(_HANDLE_STYLE)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setToolTip("Перетягніть, щоб перемістити оверлей")

    def enterEvent(self, e):
        self.setStyleSheet(_HANDLE_HOVER_STYLE)

    def leaveEvent(self, e):
        self.setStyleSheet(_HANDLE_STYLE)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._overlay._drag_offset = (
                e.globalPosition().toPoint() - self._overlay.frameGeometry().topLeft()
            )
            e.accept()

    def mouseMoveEvent(self, e):
        if self._overlay._drag_offset is not None:
            self._overlay.move(e.globalPosition().toPoint() - self._overlay._drag_offset)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._overlay._drag_offset = None
        e.accept()


class Spinner(QWidget):
    """Обертова дуга — індикатор розпізнавання. Таймер крутиться лише поки
    активний (start/stop), тож у спокої навантаження немає."""

    def __init__(self, size: int = 14, color: str = CYAN, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._angle = 0
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.setInterval(40)  # ~25 к/с — плавно й дешево
        self._timer.timeout.connect(self._advance)
        self.setVisible(False)

    def start(self):
        if not self._timer.isActive():
            self._timer.start()
        self.setVisible(True)

    def stop(self):
        self._timer.stop()
        self.setVisible(False)

    def _advance(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self._color, 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        rect = self.rect().adjusted(2, 2, -2, -2)
        # дуга 270°, що обертається (16-ті частки градуса)
        p.drawArc(rect, -self._angle * 16, 270 * 16)


class OverlayWindow(QWidget):
    """Панель статусу поверх гри. За замовчуванням click-through; у режимі
    переміщення (set_draggable) ловить мишу й її можна перетягнути."""

    save_requested = pyqtSignal()     # клік Save на оверлеї
    capture_requested = pyqtSignal()  # клік Capture на оверлеї
    close_requested = pyqtSignal()    # клік ✕ на оверлеї

    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, True)
        self.setMinimumWidth(300)
        self._screen_index = 1
        # прив'язка (ax, ay, anchor_right, anchor_bottom) або None → снап у кут
        self._anchor: tuple[int, int, bool, bool] | None = None
        self._draggable = False
        self._drag_offset: QPoint | None = None

        # картка-контейнер тримає фон/рамку; вміст — звичайні віджети в layout
        self.card = QWidget(self)
        self.card.setObjectName("overlayCard")
        # без WA_StyledBackground звичайний QWidget не малює фон зі стилю
        self.card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.card.setStyleSheet(_CARD_STYLE)

        # верхній рядок: заголовок ліворуч, панель керування (ручка · ✕) праворуч
        self.header_label = QLabel()
        self.header_label.setStyleSheet(_HEADER_STYLE)

        self.drag_handle = _DragHandle(self)  # _overlay = вікно; layout нижче перепарентить у toolbar
        self.close_button = QPushButton("✕")
        self.close_button.setStyleSheet(_CLOSE_STYLE)
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.setToolTip("Сховати оверлей")
        self.close_button.clicked.connect(lambda: self.close_requested.emit())

        self.toolbar = QWidget()
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(TOOLBAR_SPACING)
        toolbar_layout.addWidget(self.drag_handle)
        toolbar_layout.addWidget(self.close_button)
        # резервуємо ширину панелі назавжди (кнопки лише ховаємо), щоб поява панелі
        # в режимі переміщення не міняла ширину оверлея
        self.toolbar.setFixedWidth(self.toolbar.sizeHint().width())
        self.drag_handle.setVisible(False)
        self.close_button.setVisible(False)  # кнопки видимі лише в режимі переміщення

        self.top_widget = QWidget()
        top_row = QHBoxLayout(self.top_widget)
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.addWidget(self.header_label)
        top_row.addStretch()
        top_row.addWidget(self.toolbar)

        # таблиця гонок — єдине, що лишилось у HTML
        self.table_label = QLabel()
        self.table_label.setTextFormat(Qt.TextFormat.RichText)
        self.table_label.setStyleSheet(_TEXT_STYLE)

        # нижній рядок: статус ліворуч; праворуч — підказка з хоткеями АБО
        # кнопка Save (видно лише одне, перемикається в set_draggable)
        self.spinner = Spinner()  # обертова іконка замість слова "Recognizing"
        self.status_label = QLabel()
        self.status_label.setStyleSheet(_TEXT_STYLE)

        # праворуч унизу — або підказка з хоткеями, або кнопки Capture+Save.
        # Тримаємо їх у QStackedWidget: його ширина = ширша зі сторінок, тож
        # перемикання Ctrl+Alt не міняє ширину оверлея (правий край не «втікає»)
        self.hint_label = QLabel()
        self.hint_label.setStyleSheet(_HINT_STYLE)
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.capture_button = QPushButton("Capture")
        self.capture_button.setStyleSheet(_SAVE_STYLE)
        self.capture_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.capture_button.setToolTip("Зробити захоплення екрана")
        self.capture_button.clicked.connect(lambda: self.capture_requested.emit())
        self.save_button = QPushButton("Save")
        self.save_button.setStyleSheet(_SAVE_STYLE)
        self.save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_button.setToolTip("Зберегти відмічені гонки")
        self.save_button.clicked.connect(lambda: self.save_requested.emit())

        buttons_page = QWidget()
        buttons_row = QHBoxLayout(buttons_page)
        buttons_row.setContentsMargins(0, 0, 0, 0)
        buttons_row.setSpacing(TOOLBAR_SPACING)
        buttons_row.addStretch()  # притискає кнопки до правого краю
        buttons_row.addWidget(self.capture_button)
        buttons_row.addWidget(self.save_button)

        self.bottom_right = QStackedWidget()
        self.bottom_right.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self.bottom_right.addWidget(self.hint_label)  # індекс 0 — звичайний режим
        self.bottom_right.addWidget(buttons_page)     # індекс 1 — режим переміщення

        self.bottom_widget = QWidget()
        bottom_row = QHBoxLayout(self.bottom_widget)
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(TOOLBAR_SPACING)
        bottom_row.addWidget(self.spinner)
        bottom_row.addWidget(self.status_label)
        bottom_row.addStretch()
        bottom_row.addWidget(self.bottom_right)

        # фіксуємо висоту рядків під кнопки, щоб поява/зникнення кнопок та панелі
        # не розтягувала їх і оверлей не «стрибав» при вмиканні режиму переміщення
        row_h = max(self.save_button.sizeHint().height(),
                    self.capture_button.sizeHint().height(),
                    self.close_button.sizeHint().height(),
                    self.drag_handle.sizeHint().height())
        self.top_widget.setFixedHeight(row_h)
        self.bottom_widget.setFixedHeight(row_h)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(8)
        card_layout.addWidget(self.top_widget)
        card_layout.addWidget(self.table_label)
        card_layout.addWidget(self.bottom_widget)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.card)

    def update_content(self, header: str, table_html: str, status: str, hint: str,
                       in_flight: int = 0):
        """Оновлює всі частини оверлея й переобчислює розмір/позицію.

        in_flight > 0 — триває розпізнавання: показуємо обертовий спінер замість
        тексту "Recognizing" (і лічильник (N), коли кадрів кілька)."""
        self.header_label.setText(header)
        self.table_label.setText(table_html)
        if in_flight > 0:
            self.spinner.start()
            self.status_label.setText(str(in_flight) if in_flight > 1 else "")
        else:
            self.spinner.stop()
            self.status_label.setText(status)
        self.status_label.setVisible(bool(self.status_label.text()))
        self.hint_label.setText(hint)
        self.adjustSize()
        self._apply_position()

    def set_screen_index(self, index: int):
        """mss-індекс монітора (1-based); оверлей стає у кут цього екрана."""
        self._screen_index = index
        self._apply_position()

    # --- позиція ---------------------------------------------------------

    def set_anchor(self, ax: int, ay: int, anchor_right: bool, anchor_bottom: bool):
        """Прив'язує оверлей до краю екрана (вимикає снап у кут).

        ax/ay — абсолютні координати прив'язаного краю: правого або лівого по X,
        нижнього або верхнього по Y. При зміні розміру фіксований край лишається.
        """
        self._anchor = (ax, ay, anchor_right, anchor_bottom)
        self._apply_position()

    def clear_position(self):
        """Повертає поведінку за замовчуванням — снап у правий верхній кут."""
        self._anchor = None
        self._apply_position()

    def _current_side(self) -> tuple[bool, bool]:
        """До якого краю екрана ближчий центр оверлея: (right, bottom)."""
        center = self.frameGeometry().center()
        screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
        sc = screen.geometry().center()
        return center.x() > sc.x(), center.y() > sc.y()

    def compute_anchor(self) -> tuple[int, int, bool, bool]:
        """За поточним положенням визначає прив'язку: до якого краю екрана
        ближчий центр оверлея, той край і фіксуємо."""
        anchor_right, anchor_bottom = self._current_side()
        geo = self.frameGeometry()
        ax = geo.left() + self.width() if anchor_right else geo.left()
        ay = geo.top() + self.height() if anchor_bottom else geo.top()
        return ax, ay, anchor_right, anchor_bottom

    def set_save_enabled(self, enabled: bool):
        """Віддзеркалює стан кнопки Save застосунку (нема що зберігати → сіра)."""
        self.save_button.setEnabled(enabled)

    def resizeEvent(self, e):
        # у режимі переміщення (коли користувач саме не тягне) контент може
        # змінити розмір — тримаємо прив'язаний край на місці, щоб не «втікав» за екран
        super().resizeEvent(e)
        if self._draggable and self._drag_offset is None and e.oldSize().isValid():
            dw = e.size().width() - e.oldSize().width()
            dh = e.size().height() - e.oldSize().height()
            if dw or dh:
                anchor_right, anchor_bottom = self._current_side()
                x = self.x() - dw if anchor_right else self.x()
                y = self.y() - dh if anchor_bottom else self.y()
                if (x, y) != (self.x(), self.y()):
                    self.move(x, y)

    def _apply_position(self):
        # під час перетягування не сіпаємо вікно — позицією керує користувач
        if self._draggable:
            return
        if self._anchor is not None:
            ax, ay, anchor_right, anchor_bottom = self._anchor
            x = ax - self.width() if anchor_right else ax
            y = ay - self.height() if anchor_bottom else ay
            center = QPoint(x + self.width() // 2, y + self.height() // 2)
            if self._point_on_some_screen(center):
                self.move(x, y)
                return
        self._move_to_corner()

    @staticmethod
    def _point_on_some_screen(p: QPoint) -> bool:
        return any(s.geometry().contains(p) for s in QGuiApplication.screens())

    def _move_to_corner(self):
        screens = QGuiApplication.screens()
        screen = screens[self._screen_index - 1] if 0 < self._screen_index <= len(screens) else QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        self.move(geo.right() - self.width() - MARGIN, geo.top() + MARGIN)

    # --- режим переміщення ----------------------------------------------

    def is_draggable(self) -> bool:
        return self._draggable

    def set_draggable(self, on: bool):
        """Вмикає/вимикає режим переміщення: перемикає click-through і підсвітку."""
        if on == self._draggable:
            return
        self._draggable = on
        visible = self.isVisible()
        # WindowTransparentForInput на Windows застосовується лише після re-show
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, not on)
        self.card.setStyleSheet(_CARD_STYLE + (_CARD_MOVE_BORDER if on else ""))
        # контроли активні лише коли оверлей ловить мишу (Ctrl+Alt);
        # праворуч унизу Save заступає підказку з хоткеями
        self.drag_handle.setVisible(on)
        self.close_button.setVisible(on)
        # ширина стека однакова в обох режимах, тож оверлей не міняє розмір
        self.bottom_right.setCurrentIndex(1 if on else 0)
        self.adjustSize()
        if visible:
            self.show()  # WA_ShowWithoutActivating — без крадіжки фокуса в гри
