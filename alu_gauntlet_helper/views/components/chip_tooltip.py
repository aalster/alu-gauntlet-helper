from alu_gauntlet_helper import ui_lang
from alu_gauntlet_helper.utils.utils import format_signed_delta, format_time
from alu_gauntlet_helper.views import style


def prob_percent(p: float) -> int:
    """Відсоток для чипа/тултіпа, ніколи не 100: інші кандидати завжди мають
    ненульову вагу (суперник міг просто погано проїхати свій трек)."""
    return min(99, round(p * 100))


def chip_tooltip_html(p: float | None, stats: tuple[int, int] | None,
                      opponent_time: int, icon_html: str = "") -> str:
    """Єдиний тултіп чипа треку — з наявних частин: «Збіг ... {p}%», таблиця
    часів у стилі тултіпа VsStatsWidget (суперник / моя медіана / різниця
    «мій мінус суперника»), превʼю маршруту внизу (готовий <img> від
    image_preview_html). Чого немає — не виводиться; "" — не вішати тултіп."""
    def row(value: str, label: str) -> str:
        return (f"<tr><td align='right'>{value}</td>"
                f"<td style='padding-left:8px'>{label}</td></tr>")

    rows = []
    if opponent_time:
        rows.append(row(format_time(opponent_time),
                        ui_lang.t("assistant.vs_tooltip_opponent")))
    if stats:
        median, n = stats
        rows.append(row(format_time(median),
                        ui_lang.t("assistant.chip_tooltip_median").format(n=n)))
        if opponent_time:
            delta = median - opponent_time
            delta_color = style.DIFF_BETTER if delta <= 0 else style.DIFF_WORSE
            rows.append(row(
                f"<span style='color:{delta_color}'>{format_signed_delta(delta)}</span>",
                ui_lang.t("assistant.vs_tooltip_delta")))
    parts = []
    if p is not None:
        header = ui_lang.t("assistant.track_prob_chip_tooltip").format(p=prob_percent(p))
        parts.append(f"<b>{header}</b>")
    if rows:
        parts.append("<table cellspacing='0' cellpadding='1'>" + "".join(rows) + "</table>")
    html = "<br>".join(parts)
    if icon_html:
        # порожній рядок-відступ: Qt rich text не дає паддінгу на <img>
        html = html + "<br><br>" + icon_html if html else icon_html
    return html
