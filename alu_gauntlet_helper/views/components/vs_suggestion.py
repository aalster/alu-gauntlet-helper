from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QLabel, QWidget, QVBoxLayout

from alu_gauntlet_helper import ui_lang
from alu_gauntlet_helper.services.assistant import VsSuggestion
from alu_gauntlet_helper.services.races import RaceAggregate
from alu_gauntlet_helper.utils.utils import format_signed_delta
from alu_gauntlet_helper.views import style
from alu_gauntlet_helper.views.races_tab import RaceAggregateWidget




class VsStatsWidget(QWidget):
    """Колонка статистики проти суперника: «7/10 побито» + кольорова Δ."""

    def __init__(self, vs: VsSuggestion, parent=None):
        super().__init__(parent)
        value_label = QLabel(f"{vs.beat_count}/{vs.sample_count}")
        value_font = QFont()
        value_font.setBold(True)
        value_font.setPointSize(self.font().pointSize() + 4)
        value_label.setFont(value_font)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        caption_label = QLabel(ui_lang.t("assistant.beaten_caption"))
        caption_label.setStyleSheet(f"color: {style.TEXT_MUTED}; font-size: 11px;")
        caption_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ті самі кольори, що й для «різниці часу» в races_tab — семантика та сама;
        # vs.delta = opponent - avg, а показуємо «мій мінус суперника» (я швидший → −)
        delta_color = style.DIFF_BETTER if vs.delta >= 0 else style.DIFF_WORSE
        delta_label = QLabel(format_signed_delta(-vs.delta))
        delta_label.setStyleSheet(f"color: {delta_color}; font-size: 12px; font-weight: bold;")
        delta_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(2)
        layout.addWidget(value_label)
        layout.addWidget(caption_label)
        layout.addWidget(delta_label)


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
