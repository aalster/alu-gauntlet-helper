from alu_gauntlet_helper.services.opponent_picker import (Candidate, pick_cars,
                                                          prob_at_least, win_distribution)


def test_prob_at_least_exact_values():
    assert prob_at_least([], 3) == 0.0
    assert prob_at_least([1.0, 1.0, 1.0, 0.0, 0.0], 3) == 1.0
    assert abs(prob_at_least([0.5] * 5, 3) - 0.5) < 1e-9  # симетрія біноміального
    # 4 гонки по 0.5: P(>=3) = (C(4,3)+C(4,4))/16 = 5/16
    assert abs(prob_at_least([0.5] * 4, 3) - 5 / 16) < 1e-9


def test_win_distribution_exact_values():
    assert win_distribution([]) == [1.0]
    assert win_distribution([0.5, 0.5]) == [0.25, 0.5, 0.25]  # біноміальний
    probs = [0.9, 0.5, 0.3, 0.7, 0.5]
    dist = win_distribution(probs)
    assert len(dist) == 6
    assert abs(sum(dist) - 1.0) < 1e-9
    # узгодженість із prob_at_least: хвіст розподілу і є P(≥3)
    assert abs(sum(dist[3:]) - prob_at_least(probs, 3)) < 1e-9


def test_pick_assigns_distinct_cars():
    shared = [Candidate(1, 0.9, 100), Candidate(2, 0.8, 100), Candidate(3, 0.7, 100)]
    picks = pick_cars({1: shared, 2: shared, 3: shared}, pinned={})
    assert sorted(picks) == [1, 2, 3]
    assert len(set(picks.values())) == 3  # усі авто різні


def test_pick_prefers_reliability_over_one_star_race():
    # авто 1 сильне всюди; жадібний віддав би його гонці 1, але глобально
    # краще як у оптимумі — перевіряємо проти повного перебору
    candidates = {
        1: [Candidate(1, 0.9, 500), Candidate(2, 0.85, 100)],
        2: [Candidate(1, 0.6, 50), Candidate(3, 0.55, 40)],
        3: [Candidate(1, 0.95, 300), Candidate(4, 0.5, 10)],
    }
    picks = pick_cars(candidates, pinned={})
    # оптимум у цьому кейсі єдиний — можна порівняти призначення напряму
    assert picks == brute_force(candidates)[0]


def score_of(race_candidates, assignment):
    """(P(≥3), сума маржинів) призначення — та сама ціль, що й у pick_cars."""
    chosen = [next(c for c in race_candidates[r] if c.car_id == car_id)
              for r, car_id in assignment.items()]
    return (prob_at_least([c.p for c in chosen], 3), sum(c.margin for c in chosen))


def brute_force(race_candidates):
    races = sorted(race_candidates)
    best, best_score = None, (-1.0, float("-inf"))
    pools = [race_candidates[r] for r in races]
    def rec(i, used, acc):
        nonlocal best, best_score
        if i == len(races):
            probs = [c.p for c in acc]
            score = (prob_at_least(probs, 3), sum(c.margin for c in acc))
            if score > best_score:
                best_score, best = score, {r: c.car_id for r, c in zip(races, acc)}
            return
        for c in pools[i]:
            if c.car_id not in used:
                rec(i + 1, used | {c.car_id}, acc + [c])
    rec(0, set(), [])
    return best, best_score


def test_pick_matches_brute_force_on_dense_case():
    # 5 гонок × 6 спільних авто з різними p/margin — топ-K не має губити оптимум.
    # Порівнюємо СКОРИ, а не словники: оптимумів з однаковим скором може бути кілька.
    cars = range(1, 7)
    candidates = {
        r: [Candidate(c, ((c * 7 + r * 3) % 10) / 10 + 0.05, (c * 13 + r * 5) % 200)
            for c in cars]
        for r in range(1, 6)
    }
    picks = pick_cars(candidates, pinned={})
    _, best_score = brute_force(candidates)
    got_p, got_margin = score_of(candidates, picks)
    assert abs(got_p - best_score[0]) < 1e-9
    assert got_margin == best_score[1]


def test_pinned_car_excluded_from_other_races():
    shared = [Candidate(1, 0.9, 100), Candidate(2, 0.8, 90), Candidate(3, 0.7, 80)]
    picks = pick_cars({1: shared, 2: shared, 3: shared}, pinned={2: 1})
    assert picks[2] == 1
    assert picks[1] != 1 and picks[3] != 1


def test_race_without_free_candidates_left_unassigned():
    picks = pick_cars({1: [Candidate(1, 0.9, 10)], 2: [Candidate(1, 0.9, 10)]}, pinned={})
    # авто одне на двох — одна гонка лишається без призначення
    assert len(picks) == 1


def test_tie_break_by_margin_sum():
    candidates = {
        1: [Candidate(1, 0.8, 10), Candidate(2, 0.8, 500)],
        2: [Candidate(1, 0.8, 500), Candidate(2, 0.8, 10)],
    }
    picks = pick_cars(candidates, pinned={})
    assert picks == {1: 2, 2: 1}  # однакове P, але сума маржинів 1000 > 20
