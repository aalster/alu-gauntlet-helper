# gui/maps_tab.py
from PyQt6.QtCore import Qt, QSize, QObject, QEvent
from PyQt6.QtGui import QIntValidator, QFont, QFontMetrics, QIcon
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QListWidget, QLineEdit, QListWidgetItem, QHBoxLayout, \
    QLabel, QTextEdit, QFormLayout, QComboBox, QToolTip

from alu_gauntlet_helper import game_lang, ui_lang
from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.races import RaceView, RaceAggregate
from alu_gauntlet_helper.views import style
from alu_gauntlet_helper.services.tracks import TrackView
from alu_gauntlet_helper.utils.utils import format_time, format_signed_delta, time_format_regex, parse_time, \
    format_relative_time, get_resource_path
from alu_gauntlet_helper.views.components.common import InputDebounce, CLEAR_ON_ESC_FILTER, res_to_pixmap, hbox, \
    vbox, ListItemWidget, enable_clear_button, enable_search_icon, RankClassBadge, CarInfoWidget, TrackInfoWidget, \
    preserved_scroll, edit_icon_button, as_column, INFO_PADDING
from alu_gauntlet_helper.views.components.edit_dialog import EditDialog
from alu_gauntlet_helper.views.components.validated_line_edit import ValidatedLineEdit
from alu_gauntlet_helper.views.components.item_completer import ItemCompleter


class RaceDialog(EditDialog):
    def __init__(self, item: RaceView, action, parent=None, relaxed=False, title=""):
        self.item = item
        self.relaxed = relaxed  # порожні трек/авто/час дозволені (capture-драфти)

        self.track_edit = ValidatedLineEdit(
            f"{item.display_map_name} - {item.display_track_name}" if item.track_name else "")
        self.car_edit = ValidatedLineEdit(item.car_name)
        self.rank_edit = ValidatedLineEdit(str(item.rank) if item.rank else "")
        self.rank_edit.get_input().setValidator(QIntValidator(0, 10000))
        self.time_edit = ValidatedLineEdit(format_time(item.time), placeholder="mm:ss.xxx", regex=time_format_regex)
        self.bad_timing_button = QPushButton()
        self.bad_timing_button.setObjectName("iconToggle")
        self.bad_timing_button.setIcon(QIcon(get_resource_path("icons/thumbs-down.svg")))
        self.bad_timing_button.setIconSize(QSize(18, 18))
        self.bad_timing_button.setCheckable(True)
        self.bad_timing_button.setChecked(item.bad_timing)
        self.bad_timing_button.setToolTip(ui_lang.t("races.bad_timing"))
        self.bad_timing_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bad_timing_button.setFixedSize(30, 30)
        self.note_edit = QTextEdit(item.note)

        self.tracks_completer = ItemCompleter(
            self.track_edit.get_input(),
            autocomplete=APP_CONTEXT.tracks_service.autocomplete,
            presentation=lambda i: f"{i.display_map_name} - {i.display_name}",
            allow_custom_text=False
        )
        self.tracks_completer.set_selected_item(TrackView(
            id=item.track_id, name=item.track_name, name_ru=item.track_name_ru,
            map_name=item.map_name, map_name_ru=item.map_name_ru))

        self.cars_completer = ItemCompleter(
            self.car_edit.get_input(),
            autocomplete=APP_CONTEXT.cars_service.autocomplete,
            presentation=lambda i: i.name,
            selected_listener=self.on_car_selected
        )

        # видаляти можна лише вже збережений заїзд (не драфти/нові)
        delete_action = (lambda: APP_CONTEXT.races_service.delete(self.item)) if item.id else None
        super().__init__(action, parent, delete_action=delete_action,
                         delete_confirm=ui_lang.t("dialog.delete_race_confirm"))
        self.setWindowTitle(title or (ui_lang.t("dialog.edit_race") if item.id else ui_lang.t("dialog.add_race")))

    def prepare_layout(self):
        form_layout = QFormLayout()
        form_layout.addRow(ui_lang.t("field.track"), self.track_edit)
        form_layout.addRow(ui_lang.t("field.car"), self.car_edit)
        form_layout.addRow(ui_lang.t("field.rank"), self.rank_edit)
        form_layout.addRow(ui_lang.t("field.time"), hbox([self.time_edit, self.bad_timing_button], spacing=6))
        form_layout.addRow(ui_lang.t("field.note"), self.note_edit)

        return form_layout

    def on_car_selected(self, car):
        # ранг не підставляємо: порожнє поле означає "взяти поточний ранг авто" при збереженні;
        # очищаємо, щоб ранг попереднього авто не записався новому
        self.rank_edit.set_text("")

    def prepare_item(self):
        track_id = self.tracks_completer.get_selected_item().id if self.tracks_completer.get_selected_item() else 0
        car_id = self.cars_completer.get_selected_item().id if self.cars_completer.get_selected_item() else 0
        car_name = self.car_edit.text()
        rank = int(self.rank_edit.text()) if self.rank_edit.text() else 0
        time = parse_time(self.time_edit.text())
        bad_timing = self.bad_timing_button.isChecked()
        note = self.note_edit.toPlainText()

        error = False
        if track_id <= 0 and not self.relaxed:
            self.track_edit.set_error()
            error = True

        if not car_name and not self.relaxed:
            self.car_edit.set_error()
            error = True

        if not time and not self.relaxed:
            self.time_edit.set_error()
            error = True

        if error:
            return None
        return RaceView(id=self.item.id, track_id=track_id, car_id=car_id, car_name=car_name, rank=rank,
                        time=time, bad_timing=bad_timing, note=note)


class RaceListWidget(ListItemWidget):
    def __init__(self, race: RaceView, on_edit=None, parent=None):
        super().__init__(race, parent)
        self.track_info = TrackInfoWidget(race.map_icon, race.track_icon,
                                          race.display_map_name, race.display_track_name)

        rank_color = ""
        if race.rank and race.car_rank:
            if race.car_rank > race.rank:
                rank_color = style.RANK_UP
            elif race.car_rank < race.rank:
                rank_color = style.RANK_DOWN
        self.rank_badge = RankClassBadge(race.rank, race.car_max_rank if race.rank else 0, race.car_class,
                                         rank_color=rank_color)
        self.car_info = CarInfoWidget(race.car_icon, race.car_brand, race.car_model, self.rank_badge)

        time_font = QFont()
        time_font.setBold(True)
        time_font.setPointSize(self.font().pointSize() + 4)

        self.time_label = QLabel(format_time(race.time) or "—")
        self.time_label.setObjectName("rowTimeLabel")
        self.time_label.setFont(time_font)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # колонка шириною по вмісту — повітря зліва (від плашки авто) і справа
        # (до іконок) треба задати явно
        self.time_label.setContentsMargins(12, 0, 12, 0)
        self.created_at_label = QLabel(format_relative_time(race.created_at))
        self.created_at_label.setObjectName("rowCreatedLabel")
        self.created_at_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.created_at_label.setToolTip(race.created_at.strftime("%d.%m.%Y %H:%M:%S"))

        # слот 18×18 резервується завжди, навіть без іконки: блок іконок має
        # однакову ширину в усіх рядках і не зсуває межі сусідніх колонок
        self.bad_timing_label = QLabel()
        self.bad_timing_label.setFixedSize(18, 18)
        if race.bad_timing:
            self.bad_timing_label.setPixmap(res_to_pixmap("icons/thumbs-down.svg", 18))

        self.info_label = QLabel()
        self.info_label.setFixedSize(18, 18)
        if race.note:
            self.info_label.setPixmap(res_to_pixmap("icons/notepad-text.svg", 18))
            self.info_label.setToolTip(race.note)

        self.layout = QHBoxLayout(self)
        # half the default vertical padding to keep race rows compact;
        # зліва компенсуємо внутрішній відступ TrackInfoWidget
        margins = self.layout.contentsMargins()
        self.layout.setContentsMargins(margins.left() - INFO_PADDING, margins.top() // 2,
                                       margins.right(), margins.bottom() // 2)
        # AlignVCenter: без нього віджет розтягується на всю висоту рядка (затемнення
        # при наведенні прилипає до країв, а в плашки авто вертикальні відступи
        # стають більшими за бокові)
        # stretch лише в колонок зі змінним текстом; час (формат mm:ss.xxx,
        # табличні цифри Segoe UI) та іконки (фіксовані слоти) — константної
        # ширини, тож розміряються по вмісту (stretch=0) і не ростуть з вікном
        self.layout.addWidget(as_column(self.track_info), stretch=80, alignment=Qt.AlignmentFlag.AlignVCenter)
        # авто — найширший компонент: місце, звільнене іншими колонками, віддано йому
        self.layout.addWidget(as_column(self.car_info), stretch=140, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.layout.addWidget(self.time_label)
        icons = QWidget()
        icons.setLayout(hbox([self.bad_timing_label, self.info_label], spacing=8))
        self.layout.addWidget(icons)
        self.layout.addWidget(as_column(self.created_at_label), stretch=50)
        if on_edit:
            self.layout.addWidget(edit_icon_button(lambda: on_edit(race)))
        self.setLayout(self.layout)

def _diff_cell_html(time: int, base_time: int, cell: str) -> str:
    """Різниця часу заїзду з основним часом картки: менший час — зелений, більший — червоний."""
    if not time or not base_time:
        return f"<td align='right' style='{cell} color: {style.TEXT_MUTED};'>—</td>"
    diff = time - base_time
    if diff < 0:
        color = style.DIFF_BETTER
    elif diff > 0:
        color = style.DIFF_WORSE
    else:
        color = style.TEXT
    return f"<td align='right' style='{cell} color: {color};'>{format_signed_delta(diff)}</td>"


def _races_table_html(races: list, car_rank: int, base_time: int) -> str:
    if not races:
        return ""
    header_cell = f"padding: 2px 16px 4px 0; color: {style.TEXT_MUTED}; font-size: 11px;"
    header_last_cell = f"padding: 2px 0 4px 0; color: {style.TEXT_MUTED}; font-size: 11px;"
    rows = [
        f"<tr><td align='right' style='{header_cell}'>{ui_lang.t('field.time')}</td>"
        f"<td align='right' style='{header_cell}'>{ui_lang.t('field.diff')}</td>"
        f"<td align='right' style='{header_cell}'>{ui_lang.t('field.rank')}</td>"
        f"<td style='{header_last_cell}'>{ui_lang.t('field.date')}</td></tr>"
    ]
    for r in races:
        rank_color = style.TEXT
        if r.rank and car_rank:
            if car_rank > r.rank:
                rank_color = style.RANK_UP
            elif car_rank < r.rank:
                rank_color = style.RANK_DOWN
        rank_text = f"{r.rank:,}" if r.rank else "—"
        # відступ між колонками — padding-right комірки (cellspacing розтягнув би й вертикаль)
        cell = "padding: 2px 16px 2px 0;"
        last_cell = "padding: 2px 0;"
        # nbsp: тултип загортає текст по ширині — відносна дата має лишатись одним рядком
        relative_date = format_relative_time(r.created_at).replace(" ", "&nbsp;")
        rows.append(
            f"<tr><td align='right' style='{cell}'><b>{format_time(r.time)}</b></td>"
            f"{_diff_cell_html(r.time, base_time, cell)}"
            f"<td align='right' style='{cell} color: {rank_color};'>{rank_text}</td>"
            f"<td style='{last_cell} color: {style.TEXT_MUTED};'>{relative_date}</td></tr>")
    return f"<table cellspacing='0' cellpadding='0'>{''.join(rows)}</table>"


_METRIC_DESC_KEYS = {
    "recent": "races.desc_recent",
    "best": "races.desc_best",
    "ok": "races.desc_avg_ok",
    "fail": "races.desc_avg_fail",
}


def _metric_races(agg: RaceAggregate, kind: str) -> tuple[list, int]:
    """10 заїздів показника (найкращі — для best, інакше останні) та загальна
    кількість заїздів у його агрегації."""
    svc = APP_CONTEXT.races_service
    if kind == "recent":
        return svc.get_recent_clean_races(agg.track_id, agg.car_id), agg.recent_count
    if kind == "best":
        return svc.get_best_races_for_car_on_track(agg.track_id, agg.car_id), agg.timed_count
    if kind == "ok":
        return svc.get_recent_races_for_car_on_track(agg.track_id, agg.car_id, bad_timing=False), agg.ok_count
    return svc.get_recent_races_for_car_on_track(agg.track_id, agg.car_id, bad_timing=True), agg.fail_count


def _metric_base_time(agg: RaceAggregate, kind: str) -> int:
    """Основний час показника — той, що виводиться на елементі з тултипом."""
    if kind == "recent":
        return agg.avg_recent
    if kind == "best":
        return agg.best_time
    if kind == "ok":
        return agg.avg_time
    return agg.avg_fail


def _metric_tooltip_html(agg: RaceAggregate, kind: str, base_time: int | None = None) -> str:
    races, count = _metric_races(agg, kind)
    table = _races_table_html(races, agg.car_rank, base_time or _metric_base_time(agg, kind))
    margin_top = " margin-top: 8px;" if table else ""
    # {n} є лише в описі recent-показника; для решти format нічого не міняє.
    # У recent кількість вже в описі, тож окремий рядок «Всього заїздів» зайвий.
    lines = [ui_lang.t(_METRIC_DESC_KEYS[kind]).format(n=count)]
    if kind != "recent":
        lines.append(ui_lang.t("races.metric_races_n").format(n=count))
    if base_time:
        lines.append(ui_lang.t("races.metric_diff_vs_opponent"))
    footer = (f"<p style='color: {style.TEXT_MUTED}; font-size: 11px; margin: 0;{margin_top}'>"
              f"{'<br>'.join(lines)}</p>")
    return table + footer


class _LazyMetricTooltip(QObject):
    """Тултип показника будується ліниво — запит у БД лише при наведенні,
    результат кешується у властивості віджета до перебудови списку."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.ToolTip:
            html = obj.property("_metric_html")
            if html is None:
                html = _metric_tooltip_html(obj.property("_metric_agg"), obj.property("_metric_kind"),
                                            obj.property("_metric_base"))
                obj.setProperty("_metric_html", html)
            QToolTip.showText(event.globalPos(), html, obj)
            return True
        return False


# спільний фільтр на всі картки: стан тримається у властивостях віджета
_METRIC_TOOLTIP = _LazyMetricTooltip()


def _install_metric_tooltip(widget: QWidget, agg: RaceAggregate, kind: str,
                            base_time: int | None = None):
    """base_time — база для колонки різниці замість основного часу показника
    (в асистенті різниці рахуються від часу суперника)."""
    widget.setProperty("_metric_agg", agg)
    widget.setProperty("_metric_kind", kind)
    widget.setProperty("_metric_base", base_time)
    widget.installEventFilter(_METRIC_TOOLTIP)


class RaceAggregateWidget(ListItemWidget):
    """Картка пари трек+авто в режимі агрегації: середнє за останні заїзди (головне)
    та таблиця показників — найкращий час, загальне середнє успішних, середнє невдалих."""

    def __init__(self, agg: RaceAggregate, parent=None,
                 show_track: bool = True, vs_widget: QWidget | None = None,
                 highlight_best: bool = False, opponent_time: int = 0):
        """show_track=False — без колонки треку (він відомий з контексту, як у
        підборі проти суперника); vs_widget — додаткова колонка одразу після авто;
        highlight_best — кольоровий акцент переноситься з головного середнього на
        найкращий час (режим сортування за найкращим); opponent_time — різниці в
        тултипах усіх показників рахуються від часу суперника, а не від самого
        показника."""
        super().__init__(agg, parent)
        self.track_info = None
        if show_track:
            self.track_info = TrackInfoWidget(agg.map_icon, agg.track_icon,
                                              agg.display_map_name, agg.display_track_name)
        badge = RankClassBadge(agg.car_rank, agg.car_max_rank, agg.car_class)
        self.car_info = CarInfoWidget(agg.car_icon, agg.car_brand, agg.car_model, badge)

        stats_rows = [
            self._stat_row(agg, "best", ui_lang.t("races.row_best"), format_time(agg.best_time),
                           highlight=highlight_best, opponent_time=opponent_time),
            self._stat_row(agg, "ok", ui_lang.t("races.row_avg_ok"), format_time(agg.avg_time),
                           opponent_time=opponent_time),
            # резерв ширини підпису під найширший відсоток, інакше «(100%)» проти
            # «(0%)» дає різну ширину колонки і межі гуляють між рядками
            self._stat_row(agg, "fail", f"{ui_lang.t('races.row_avg_fail')} ({agg.dislike_pct}%)",
                           format_time(agg.avg_fail),
                           caption_reserve=f"{ui_lang.t('races.row_avg_fail')} (100%)",
                           opponent_time=opponent_time),
        ]
        stats_table = QWidget()
        stats_table.setLayout(vbox(stats_rows, spacing=2))
        # Ignored-політика колонки дозволяє стискання нижче вмісту — з малим
        # stretch на вузькому вікні текст обрізався б; мінімум = власний вміст
        # (після резервів вище він однаковий у всіх картках)
        stats_table.ensurePolished()
        stats_table.setMinimumWidth(stats_table.sizeHint().width())

        self.layout = QHBoxLayout(self)
        # зліва компенсуємо внутрішній відступ TrackInfoWidget
        margins = self.layout.contentsMargins()
        self.layout.setContentsMargins(margins.left() - INFO_PADDING, margins.top() // 2,
                                       margins.right(), margins.bottom() // 2)
        # AlignVCenter: без нього віджет розтягується на всю висоту рядка (затемнення
        # при наведенні прилипає до країв, а в плашки авто вертикальні відступи
        # стають більшими за бокові)
        # головний час — по вмісту (найширший елемент колонки — підпис «середнє
        # за N» — практично константний); лічильник і таблиця показників мають
        # текст змінної довжини (форма слова, відсоток), тому лишаються на
        # stretch — з шириною по вмісту їхні межі гуляли б між рядками
        if self.track_info is not None:
            self.layout.addWidget(as_column(self.track_info), stretch=80, alignment=Qt.AlignmentFlag.AlignVCenter)
        # авто — найширший компонент: місце, звільнене іншими колонками, віддано йому
        self.layout.addWidget(as_column(self.car_info), stretch=148, alignment=Qt.AlignmentFlag.AlignVCenter)
        if vs_widget is not None:
            self.layout.addWidget(as_column(vs_widget), stretch=48)
        self.layout.addWidget(as_column(self._race_count_stat(agg)), stretch=32)
        self.layout.addWidget(self._main_stat(agg, highlight_best, opponent_time))
        self.layout.addWidget(as_column(stats_table), stretch=38)
        self.setLayout(self.layout)

    def _main_stat(self, agg: RaceAggregate, highlight_best: bool = False,
                   opponent_time: int = 0) -> QWidget:
        value_label = QLabel(format_time(agg.avg_recent) or "—")
        # при сортуванні за найкращим зелений акцент іде на рядок best,
        # головний середній лишається білим (дефолтний колір QLabel)
        if not highlight_best:
            value_label.setObjectName("rowTimeLabel")
        value_font = QFont()
        value_font.setBold(True)
        value_font.setPointSize(self.font().pointSize() + 4)
        value_label.setFont(value_font)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        caption_label = QLabel(ui_lang.t("races.avg_over_n").format(n=agg.recent_count))
        caption_label.setStyleSheet(f"color: {style.TEXT_MUTED}; font-size: 11px;")
        caption_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # підпис — найширший елемент колонки, а колонка розміряється по вмісту:
        # резерв під двозначне N (максимум 10, див. get_recent_clean_races),
        # щоб рядки з різним N не мали різну ширину колонки
        caption_label.ensurePolished()
        caption_label.setMinimumWidth(caption_label.fontMetrics().horizontalAdvance(
            ui_lang.t("races.avg_over_n").format(n=10)))

        column = QWidget()
        # plain QWidget ігнорує QSS-фон без цього атрибута (затемнення при наведенні)
        column.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        column.setObjectName("aggMainStat")
        layout = vbox([value_label, caption_label], spacing=2)
        # колонка тепер шириною по вмісту — відступи, щоб hover-підсвітка
        # не прилипала до країв тексту
        layout.setContentsMargins(8, 0, 8, 0)
        column.setLayout(layout)
        _install_metric_tooltip(column, agg, "recent", opponent_time or None)
        return column

    def _race_count_stat(self, agg: RaceAggregate) -> QWidget:
        value_label = QLabel(str(agg.race_count))
        # мало заїздів — статистика ненадійна: < 5 червона цифра, < 10 помаранчева
        if agg.race_count < 5:
            value_label.setStyleSheet(f"color: {style.DIFF_WORSE};")
        elif agg.race_count < 10:
            value_label.setStyleSheet(f"color: {style.COUNT_WARN};")
        value_font = QFont()
        value_font.setBold(True)
        value_font.setPointSize(self.font().pointSize() + 4)
        value_label.setFont(value_font)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        caption_label = QLabel(ui_lang.runs_word(agg.race_count))
        caption_label.setStyleSheet(f"color: {style.TEXT_MUTED}; font-size: 11px;")
        caption_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        column = QWidget()
        column.setLayout(vbox([value_label, caption_label], spacing=2))
        return column

    @staticmethod
    def _stat_row(agg: RaceAggregate, kind: str, caption: str, value: str,
                  caption_reserve: str = "", highlight: bool = False,
                  opponent_time: int = 0) -> QWidget:
        caption_label = QLabel(caption)
        caption_label.setStyleSheet(f"color: {style.TEXT_MUTED}; font-size: 11px;")
        if caption_reserve:
            caption_label.ensurePolished()
            caption_label.setMinimumWidth(
                caption_label.fontMetrics().horizontalAdvance(caption_reserve))

        value_label = QLabel(value or "—")
        if highlight:
            value_label.setStyleSheet(f"color: {style.TIME_YELLOW};")
        value_font = QFont()
        value_font.setBold(True)
        value_label.setFont(value_font)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        # «—» вужче за час — без резерву рядки без значення були б вужчими
        value_label.setMinimumWidth(
            QFontMetrics(value_font).horizontalAdvance(format_time(599_999)))

        row = QWidget()
        # plain QWidget ігнорує QSS-фон без цього атрибута (затемнення при наведенні)
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row.setObjectName("aggStatRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(4, 0, 4, 0)
        row_layout.setSpacing(8)
        row_layout.addWidget(caption_label, stretch=1)
        row_layout.addWidget(value_label)
        _install_metric_tooltip(row, agg, kind, opponent_time or None)
        return row


class RacesTab(QWidget):
    def __init__(self):
        super().__init__()

        self.track_query = QLineEdit()
        enable_search_icon(self.track_query)
        enable_clear_button(self.track_query)
        self.track_query.installEventFilter(CLEAR_ON_ESC_FILTER)
        self.track_query.setPlaceholderText(ui_lang.t("field.track"))
        self.track_debounce = InputDebounce(self.track_query, on_change=self.on_search)

        self.car_query = QLineEdit()
        enable_search_icon(self.car_query)
        enable_clear_button(self.car_query)
        self.car_query.installEventFilter(CLEAR_ON_ESC_FILTER)
        self.car_query.setPlaceholderText(ui_lang.t("field.car"))
        self.car_debounce = InputDebounce(self.car_query, on_change=self.on_search)

        self.sort_combo = QComboBox()
        self._sort_icon = QIcon(get_resource_path("icons/sort.svg"))
        self.sort_combo.setToolTip(ui_lang.t("cars.sort_order"))
        self.sort_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self._set_sort_items(aggregated=False)
        self.sort_combo.currentIndexChanged.connect(self.on_search) # type: ignore

        self.aggregate_button = QPushButton(ui_lang.t("races.aggregate"))
        self.aggregate_button.setObjectName("secondary")
        self.aggregate_button.setCheckable(True)
        self.aggregate_button.setToolTip(ui_lang.t("races.aggregate_hint"))
        self.aggregate_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.aggregate_button.toggled.connect(self.on_aggregate_toggled) # type: ignore

        self.add_button = QPushButton(ui_lang.t("common.add"))
        self.add_button.clicked.connect(self.on_add) # type: ignore

        self.list_widget = QListWidget()

        self.count_label = QLabel()
        self.count_label.setStyleSheet(f"color: {style.TEXT_MUTED}; font-size: 12px;")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.track_query)
        top_layout.addWidget(self.car_query)
        top_layout.addWidget(self.sort_combo)
        top_layout.addWidget(self.aggregate_button)
        top_layout.addSpacing(16)
        top_layout.addWidget(self.add_button)

        layout = QVBoxLayout()
        layout.addLayout(top_layout)
        layout.addWidget(self.list_widget)
        layout.addWidget(self.count_label)
        self.setLayout(layout)

        # перебудова списку дорога (100 композитних рядків), тому робимо її лише коли дані
        # реально змінились. Сервіси гонок/авто/треків/мап сигналять про мутації.
        self._dirty = False
        self._rebuild()
        for svc in (APP_CONTEXT.races_service, APP_CONTEXT.cars_service,
                    APP_CONTEXT.tracks_service, APP_CONTEXT.maps_service):
            svc.add_listener(self._mark_dirty)
        # зміна мови гри змінює відображувані назви — перебудувати при наступному показі
        game_lang.add_listener(self._mark_dirty)

    def _mark_dirty(self):
        self._dirty = True

    def refresh(self):
        # викликається при кожному перемиканні на вкладку — перебудова лише за потреби
        if self._dirty:
            self._rebuild()

    def _rebuild(self):
        track_query = self.track_query.text().strip()
        car_query = self.car_query.text().strip()
        with preserved_scroll(self.list_widget):
            self.list_widget.clear()
            # в обох режимах другий пункт комбобокса — «найкращий час»
            by_best_time = self.sort_combo.currentIndex() == 1
            if self.aggregate_button.isChecked():
                for a in APP_CONTEXT.races_service.get_aggregates(track_query, car_query, by_best_time):
                    RaceAggregateWidget(a, highlight_best=by_best_time).add_to_list(self.list_widget)
                total = APP_CONTEXT.races_service.count_aggregates(track_query, car_query)
            else:
                for i in APP_CONTEXT.races_service.get_all(track_query, car_query, by_best_time):
                    RaceListWidget(i, on_edit=self.on_edit).add_to_list(self.list_widget)
                total = APP_CONTEXT.races_service.count(track_query, car_query)
        shown = min(total, APP_CONTEXT.races_service.list_limit)
        self.count_label.setText(ui_lang.t("common.shown_count").format(shown=shown, total=total))
        self._dirty = False

    def on_search(self):
        self._rebuild()  # фільтр змінився — перебудова обов'язкова
        self.list_widget.scrollToTop()  # результати з початку

    def _set_sort_items(self, aggregated: bool):
        first = ui_lang.t("races.sort_avg") if aggregated else ui_lang.t("races.sort_latest")
        self.sort_combo.clear()
        self.sort_combo.addItem(self._sort_icon, first)
        self.sort_combo.addItem(self._sort_icon, ui_lang.t("races.sort_best"))

    def on_aggregate_toggled(self, checked: bool):
        # перемикання режиму скидає сортування на дефолтне; сигнали глушимо,
        # щоб clear/addItem не викликали зайвих перебудов — on_search зробить одну
        self.sort_combo.blockSignals(True)
        self._set_sort_items(aggregated=checked)
        self.sort_combo.blockSignals(False)
        self.on_search()

    def on_add(self):
        if RaceDialog(item=RaceView(), action=APP_CONTEXT.races_service.save, parent=self).exec():
            self._rebuild()

    def on_edit(self, race: RaceView):
        if RaceDialog(item=race, action=APP_CONTEXT.races_service.save, parent=self).exec():
            self._rebuild()
