"""Чиста математика автопідбору авто проти суперника: ціль — щонайменше
k перемог з 5 (режим сесії 3/5, 4/5 чи 5/5).

Обґрунтування K = кількості вільних гонок (аргумент обміну): інші N-1 гонок
займають щонайбільше N-1 авто з топ-N будь-якої гонки, тож завжди лишається
вільний кандидат не гірший за будь-якого поза топ-N; P(≥k) і Σp монотонні по
кожному p окремо, тому обмін не погіршує рішення. Умова коректності:
кандидати ранжуються ТИМ САМИМ ключем (p ↓, margin ↓), що й цільова функція.
"""
from typing import NamedTuple


class Candidate(NamedTuple):
    car_id: int
    p: float    # шанс побити час суперника, Φ(Δ/σ) (0.5 = невідомо)
    margin: int  # запас, мс: opponent_time - avg_recent (або -avg без часу суперника)


def win_distribution(probs: list[float]) -> list[float]:
    """dist[j] = точна P(рівно j успіхів) незалежних подій — Пуассон-біноміальний DP."""
    dist = [1.0]
    for p in probs:
        nxt = [0.0] * (len(dist) + 1)
        for j, q in enumerate(dist):
            nxt[j] += q * (1 - p)
            nxt[j + 1] += q * p
        dist = nxt
    return dist


def prob_at_least(probs: list[float], k: int) -> float:
    """Точна P(≥k успіхів) незалежних подій — хвіст win_distribution."""
    dist = win_distribution(probs)
    return sum(dist[k:]) if k < len(dist) else 0.0


def pick_cars(race_candidates: dict[int, list[Candidate]],
              pinned: dict[int, int], wins_needed: int) -> dict[int, int]:
    """Оптимальне призначення різних авто на гонки.

    race_candidates — лише гонки, де є що обирати (може бути < 5).
    pinned {race_number: car_id} — зафіксовані вручну: входять у відповідь
    як є, їхні авто виключаються з пулів інших гонок.
    Ціль: max (P(≥wins_needed перемог), очікувана кількість перемог Σp,
    сума маржинів) лексикографічно. Σp розрізняє варіанти, коли ціль уже
    досягнута чи вже недосяжна (P(≥k) = 1 або 0 для будь-якого підбору) —
    тоді виграємо якомога більше гонок."""
    pinned_cars = set(pinned.values())
    free_races = [r for r in sorted(race_candidates) if r not in pinned]

    k = max(1, len(free_races))
    pools = {}
    for r in free_races:
        pool = [c for c in race_candidates[r] if c.car_id not in pinned_cars]
        pool.sort(key=lambda c: (-c.p, -c.margin))
        pools[r] = pool[:k]

    # внесок запінених гонок у ймовірність: p їхнього авто (0.5, як невідомо)
    base_probs = []
    for r, car_id in pinned.items():
        cand = next((c for c in race_candidates.get(r, []) if c.car_id == car_id), None)
        base_probs.append(cand.p if cand else 0.5)

    best_score = (-1.0, -1.0, float("-inf"))
    best_picks: dict[int, int] = {}

    def dfs(idx: int, used: set, picks: dict, probs: list, margin_sum: int):
        nonlocal best_score, best_picks
        if idx == len(free_races):
            all_probs = base_probs + probs
            score = (prob_at_least(all_probs, wins_needed), sum(all_probs), margin_sum)
            if score > best_score:
                best_score, best_picks = score, dict(picks)
            return
        r = free_races[idx]
        options = [c for c in pools[r] if c.car_id not in used]
        if not options:  # всі кандидати розібрані — гонка без призначення
            dfs(idx + 1, used, picks, probs + [0.5], margin_sum)
            return
        for c in options:
            used.add(c.car_id)
            picks[r] = c.car_id
            dfs(idx + 1, used, picks, probs + [c.p], margin_sum + c.margin)
            del picks[r]
            used.discard(c.car_id)

    dfs(0, set(), {}, [], 0)
    return {**pinned, **best_picks}
