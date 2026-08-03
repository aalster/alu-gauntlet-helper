from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QLabel, QWidget, QVBoxLayout

from alu_gauntlet_helper import ui_lang
from alu_gauntlet_helper.services.assistant import VsSuggestion
from alu_gauntlet_helper.services.races import RaceAggregate
from alu_gauntlet_helper.utils.utils import format_signed_delta, format_time
from alu_gauntlet_helper.views import style
from alu_gauntlet_helper.views.races_tab import RaceAggregateWidget




class VsStatsWidget(QWidget):
    """Колонка статистики проти суперника: шанс перемоги крупно, під ним
    «7/10 побито» дрібно одним рядком + кольорова Δ."""

    def __init__(self, vs: VsSuggestion, parent=None):
        super().__init__(parent)
        # той самий ховер-фон, що в колонок статистики агрегації (QSS #vsStats);
        # plain QWidget ігнорує QSS-фон без WA_StyledBackground
        self.setObjectName("vsStats")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setToolTip(self._tooltip(vs))
        # той самий кольоровий відсоток, що на картці гонки (лапласова оцінка
        # вже порахована в p_smoothed)
        chance_color = style.WIN_BRIGHT if vs.p_smoothed >= 0.5 else style.LOSS_BRIGHT
        chance_label = QLabel(f"{round(vs.p_smoothed * 100)}%")
        chance_font = QFont()
        chance_font.setBold(True)
        chance_font.setPointSize(self.font().pointSize() + 4)
        chance_label.setFont(chance_font)
        chance_label.setStyleSheet(f"color: {chance_color};")
        chance_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        beaten_label = QLabel(ui_lang.t("assistant.beaten").format(
            wins=vs.beat_count, n=vs.sample_count))
        beaten_label.setStyleSheet(f"color: {style.TEXT_MUTED}; font-size: 11px;")
        beaten_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ті самі кольори, що й для «різниці часу» в races_tab — семантика та сама;
        # vs.delta = opponent - avg, а показуємо «мій мінус суперника» (я швидший → −)
        delta_color = style.DIFF_BETTER if vs.delta >= 0 else style.DIFF_WORSE
        delta_label = QLabel(format_signed_delta(-vs.delta))
        delta_label.setStyleSheet(f"color: {delta_color}; font-size: 12px; font-weight: bold;")
        delta_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        # бічні відступи більші, ніж було (4): ховер-підсвітка не прилипає до тексту
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(2)
        layout.addWidget(chance_label)
        layout.addWidget(beaten_label)
        layout.addWidget(delta_label)

    @staticmethod
    def _tooltip(vs: VsSuggestion) -> str:
        """Докладна розшифровка колонки: шанс, вибірка + таблиця часів
        (суперник / мій середній / різниця)."""
        def row(value: str, label: str) -> str:
            return (f"<tr><td align='right'>{value}</td>"
                    f"<td style='padding-left:8px'>{label}</td></tr>")

        # vs.delta = opponent - avg, тож час суперника відновлюється як avg + delta;
        # у рядку різниці — «мій мінус суперника», як у колонці (я швидший → −)
        delta_color = style.DIFF_BETTER if vs.delta >= 0 else style.DIFF_WORSE
        table = "<table cellspacing='0' cellpadding='1'>" + row(
            format_time(vs.avg_time + vs.delta),
            ui_lang.t("assistant.vs_tooltip_opponent")) + row(
            format_time(vs.avg_time),
            ui_lang.t("assistant.vs_tooltip_avg").format(n=vs.sample_count)) + row(
            f"<span style='color:{delta_color}'>{format_signed_delta(-vs.delta)}</span>",
            ui_lang.t("assistant.vs_tooltip_delta")) + "</table>"
        return "<br>".join([
            f"<b>{ui_lang.t('assistant.vs_tooltip_chance').format(p=round(vs.p_smoothed * 100))}</b>",
            ui_lang.t("assistant.vs_tooltip_beaten").format(wins=vs.beat_count,
                                                            n=vs.sample_count),
            table,
        ])


class VsSuggestionWidget(RaceAggregateWidget):
    """Рядок пропозиції авто проти суперника: та сама картка агрегації, що на
    вкладці заїздів, але без колонки треку (він уже показаний у картці гонки
    вище) і з колонкою «N/10 побито · Δ» одразу після авто."""

    def __init__(self, agg: RaceAggregate, vs: VsSuggestion, has_opponent_time: bool, parent=None):
        super().__init__(agg, parent, show_track=False,
                         vs_widget=VsStatsWidget(vs) if has_opponent_time else None)
        self.car_id = vs.car_id
        self.car_name = vs.car_name

    def set_dimmed(self, dimmed: bool):
        # setEnabled сам по собі притлумлює лише піксмапи (іконку авто): кольори
        # тексту задані глобальним QSS без :disabled-правил і не міняються.
        # Тому весь рядок притемнюємо opacity-ефектом — рівномірно, разом з
        # бейджами і кольоровими дельтами.
        self.setEnabled(not dimmed)
        if dimmed:
            effect = QGraphicsOpacityEffect(self)
            effect.setOpacity(0.35)
            self.setGraphicsEffect(effect)
        else:
            self.setGraphicsEffect(None)
