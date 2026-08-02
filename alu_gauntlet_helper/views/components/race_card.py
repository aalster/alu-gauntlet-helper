from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel, QSizePolicy,
                             QVBoxLayout, QWidget)

from alu_gauntlet_helper import ui_lang
from alu_gauntlet_helper.services.assistant import laplace
from alu_gauntlet_helper.utils.utils import format_time, load_pixmap_cover
from alu_gauntlet_helper.views import style
from alu_gauntlet_helper.views.components.common import (INFO_PADDING, WARN_ICON,
                                                         CarInfoWidget, RankClassBadge,
                                                         TrackInfoWidget, edit_icon_button,
                                                         res_to_pixmap, set_lazy_image_tooltip)

# у style.py немає окремої константи ACCENT — беремо жовтий, як WARN_ICON
CARD_BORDER_SELECTED = style.ACCENT if hasattr(style, "ACCENT") else "#FFC107"


class _CoverIcon(QLabel):
    """Іконка авто на всю доступну ширину: докадровує зображення (cover) під
    фактичний розмір лейбла і перекадровує при resize картки."""

    def __init__(self, height: int, parent=None):
        super().__init__(parent)
        self.setObjectName("carIconLabel")
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._path = ""

    def set_icon(self, path: str):
        self._path = path or ""
        self._reload()

    def _reload(self):
        pixmap = (load_pixmap_cover(self._path, w=self.width(), h=self.height())
                  if self._path and self.width() > 0 else None)
        if pixmap:
            self.setPixmap(pixmap)
        else:
            self.clear()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reload()


class RaceCard(QFrame):
    """Клікабельна картка гонки в ряду з 5: чекбокс збереження, трек (як у списку
    заїздів), час суперника, авто на плашці як у CarInfoWidget (закріплене — до
    заїзду, фактичне — після) з «7/10», мій час з іконками і редагуванням."""

    clicked = pyqtSignal(int)

    def __init__(self, race_number: int, on_toggle, on_edit, parent=None):
        super().__init__(parent)
        self.race_number = race_number
        self.setObjectName("raceCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(150)

        # чекбокс вирішує, чи піде заїзд у базу при Save (як у списку раніше);
        # clicked — тільки від кліку юзера, програмний setChecked його не емітить
        self.checkbox = QCheckBox()
        self.checkbox.clicked.connect(lambda c: on_toggle(race_number, c))

        self.title_label = QLabel(ui_lang.t("assistant.race_n").format(n=race_number))
        title_font = QFont()
        title_font.setBold(True)
        self.title_label.setFont(title_font)

        # трек як у списку заїздів: іконка карти зліва, правіше карта і трек
        # окремими рядками (+ ховер-превʼю маршруту); віджет замінюється при update
        self.track_row = QHBoxLayout()
        self.track_row.setContentsMargins(0, 0, 0, 0)
        self.track_info: TrackInfoWidget = TrackInfoWidget("", "", "", "")
        self.track_row.addWidget(self.track_info)

        # час суперника: крупно жирним білим + дрібний підпис праворуч
        opponent_font = QFont()
        opponent_font.setBold(True)
        opponent_font.setPointSize(self.font().pointSize() + 2)
        self.opponent_time_label = QLabel("")
        self.opponent_time_label.setFont(opponent_font)
        self.opponent_caption = QLabel(ui_lang.t("assistant.opponent_time_caption"))
        self.opponent_caption.setStyleSheet(f"color: {style.TEXT_MUTED}; font-size: 11px;")
        # контейнер, щоб без часу суперника рядок не займав висоту
        self.opponent_widget = QWidget()
        opponent_row = QHBoxLayout(self.opponent_widget)
        opponent_row.setContentsMargins(INFO_PADDING, 0, INFO_PADDING, 0)
        opponent_row.setSpacing(6)
        opponent_row.addWidget(self.opponent_time_label)
        opponent_row.addWidget(self.opponent_caption)
        opponent_row.addStretch()

        # --- авто: вертикальна версія CarInfoWidget — та сама плашка/стилі/тултип,
        # іконка на всю ширину, під нею МАРКА (капс) + ранг навпроти, нижче модель
        self.car_plate = QWidget()
        self.car_plate.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.car_plate.setObjectName("carInfoPlate")

        self.car_icon = _CoverIcon(64)

        self.brand_label = QLabel("")
        self.brand_label.setObjectName("carBrandLabel")

        self.rank_badge: QLabel | RankClassBadge = QLabel("")
        self.brand_row = QHBoxLayout()
        self.brand_row.setContentsMargins(0, 0, 0, 0)
        self.brand_row.setSpacing(6)
        self.brand_row.addWidget(self.brand_label)
        self.brand_row.addStretch()
        self.brand_row.addWidget(self.rank_badge)

        self.model_label = QLabel("")
        self.model_label.setObjectName("carModelLabel")
        self.model_label.setWordWrap(True)

        plate_layout = QVBoxLayout(self.car_plate)
        plate_layout.setContentsMargins(INFO_PADDING, INFO_PADDING, INFO_PADDING, INFO_PADDING)
        plate_layout.setSpacing(3)
        plate_layout.addWidget(self.car_icon)
        plate_layout.addLayout(self.brand_row)
        plate_layout.addWidget(self.model_label)


        # шанс побити суперника показаним авто: крупний кольоровий відсоток
        # (та сама лапласова оцінка, що й у автопідборі) + "7/10 побито" поруч
        prob_font = QFont()
        prob_font.setBold(True)
        prob_font.setPointSize(self.font().pointSize() + 4)
        self.prob_label = QLabel("")
        self.prob_label.setFont(prob_font)
        self.beat_label = QLabel("")  # "7/10 побито" — по показаному авто
        self.beat_label.setStyleSheet("font-size: 11px;")
        # контейнер, щоб рядок зовсім не займав висоту, коли схований
        self.beat_widget = QWidget()
        beat_row = QHBoxLayout(self.beat_widget)
        beat_row.setContentsMargins(INFO_PADDING, 0, INFO_PADDING, 0)
        beat_row.setSpacing(6)
        beat_row.addWidget(self.prob_label)
        beat_row.addWidget(self.beat_label)
        beat_row.addStretch()

        # --- мій час + іконки 👎/нотатки ---
        # розмір шрифту як у відсотка ймовірності — обидва головні акценти картки
        time_font = QFont()
        time_font.setBold(True)
        time_font.setPointSize(self.font().pointSize() + 4)
        self.time_label = QLabel("")
        self.time_label.setFont(time_font)

        self.bad_timing_label = QLabel()
        self.note_label = QLabel()
        self.edit_button = edit_icon_button(lambda: on_edit(race_number))

        self.time_widget = QWidget()
        time_row = QHBoxLayout(self.time_widget)
        time_row.setContentsMargins(INFO_PADDING, 0, INFO_PADDING, 0)
        time_row.setSpacing(4)
        time_row.addWidget(self.time_label)
        time_row.addStretch()
        time_row.addWidget(self.bad_timing_label)
        time_row.addWidget(self.note_label)

        header = QHBoxLayout()
        header.setContentsMargins(INFO_PADDING, 0, INFO_PADDING, 0)
        header.addWidget(self.checkbox)
        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(self.edit_button)

        layout = QVBoxLayout(self)
        # бокові маржини зменшені на внутрішній відступ плашок (трек/авто), а
        # «плоскі» рядки додають його собі самі: контент скрізь на одній
        # вертикалі з іконками всередині плашок, фони плашок ширші на відступ
        layout.setContentsMargins(10 - INFO_PADDING, 8, 10 - INFO_PADDING, 8)
        layout.setSpacing(2)
        layout.addLayout(header)
        layout.addLayout(self.track_row)
        layout.addWidget(self.opponent_widget)
        layout.addWidget(self.car_plate)
        layout.addWidget(self.beat_widget)
        layout.addStretch()
        layout.addWidget(self.time_widget)

    def mousePressEvent(self, event):
        # чекбокс/кнопка редагування поглинають свої кліки самі — сюди доходять
        # лише кліки по «тілу» картки, вони перемикають вибрану гонку
        self.clicked.emit(self.race_number)
        super().mousePressEvent(event)

    def _set_track_info(self, widget: TrackInfoWidget):
        self.track_row.replaceWidget(self.track_info, widget)
        self.track_info.deleteLater()
        self.track_info = widget

    def _set_rank_badge(self, widget):
        self.brand_row.replaceWidget(self.rank_badge, widget)
        self.rank_badge.deleteLater()
        self.rank_badge = widget

    def update_card(self, e, track, car, beat, checked: bool, selected: bool):
        """e: EffectiveRace | None; track: TrackView | None; car: Car показаного
        авто (фактичне з заїзду або закріплене) | None; beat: (wins, n) | None;
        checked — стан чекбокса збереження; selected — чи це відкрита панель."""
        self.checkbox.setEnabled(e is not None)
        self.checkbox.setChecked(checked)

        if track is not None:
            warn = WARN_ICON if e is not None and e.track_uncertain else ""
            self._set_track_info(TrackInfoWidget(
                track.map_icon or "", track.icon or "",
                track.display_map_name, warn + track.display_name))
        else:
            # трек невідомий — компонент не показуємо зовсім (порожнє місце)
            self._set_track_info(TrackInfoWidget("", "", "", ""))
        self.track_info.setVisible(track is not None)

        opp = e.opponent_time if e else 0
        self.opponent_time_label.setText(format_time(opp) if opp else "")
        self.opponent_widget.setVisible(bool(opp))

        self._update_car(e, car)

        # низ картки взаємовиключний: зіграна гонка показує мій час (з іконками),
        # незіграна — лише статистику шансів (👎/нотатка без часу не показуються);
        # порожні рядки сховані повністю й висоти не займають
        played = e is not None and e.time > 0
        if beat:
            p = laplace(*beat)
            color = style.WIN_BRIGHT if p >= 0.5 else style.LOSS_BRIGHT
            self.prob_label.setText(f"{round(p * 100)}%")
            self.prob_label.setStyleSheet(f"color: {color};")
            self.beat_label.setText(ui_lang.t("assistant.beaten").format(wins=beat[0], n=beat[1]))
        else:
            self.prob_label.setText("")
            self.beat_label.setText("")
        self.beat_widget.setVisible(bool(beat) and not played)

        self._update_time_row(e)
        self.time_widget.setVisible(played)

        # мій час уже є — гонка зіграна, підсвічуємо заголовок зеленим (як оверлей).
        # У style.py немає константи «успішно/виграно», тож лишаємо літерал, але
        # значення узгоджене з overlay.COMPLETE_COLOR ("#67d27a" — теж літерал там,
        # колір номера гонки з усіма заповненими полями).
        self.title_label.setStyleSheet("color: #67d27a;" if played else "")

        # невибрані картки теж мають обводку (штатний колір рамок) — інакше
        # зливаються з фоном; золота лишається маркером активної
        border = CARD_BORDER_SELECTED if selected else style.BORDER
        self.setStyleSheet(f"QFrame#raceCard {{ border: 1px solid {border}; border-radius: 6px; }}")

    def _update_car(self, e, car):
        """Плашка авто; car=None з e.car_name — кастомне авто з драфта (без
        іконки й рангу), зовсім без авто — плашка схована, місце порожнє."""
        custom_name = e.car_name if e is not None and not (e.car_id or 0) else ""
        if car is not None:
            self.car_icon.set_icon(car.icon)
            self.car_icon.show()
            # той самий лінивий тултип-превʼю, що й у CarInfoWidget; при зміні авто
            # властивість перезаписується, порожній шлях чистимо вручну
            if car.icon:
                set_lazy_image_tooltip(self.car_icon, car.icon, CarInfoWidget.PREVIEW_WIDTH)
            else:
                self.car_icon.setProperty("_lazy_tooltip_icon", "")
            self.brand_label.setText((car.brand or "").upper())
            warn = WARN_ICON if e is not None and e.car_uncertain and e.car_id else ""
            self.model_label.setText(warn + (car.model or car.name))
            rank = (e.rank if e is not None and e.rank else 0) or car.rank
            # спрощений бейдж: без максимального рангу і іконки overclock —
            # на вузькій картці лише ранг і клас (max_rank=0 вимикає обидва)
            self._set_rank_badge(RankClassBadge(rank, 0, car.car_class))
            self.car_plate.show()
        elif custom_name:
            self.car_icon.set_icon("")
            self.car_icon.setProperty("_lazy_tooltip_icon", "")
            self.car_icon.hide()
            self.brand_label.setText("")
            self.model_label.setText(custom_name)
            self._set_rank_badge(QLabel(""))
            self.car_plate.show()
        else:
            self.car_plate.hide()

    def _update_time_row(self, e):
        if e is not None and e.time > 0:
            self.time_label.setText(format_time(e.time))
            # той самий яскравий зелений, що в часу у списку заїздів (rowTimeLabel);
            # яскравим червоним — лише програш часу суперника
            if e.opponent_time and e.time >= e.opponent_time:
                self.time_label.setStyleSheet(f"color: {style.LOSS_BRIGHT};")
            else:
                self.time_label.setStyleSheet(f"color: {style.WIN_BRIGHT};")
        else:
            self.time_label.setText("")
            self.time_label.setStyleSheet("")

        if e is not None and e.bad_timing:
            self.bad_timing_label.setPixmap(res_to_pixmap("icons/thumbs-down.svg", 18))
        else:
            self.bad_timing_label.clear()

        if e is not None and e.note:
            self.note_label.setPixmap(res_to_pixmap("icons/notepad-text.svg", 18))
            self.note_label.setToolTip(e.note)
        else:
            self.note_label.clear()
            self.note_label.setToolTip("")
