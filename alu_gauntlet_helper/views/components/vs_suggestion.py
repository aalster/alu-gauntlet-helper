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
    """Колонка статистики проти суперника: Δ «мій мінус суперника» крупно
    (−1.300 = я швидший, зелена), під нею «7/10 побито» дрібно. Модельний
    шанс гонки Φ(Δ/σ) — лише в тултіпі."""

    def __init__(self, vs: VsSuggestion, parent=None):
        super().__init__(parent)
        # той самий ховер-фон, що в колонок статистики агрегації (QSS #vsStats);
        # plain QWidget ігнорує QSS-фон без WA_StyledBackground
        self.setObjectName("vsStats")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setToolTip(self._tooltip(vs))
        # ті самі кольори й знак, що на картці гонки та в оверлеї; нічия = програш
        delta_color = style.WIN_BRIGHT if vs.delta > 0 else style.LOSS_BRIGHT
        self.delta_label = QLabel(format_signed_delta(-vs.delta))
        delta_font = QFont()
        delta_font.setBold(True)
        delta_font.setPointSize(self.font().pointSize() + 4)
        self.delta_label.setFont(delta_font)
        self.delta_label.setStyleSheet(f"color: {delta_color};")
        self.delta_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.beaten_label = QLabel(ui_lang.t("assistant.beaten").format(
            wins=vs.beat_count, n=vs.sample_count))
        self.beaten_label.setStyleSheet(f"color: {style.TEXT_MUTED}; font-size: 11px;")
        self.beaten_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        # бічні відступи більші, ніж було (4): ховер-підсвітка не прилипає до тексту
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(2)
        layout.addWidget(self.delta_label)
        layout.addWidget(self.beaten_label)

    @staticmethod
    def _tooltip(vs: VsSuggestion) -> str:
        """Докладна розшифровка колонки: модельний шанс гонки, вибірка +
        таблиця часів (суперник / мій середній / різниця)."""
        def row(value: str, label: str) -> str:
            return (f"<tr><td align='right'>{value}</td>"
                    f"<td style='padding-left:8px'>{label}</td></tr>")

        # у рядку різниці — «мій мінус суперника», як у колонці (я швидший → −)
        delta_color = style.WIN_BRIGHT if vs.delta > 0 else style.LOSS_BRIGHT
        table = "<table cellspacing='0' cellpadding='1'>" + row(
            format_time(vs.opponent_time),
            ui_lang.t("assistant.vs_tooltip_opponent")) + row(
            format_time(vs.avg_time),
            ui_lang.t("assistant.vs_tooltip_avg").format(n=vs.sample_count)) + row(
            f"<span style='color:{delta_color}'>{format_signed_delta(-vs.delta)}</span>",
            ui_lang.t("assistant.vs_tooltip_delta")) + "</table>"
        return "<br>".join([
            f"<b>{ui_lang.t('assistant.vs_tooltip_chance').format(p=round(vs.p * 100))}</b>",
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
                         vs_widget=VsStatsWidget(vs) if has_opponent_time else None,
                         opponent_time=vs.opponent_time)
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
            effect.setOpacity(0.5)
            self.setGraphicsEffect(effect)
        else:
            self.setGraphicsEffect(None)
