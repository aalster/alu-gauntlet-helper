import re
import tempfile
from html import escape
from pathlib import Path

from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QPushButton,
                             QStackedWidget, QVBoxLayout, QWidget)

from alu_gauntlet_helper import ui_lang
from alu_gauntlet_helper.services.assistant import BeatStats
from alu_gauntlet_helper.services.challenge_session import (RACE_COUNT, WIN_GOALS,
                                                            EffectiveRace)
from alu_gauntlet_helper.utils.utils import (format_signed_delta, format_time,
                                             get_resource_path)
from alu_gauntlet_helper.views.components.chip_tooltip import WIDEST_GOAL_LABEL
from alu_gauntlet_helper.views.components.common import res_to_pixmap
from alu_gauntlet_helper.views.components.goal_button import GoalButton
from alu_gauntlet_helper.views.style import (BORDER, CARD_SELECTED, CYAN,
                                             LOSS_BRIGHT, TEXT, TEXT_DARK,
                                             WIN_BRIGHT, YELLOW, YELLOW_HOVER,
                                             YELLOW_PRESSED)

MARGIN = 16
# Qt rich text підтримує vertical-align лише на <td> (не на <img>), тож центруємо
# по висоті рядка весь вміст комірок — інакше іконка 👎 «випливає» над текстом
_TD_MIDDLE = "vertical-align:middle"


def _cell(text: str, color: str | None = None) -> str:
    """Текст комірки, за потреби — у кольорі. Непевність (low-confidence) оверлей
    не показує: поріг матчера вже відсіяв сміття, а амбер лише відволікав."""
    safe = escape(text)
    if color:
        return f"<span style='color:{color}'>{safe}</span>"
    return safe


COMPLETE_COLOR = "#67d27a"  # колір номера гонки: всі поля заповнені


def _num_cell(n: int, complete: bool, lost: bool = False) -> str:
    """Номер гонки: червоний — програна гонка проти суперника, зелений — рядок
    повністю заповнений, білий — дані часткові."""
    color = LOSS_BRIGHT if lost else (COMPLETE_COLOR if complete else "white")
    return (f"<td style='padding-right:8px;{_TD_MIDDLE}'>"
            f"<span style='color:{color};font-weight:bold'>{n}</span></td>")


_ICON_CACHE_DIR: Path | None = None
_ICON_URIS: dict[tuple[str, int, float], str] = {}


def _screen_dpr() -> float:
    screen = QGuiApplication.primaryScreen() if QGuiApplication.instance() else None
    return screen.devicePixelRatio() if screen else 1.0


def _icon_uri(name: str, size: int, dpr: float | None = None,
              cache_dir: Path | None = None) -> str:
    """URI SVG-іконки для <img width=size> у rich-text QLabel.

    Qt растеризує SVG у його власному розмірі (12 px) і на HiDPI розтягує
    піксмап без згладжування — шеврон виходить розмитим/зубчастим. Для
    dpr > 1 Qt шукає поруч «name@2x.svg»; підкладаємо в temp-теку копію з
    intrinsic size = size·dpr (той самий viewBox), тож піксмап лягає в
    пристрій 1:1. При dpr = 1 — оригінал з resources."""
    global _ICON_CACHE_DIR
    dpr = _screen_dpr() if dpr is None else dpr
    key = (name, size, dpr)
    if key in _ICON_URIS:
        return _ICON_URIS[key]
    source = Path(get_resource_path(f"icons/{name}"))
    if dpr <= 1.0:
        uri = source.as_uri()
    else:
        if cache_dir is None:
            if _ICON_CACHE_DIR is None:
                _ICON_CACHE_DIR = Path(tempfile.mkdtemp(prefix="alu-overlay-icons-"))
            cache_dir = _ICON_CACHE_DIR
        svg = source.read_text(encoding="utf-8")
        px = round(size * dpr)
        hidpi = re.sub(r'width="\d+" height="\d+"', f'width="{px}" height="{px}"', svg, count=1)
        stem, ext = name.rsplit(".", 1)
        (cache_dir / name).write_text(svg, encoding="utf-8")
        (cache_dir / f"{stem}@2x.{ext}").write_text(hidpi, encoding="utf-8")
        uri = (cache_dir / name).as_uri()
    _ICON_URIS[key] = uri
    return uri


def _dislike_cell(n: int, active: bool) -> str:
    """Комірка-перемикач «некоректний час» (👎). Клік ловиться через
    linkActivated — спрацьовує лише в режимі керування, коли вікно не click-through."""
    icon = "thumbs-down.svg" if active else "thumbs-down-dim.svg"
    src = _icon_uri(icon, 14)
    return (f"<td style='padding-left:12px;{_TD_MIDDLE}'><a href='dislike:{n}'>"
            f"<img src='{src}' width='14' height='14'></a></td>")


_GRADE_ICONS = {2: "grade-up2.svg", 1: "grade-up.svg", 0: "grade-eq.svg",
                -1: "grade-down.svg", -2: "grade-down2.svg"}


def _grade_icon(grade: int) -> str:
    """Шеврон «як проїхав» після мого часу: угору зелений (швидше за середнє),
    униз червоний, «≈» блакитний; подвійний — сильно краще/гірше."""
    src = _icon_uri(_GRADE_ICONS[grade], 12)
    return f" <img src='{src}' width='12' height='12'>"


def header_text(races: dict[int, EffectiveRace]) -> str:
    """Заголовок оверлея — статичний бренд; шанси перемог показують кнопки
    режимів поруч (OverlayWindow.set_goals)."""
    return ui_lang.t("window.title")


def _track_cell(e: EffectiveRace, track_names: dict[int, str],
                track_maps: dict[int, str], map_names: dict[int, str]) -> str:
    """Комірка треку: «Карта - Трек» для треку зі скану/драфта; трек, вибраний
    чипом чи виведений звуженням (track_fixed), — cyan поруч із білими
    «Карта - »; гонка лише з картою — назва карти замість «?»."""
    if e.track_id:
        track = track_names.get(e.track_id, "?")
        if e.track_fixed:
            map_name = map_names.get(e.map_id, "") or track_maps.get(e.track_id, "")
            prefix = f"{escape(map_name)} - " if map_name else ""
            return f"{prefix}<span style='color:{CYAN}'>{escape(track)}</span>"
        map_name = track_maps.get(e.track_id, "")
        label = f"{map_name} - {track}" if map_name else track
        return _cell(label)
    if e.map_id and e.map_id in map_names:
        return _cell(map_names[e.map_id])
    return _cell("?")


def build_races_table(races: dict[int, EffectiveRace],
                      track_names: dict[int, str],
                      car_names: dict[int, str],
                      beat_stats: dict[int, BeatStats] | None = None,
                      track_maps: dict[int, str] | None = None,
                      map_names: dict[int, str] | None = None,
                      run_grades: dict[int, int] | None = None) -> str:
    """Будує rich-text (HTML) таблицю 5 гонок.

    beat_stats {race_number: BeatStats} — Δ і «побито з n» показаного авто проти
    часу суперника для незіграних гонок: Δ у колонці часу праворуч, «7/10» —
    окремою колонкою на місці 👎.
    run_grades {race_number: −2…+2} — оцінка зіграного заїзду проти власного
    середнього (assistant.grade_run): шеврон після часу.
    track_names — назви треків (БЕЗ карти), track_maps {track_id: назва карти},
    map_names {map_id: назва карти} — для map-only гонок і cyan-треків з фікса.
    Лише таблиця залишена в HTML: колонки треку/авто/часу так вирівнюються
    попри пропорційний шрифт; заголовок і footer — окремі віджети.
    """
    beat_stats = beat_stats or {}
    run_grades = run_grades or {}
    track_maps = track_maps or {}
    map_names = map_names or {}
    rows = []
    for n in range(1, RACE_COUNT + 1):
        e = races.get(n)
        if e is None:
            rows.append(
                f"<tr><td style='padding-right:8px'>{n}</td>"
                f"<td colspan='4' style='color:#9aa0c0'>{ui_lang.t('overlay.no_data')}</td></tr>"
            )
            continue
        # без фактичного авто показуємо рекомендоване (shown_car_id) — воно і є
        # підказкою «чим їхати», заради якої оверлей висить поверх гри;
        # рекомендація фарбується блакитним, як бейдж на картці гонки
        suggested = e.car_id <= 0 and e.suggested_car_id > 0
        car = (car_names.get(e.shown_car_id, "?") if e.shown_car_id
               else (e.car_name or "?"))
        track_cell = _track_cell(e, track_names, track_maps, map_names)
        car_cell = _cell(car, CYAN if suggested else None)
        # як на картці гонки: зіграна — мій час (+👎), незіграна з авто — Δ
        # «мій мінус суперника» (−1.300 = я швидший, зелена) і «7/10» без
        # перемикача 👎 (без часу він безглуздий); нічия = програш, як в оцінці шансів
        played = e.time > 0
        beat = beat_stats.get(n) if not played else None
        with_car = e.shown_car_id > 0 or bool(e.car_name)
        if beat:
            # Δ і «7/10» — окремі колонки: Δ притиснута праворуч (знаки й
            # десяткові в стовпчик), лічильник займає колонку 👎, яка для
            # незіграної гонки однаково порожня
            color = WIN_BRIGHT if beat.delta > 0 else LOSS_BRIGHT
            time_td = (f"<td align='right' style='{_TD_MIDDLE}'>"
                       f"<span style='color:{color};font-weight:bold'>"
                       f"{format_signed_delta(-beat.delta)}</span></td>")
            last_td = (f"<td style='padding-left:8px;{_TD_MIDDLE}'>"
                       f"{beat.wins}/{beat.n}</td>")
        else:
            time_cell = escape(format_time(e.time) if e.time else "?")
            if played and (grade := run_grades.get(n)) is not None:
                time_cell += _grade_icon(grade)
            time_td = f"<td style='{_TD_MIDDLE}'>{time_cell}</td>"
            last_td = ("<td></td>" if not played and with_car
                       else _dislike_cell(n, e.bad_timing))
        # програш проти суперника (лише коли його час відомий): нічия = програш,
        # як в оцінці шансів
        lost = played and e.opponent_time > 0 and e.time >= e.opponent_time
        rows.append(
            f"<tr>"
            f"{_num_cell(n, e.is_complete, lost)}"
            f"<td style='padding-right:12px;{_TD_MIDDLE}'>{track_cell}</td>"
            f"<td style='padding-right:12px;{_TD_MIDDLE}'>{car_cell}</td>"
            f"{time_td}"
            f"{last_td}"
            f"</tr>"
        )
    return "<table cellspacing='0' cellpadding='0'>" + "".join(rows) + "</table>"


TRAINING_OVERLAY_LIMIT = 10  # скільки останніх заїздів тренування видно на оверлеї


def build_training_table(runs: dict[int, EffectiveRace],
                         track_names: dict[int, str],
                         car_names: dict[int, str],
                         track_maps: dict[int, str] | None = None,
                         map_names: dict[int, str] | None = None,
                         run_grades: dict[int, int] | None = None) -> str:
    """HTML-таблиця тренувальної сесії: останні TRAINING_OVERLAY_LIMIT заїздів
    із наскрізними номерами (проїхав 15 — перший видимий рядок «6»).

    Рядок — як у таблиці челенджа: № · трек · авто · час (+ шеврон «як проїхав»
    з run_grades) · 👎; заїзди завжди зіграні (час є), тож колонки шансу немає.
    Порожня сесія — «no data»."""
    track_maps = track_maps or {}
    map_names = map_names or {}
    run_grades = run_grades or {}
    numbers = sorted(runs)[-TRAINING_OVERLAY_LIMIT:]
    if not numbers:
        return ("<table cellspacing='0' cellpadding='0'><tr>"
                f"<td style='color:#9aa0c0'>{ui_lang.t('overlay.no_data')}</td>"
                "</tr></table>")
    rows = []
    for n in numbers:
        e = runs[n]
        car = car_names.get(e.car_id, "?") if e.car_id else (e.car_name or "?")
        time_cell = escape(format_time(e.time) if e.time else "?")
        if e.time and (grade := run_grades.get(n)) is not None:
            time_cell += _grade_icon(grade)
        rows.append(
            f"<tr>"
            f"{_num_cell(n, e.is_complete)}"
            f"<td style='padding-right:12px;{_TD_MIDDLE}'>"
            f"{_track_cell(e, track_names, track_maps, map_names)}</td>"
            f"<td style='padding-right:12px;{_TD_MIDDLE}'>{_cell(car)}</td>"
            f"<td style='{_TD_MIDDLE}'>{time_cell}</td>"
            f"{_dislike_cell(n, e.bad_timing)}"
            f"</tr>"
        )
    return "<table cellspacing='0' cellpadding='0'>" + "".join(rows) + "</table>"


# фон-картка оверлея. Рамка завжди присутня (2px), але прозора — щоб розмір
# не змінювався при вмиканні режиму переміщення, інакше прив'язаний край «стрибав» би
_CARD_RGB = "8, 10, 40"
_CARD_ACTIVE_BORDER = "#67d27a"  # колір рамки, коли керування активне


def _card_style(opacity_percent: int, active: bool) -> str:
    """Стиль картки: альфа фону — з відсотка непрозорості; коли керування
    активне (Ctrl+Alt) — зелена рамка, інакше прозора (щоб розмір не стрибав)."""
    alpha = round(max(0, min(100, opacity_percent)) / 100 * 255)
    border = _CARD_ACTIVE_BORDER if active else "transparent"
    return (
        "#overlayCard {"
        f"  background-color: rgba({_CARD_RGB}, {alpha});"
        "  border-radius: 8px;"
        f"  border: 2px solid {border};"
        "}"
    )

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
# режими підбору 3/5 · 4/5 · 5/5 у заголовку: неактивні — просто текст,
# активний — темний фон без рамки; ховер (лише в Ctrl+Alt, інакше вікно
# click-through) — той самий фон
_GOAL_STYLE = (
    f"QLabel {{ background-color: transparent; color: #9aa0c0;"
    f" border: none; border-radius: 4px; padding: 2px 6px;"
    f" font-size: 13px; font-weight: bold; }}"
    f"QLabel:hover {{ background-color: {_SECONDARY_BG}; }}"
    f"QLabel[active=\"true\"] {{ background-color: {_SECONDARY_BG}; color: {TEXT}; }}"
)


class _DragHandle(QLabel):
    """Кнопка справа вгорі: лише за неї можна перетягувати оверлей."""

    def __init__(self, overlay: "OverlayWindow"):
        super().__init__(overlay)
        self._overlay = overlay
        self.setPixmap(res_to_pixmap("icons/move.svg", 16))  # lucide move
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(_HANDLE_STYLE)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setToolTip(ui_lang.t("overlay.drag_tooltip"))

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
    керування (set_actions_mode) ловить мишу — можна перетягувати й тиснути кнопки."""

    save_requested = pyqtSignal()     # клік Save на оверлеї
    capture_requested = pyqtSignal()  # клік Capture на оверлеї
    close_requested = pyqtSignal()    # клік ✕ на оверлеї
    dislike_toggled = pyqtSignal(int)  # клік 👎 у рядку гонки (номер гонки)
    goal_selected = pyqtSignal(int)    # клік по режиму 3/5 · 4/5 · 5/5 (k)
    visibility_changed = pyqtSignal(bool)  # show/hide вікна — стан тогл-кнопки «Оверлей»

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
        self._actions_mode = False
        self._drag_offset: QPoint | None = None
        self._opacity_percent = 80  # % непрозорості картки; перекривається налаштуваннями

        # картка-контейнер тримає фон/рамку; вміст — звичайні віджети в layout
        self.card = QWidget(self)
        self.card.setObjectName("overlayCard")
        # без WA_StyledBackground звичайний QWidget не малює фон зі стилю
        self.card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.card.setStyleSheet(_card_style(self._opacity_percent, False))

        # верхній рядок: заголовок ліворуч, панель керування (ручка · ✕) праворуч
        self.header_label = QLabel()
        self.header_label.setStyleSheet(_HEADER_STYLE)

        self.drag_handle = _DragHandle(self)  # _overlay = вікно; layout нижче перепарентить у toolbar
        self.close_button = QPushButton("✕")
        self.close_button.setStyleSheet(_CLOSE_STYLE)
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.setToolTip(ui_lang.t("overlay.hide_tooltip"))
        self.close_button.clicked.connect(lambda: self.close_requested.emit())

        self.toolbar = QWidget()
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(TOOLBAR_SPACING)
        toolbar_layout.addWidget(self.drag_handle)
        toolbar_layout.addWidget(self.close_button)
        # кнопки видимі лише в режимі керування; коли сховані, панель має ~нульову
        # ширину й нічого не резервує. Зміну ширини оверлея від появи кнопок
        # компенсує set_actions_mode, тримаючи прив'язаний край — без фіксації ширини.
        self.drag_handle.setVisible(False)
        self.close_button.setVisible(False)  # кнопки видимі лише в режимі переміщення

        # режими підбору поруч із заголовком; сховані для тренування
        self.goals_widget = QWidget()
        goals_row = QHBoxLayout(self.goals_widget)
        goals_row.setContentsMargins(0, 0, 0, 0)
        goals_row.setSpacing(2)
        self.goal_buttons: dict[int, GoalButton] = {}
        for goal in WIN_GOALS:
            button = GoalButton()
            button.setStyleSheet(_GOAL_STYLE)
            button.reserve_width(WIDEST_GOAL_LABEL)
            button.setText(f"{goal}/{RACE_COUNT}")
            button.clicked.connect(lambda g=goal: self.goal_selected.emit(g))
            self.goal_buttons[goal] = button
            goals_row.addWidget(button)
        self.goals_widget.setVisible(False)

        self.top_widget = QWidget()
        top_row = QHBoxLayout(self.top_widget)
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.addWidget(self.header_label)
        top_row.addWidget(self.goals_widget)
        top_row.addStretch()
        top_row.addWidget(self.toolbar)

        # таблиця гонок — єдине, що лишилось у HTML
        self.table_label = QLabel()
        self.table_label.setTextFormat(Qt.TextFormat.RichText)
        self.table_label.setStyleSheet(_TEXT_STYLE)
        # лінки-перемикачі 👎 у таблиці; поза режимом керування вікно click-through,
        # тож кліки до них просто не долітають
        self.table_label.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.table_label.linkActivated.connect(self._on_table_link)

        # нижній рядок: статус ліворуч; праворуч — підказка з хоткеями АБО
        # кнопка Save (видно лише одне, перемикається в set_actions_mode)
        self.spinner = Spinner()  # обертова іконка замість слова "Recognizing"
        self.status_label = QLabel()
        self.status_label.setStyleSheet(_TEXT_STYLE)

        # праворуч унизу — або підказка з хоткеями, або кнопки Capture+Save.
        # Тримаємо їх у QStackedWidget: його ширина природно дорівнює ширшій зі
        # сторінок, тож нижній рядок не стрибає при перемиканні Ctrl+Alt.
        self.hint_label = QLabel()
        self.hint_label.setStyleSheet(_HINT_STYLE)
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.capture_button = QPushButton(ui_lang.t("overlay.capture"))
        self.capture_button.setStyleSheet(_SAVE_STYLE)
        self.capture_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.capture_button.setToolTip(ui_lang.t("overlay.capture_tooltip"))
        self.capture_button.clicked.connect(lambda: self.capture_requested.emit())
        self.save_button = QPushButton(ui_lang.t("overlay.save"))
        self.save_button.setStyleSheet(_SAVE_STYLE)
        self.save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_button.setToolTip(ui_lang.t("overlay.save_tooltip"))
        self.save_button.clicked.connect(lambda: self.save_requested.emit())

        buttons_page = QWidget()
        buttons_row = QHBoxLayout(buttons_page)
        buttons_row.setContentsMargins(0, 0, 0, 0)
        buttons_row.setSpacing(TOOLBAR_SPACING)
        buttons_row.addStretch()  # притискає кнопки до правого краю
        buttons_row.addWidget(self.capture_button)
        buttons_row.addWidget(self.save_button)

        self.bottom_right = QStackedWidget()
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

    def _on_table_link(self, href: str):
        kind, _, arg = href.partition(":")
        if kind == "dislike" and arg.isdigit():
            self.dislike_toggled.emit(int(arg))

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
        self.card.updateGeometry()
        self.layout().activate()
        self.adjustSize()
        self._apply_position()

    def set_screen_index(self, index: int):
        """mss-індекс монітора (1-based); оверлей стає у кут цього екрана."""
        self._screen_index = index
        self._apply_position()

    def set_opacity(self, percent: int):
        """Непрозорість картки (%). У режимі керування картка завжди 100%, тож
        тут лише запам'ятовуємо й застосовуємо, коли керування неактивне."""
        self._opacity_percent = percent
        if not self._actions_mode:
            self.card.setStyleSheet(_card_style(percent, False))

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

    def set_goals(self, labels: dict[int, str] | None, active: int = 0):
        """Кнопки режимів підбору: {k: «5/5 72%»} і активний k; None — сховати
        (тренування). Викликати перед update_content — той переобчислює розмір."""
        self.goals_widget.setVisible(labels is not None)
        for goal, button in self.goal_buttons.items():
            if labels is not None:
                button.setText(labels[goal])
            button.set_active(goal == active)

    def set_save_enabled(self, enabled: bool):
        """Віддзеркалює стан кнопки Save застосунку (нема що зберігати → сіра)."""
        self.save_button.setEnabled(enabled)

    def showEvent(self, event):
        super().showEvent(event)
        self.visibility_changed.emit(True)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.visibility_changed.emit(False)

    def resizeEvent(self, e):
        # будь-яка зміна розміру (контент, поява кнопок у Ctrl+Alt) не повинна
        # зрушувати прив'язаний край — тримаємо його на місці, нарощуючи в інший бік.
        # Саме це дозволяє внутрішнім елементам мати природну ширину: на місці
        # лишається край вікна, а не заморожена ширина віджетів усередині.
        super().resizeEvent(e)
        if self._drag_offset is not None or not e.oldSize().isValid():
            return  # під час перетягування позицією керує користувач
        dw = e.size().width() - e.oldSize().width()
        dh = e.size().height() - e.oldSize().height()
        if not (dw or dh):
            return
        # у режимі керування орієнтуємось на поточне положення (користувач міг
        # перетягнути); у звичайному — на збережену прив'язку
        if self._actions_mode or self._anchor is None:
            anchor_right, anchor_bottom = self._current_side()
        else:
            anchor_right, anchor_bottom = self._anchor[2], self._anchor[3]
        x = self.x() - dw if anchor_right else self.x()
        y = self.y() - dh if anchor_bottom else self.y()
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)

    def _apply_position(self):
        # під час перетягування не сіпаємо вікно — позицією керує користувач
        if self._actions_mode:
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

    # --- режим керування (Ctrl+Alt) -------------------------------------

    def is_actions_mode(self) -> bool:
        return self._actions_mode

    def set_actions_mode(self, on: bool):
        """Вмикає/вимикає режим керування: перемикає click-through і підсвітку."""
        if on == self._actions_mode:
            return
        self._actions_mode = on
        visible = self.isVisible()
        # край, до якого притиснутий оверлей, і геометрія ДО перемикання:
        # setWindowFlag ховає вікно, а сховане отримує resize-подію без старого
        # розміру — resizeEvent не компенсує зміну ширини від появи/зникнення
        # кнопок керування, тож прив'язаний край тримаємо тут явно
        anchor_right, anchor_bottom = self._current_side()
        old_x, old_y, old_w, old_h = self.x(), self.y(), self.width(), self.height()
        # WindowTransparentForInput на Windows застосовується лише після re-show
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, not on)
        # у режимі керування картка завжди 100% непрозора; поза ним — за налаштуванням
        self.card.setStyleSheet(_card_style(100 if on else self._opacity_percent, on))
        # контроли активні лише коли оверлей ловить мишу (Ctrl+Alt);
        # праворуч унизу Save заступає підказку з хоткеями
        self.drag_handle.setVisible(on)
        self.close_button.setVisible(on)
        # ширина стека однакова в обох режимах; ширину може змінити лише
        # рядок заголовка (режими підбору + ручка/✕), коли він ширший за таблицю
        self.bottom_right.setCurrentIndex(1 if on else 0)
        self.adjustSize()
        self.move(old_x + old_w - self.width() if anchor_right else old_x,
                  old_y + old_h - self.height() if anchor_bottom else old_y)
        if visible:
            self.show()  # WA_ShowWithoutActivating — без крадіжки фокуса в гри
