from alu_gauntlet_helper import ui_lang
from alu_gauntlet_helper.services.challenge_session import RACE_COUNT
from alu_gauntlet_helper.utils.utils import format_signed_delta, format_time
from alu_gauntlet_helper.views import style


def prob_percent(p: float) -> int:
    """Відсоток для чипа/тултіпа, ніколи не 100: інші кандидати завжди мають
    ненульову вагу (суперник міг просто погано проїхати свій трек)."""
    return min(99, round(p * 100))


def _row(value: str, label: str) -> str:
    """Рядок двоколонкової таблиці тултіпа: значення (праве вирівнювання) + підпис.
    nowrap: rich-text тултіпи Qt мають примусовий word-wrap і без нього
    переносять підпис на другий рядок."""
    return (f"<tr><td align='right'>{value}</td>"
            f"<td style='padding-left:8px;white-space:nowrap'>{label}</td></tr>")


def goal_percent(dist: list[float], goal: int) -> int:
    """P(≥goal перемог) у відсотках — число на кнопці режиму."""
    return round(sum(dist[goal:]) * 100)


def goal_label(goal: int, dist: list[float] | None) -> str:
    """Rich-text підпис кнопки режиму: «5/5» кольору кнопки + «72%» кольору
    шансу (пороги win_chance_color); без часів суперника — просто «5/5»."""
    label = f"{goal}/{RACE_COUNT}"
    if dist is None:
        return label
    pct = goal_percent(dist, goal)
    return f"{label} <span style='color:{style.win_chance_color(pct)}'>{pct}%</span>"


# найширший підпис — під нього резервується ширина кнопки (GoalButton.reserve_width)
WIDEST_GOAL_LABEL = goal_label(RACE_COUNT, [0.0] * RACE_COUNT + [1.0])


def win_chance_tooltip(dist: list[float], goal: int | None = None) -> str:
    """Тултіп кнопки режиму — таблиця «{p}% | шанс виграти щонайменше N
    гонки» для N=3..4 і «... всі гонки» для N=5 за підбором цього режиму;
    рядок самого режиму (goal) жирний — його відсоток і є на кнопці.
    Кольори — пороги win_chance_color."""
    rows = []
    for n in range(3, len(dist)):
        pct = goal_percent(dist, n)
        p = f"<span style='color:{style.win_chance_color(pct)}'>{pct}%</span>"
        label = (ui_lang.t("assistant.win_all") if n == len(dist) - 1
                 else ui_lang.t("assistant.win_at_least").format(n=n))
        if n == goal:
            p, label = f"<b>{p}</b>", f"<b>{label}</b>"
        rows.append(_row(p, label))
    return "<table cellspacing='0' cellpadding='1'>" + "".join(rows) + "</table>"


def chip_tooltip_html(p: float | None, stats: tuple[int, int] | None,
                      opponent_time: int, icon_html: str = "") -> str:
    """Єдиний тултіп чипа треку — з наявних частин: «Збіг ... {p}%», таблиця
    часів у стилі тултіпа VsStatsWidget (суперник / моя медіана / різниця
    «мій мінус суперника»), превʼю маршруту внизу (готовий <img> від
    image_preview_html). Чого немає — не виводиться; "" — не вішати тултіп."""
    rows = []
    if opponent_time:
        rows.append(_row(format_time(opponent_time),
                         ui_lang.t("assistant.vs_tooltip_opponent")))
    if stats:
        median, n = stats
        rows.append(_row(format_time(median),
                         ui_lang.t("assistant.chip_tooltip_median").format(n=n)))
        if opponent_time:
            delta = median - opponent_time
            delta_color = style.DIFF_BETTER if delta <= 0 else style.DIFF_WORSE
            rows.append(_row(
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
