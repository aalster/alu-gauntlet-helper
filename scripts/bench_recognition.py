"""Замір продуктивності розпізнавання: OCR-виклики + час + коректність.

Лічить, скільки разів кожен екстрактор спавнить tesseract (через monkeypatch
pytesseract.image_to_string), скільки на це йде часу, і чи правильний результат.
Порівнює поточний ChallengeAccordionExtractor зі швидким CarSelectionFastExtractor
на повільних RU-скрінах (екран CAR SELECTION).

Запуск (з кореня, .venv):
  .\\.venv\\Scripts\\python.exe -m scripts.bench_recognition
"""
import sys
import time
from pathlib import Path

import cv2
import pytesseract

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alu_gauntlet_helper.screen_recognition import ocr  # noqa: E402
from alu_gauntlet_helper.screen_recognition.screens.challenge_accordion import (  # noqa: E402
    ChallengeAccordionExtractor,
)
from alu_gauntlet_helper.screen_recognition.screens.car_selection_fast import (  # noqa: E402
    CarSelectionFastExtractor,
)
from alu_gauntlet_helper.screen_recognition.screens.race_result import (  # noqa: E402
    RaceResultExtractor,
)
from alu_gauntlet_helper.screen_recognition.screens.race_result_fast import (  # noqa: E402
    RaceResultFastExtractor,
)
from alu_gauntlet_helper.screen_recognition.screens.challenge_complete import (  # noqa: E402
    ChallengeCompleteExtractor,
)
from alu_gauntlet_helper.screen_recognition.screens.challenge_complete_fast import (  # noqa: E402
    ChallengeCompleteFastExtractor,
)
from tests.recognition_vocab import build_resolvers, car_label, track_label  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

# Очікувані результати на повільних RU-скрінах CAR SELECTION (ground truth).
EXPECTED = {
    "car_selection_ru_1_sf.png": dict(race=1, map="San Francisco", track="Railroad Bustle",
                                      car="Rimac Nevera Time Attack", rank=4835, lang="ru"),
    "car_selection_ru_2_auckland.png": dict(race=2, map="Auckland", track="Straight Sprint",
                                            car="Ferrari SF90 Stradale", rank=4795, lang="ru"),
    "accordion_ru_1_nevada.png": dict(race=1, map="Nevada", track="Bridge to Bridge",
                                      car="Bugatti Chiron", rank=5130, lang="ru"),
    "accordion_ru_2_osaka.png": dict(race=2, map="Osaka", track="Namba Park",
                                     car="Vanda Electrics Dendrobium", rank=4099, lang="ru"),
    "accordion_ru_3_new_york.png": dict(race=3, map="New York", track="Wall Street Ride",
                                        car="Koenigsegg CCXR", rank=4998, lang="ru"),
    "accordion_ru_4_singapore.png": dict(race=4, map="Singapore", track="Urban Rush",
                                         car="Rimac Nevera Time Attack", rank=4835, lang="ru"),
    "accordion_ru_5_scotland.png": dict(race=5, map="Scotland", track="Rocky Valley",
                                        car="Ferrari SF90 Stradale", rank=4795, lang="ru"),
}


class OcrCounter:
    """Контекст: рахує виклики pytesseract.image_to_string."""

    def __enter__(self):
        self.count = 0
        self._orig = pytesseract.image_to_string

        def wrapped(*a, **k):
            self.count += 1
            return self._orig(*a, **k)

        pytesseract.image_to_string = wrapped
        return self

    def __exit__(self, *exc):
        pytesseract.image_to_string = self._orig


def check(capture, exp, tv, cv) -> tuple[bool, str]:
    """Чи збігається захоплення з очікуванням. Повертає (ok, опис розбіжностей)."""
    if capture is None:
        return False, "немає захоплення"
    issues = []
    if capture.race_number != exp["race"]:
        issues.append(f"race {capture.race_number}≠{exp['race']}")
    if exp["track"] is not None:
        got = track_label(tv, capture.track.value) if capture.track else None
        want = (exp["map"], exp["track"])
        if got != want:
            issues.append(f"track {got}≠{want}")
    if exp["car"] is not None:
        got = car_label(cv, capture.car.value) if capture.car else None
        if got != exp["car"]:
            issues.append(f"car {got}≠{exp['car']}")
    if exp["rank"] is not None and capture.rank != exp["rank"]:
        issues.append(f"rank {capture.rank}≠{exp['rank']}")
    if capture.game_language != exp["lang"]:
        issues.append(f"lang {capture.game_language}≠{exp['lang']}")
    return (not issues), ", ".join(issues)


def run_extractor(label, extractor, tv, cv):
    print(f"\n### {label}")
    print(f"{'fixture':<34} {'calls':>6} {'time,s':>8}  result")
    tot_calls = tot_time = 0.0
    for fixture, exp in EXPECTED.items():
        path = FIXTURES / fixture
        if not path.exists():
            print(f"{fixture:<34} {'—':>6} {'—':>8}  немає фікстури")
            continue
        img = cv2.imread(str(path))
        with OcrCounter() as c:
            t0 = time.perf_counter()
            caps = extractor.extract(img)
            dt = time.perf_counter() - t0
        tot_calls += c.count
        tot_time += dt
        cap = caps[0] if caps else None
        ok, msg = check(cap, exp, tv, cv)
        verdict = "OK" if ok else f"FAIL: {msg or 'порожньо'}"
        print(f"{fixture:<34} {c.count:>6} {dt:>8.2f}  {verdict}")
    print(f"{'РАЗОМ':<34} {tot_calls:>6.0f} {tot_time:>8.2f}")
    return tot_calls, tot_time


# --- Header-екрани: race_result і challenge_complete (multi-capture) ---------
# Очікування як {race_number: (car_name, time, rank)}.
RACE_RESULT_EXPECTED = {
    "race_result_ru_1_won.png": {1: ("Bugatti Chiron", 23229, 5130)},
    "race_result_ru_2_won.png": {2: ("Vanda Electrics Dendrobium", 21965, 4099)},
    "race_result_ru_3_won.png": {3: ("Koenigsegg CCXR", 22749, 4998)},
}
COMPLETE_EXPECTED = {
    "challenge_complete_ru.png": {
        1: ("Bugatti Chiron", 23229, None),
        2: ("Vanda Electrics Dendrobium", 21965, None),
        3: ("Koenigsegg CCXR", 22749, None),
    },
}


def check_header(caps, exp, cv) -> tuple[bool, str]:
    by_race = {c.race_number: c for c in caps}
    issues = []
    for race, (car, time, rank) in exp.items():
        if race not in by_race:
            issues.append(f"гонка {race} відсутня")
            continue
        c = by_race[race]
        got_car = car_label(cv, c.car.value) if c.car else None
        if got_car != car:
            issues.append(f"r{race} car {got_car}≠{car}")
        if c.time != time:
            issues.append(f"r{race} time {c.time}≠{time}")
        if rank is not None and c.rank != rank:
            issues.append(f"r{race} rank {c.rank}≠{rank}")
    return (not issues), ", ".join(issues)


def run_header(label, extractor, cv, expected):
    print(f"\n### {label}")
    print(f"{'fixture':<34} {'calls':>6} {'time,s':>8}  result")
    tot_calls = tot_time = 0.0
    for fixture, exp in expected.items():
        path = FIXTURES / fixture
        if not path.exists():
            print(f"{fixture:<34} {'—':>6} {'—':>8}  немає фікстури")
            continue
        img = cv2.imread(str(path))
        with OcrCounter() as c:
            t0 = time.perf_counter()
            caps = extractor.extract(img)
            dt = time.perf_counter() - t0
        tot_calls += c.count
        tot_time += dt
        ok, msg = check_header(caps, exp, cv)
        verdict = "OK" if ok else f"FAIL: {msg or 'порожньо'}"
        print(f"{fixture:<34} {c.count:>6} {dt:>8.2f}  {verdict}")
    print(f"{'РАЗОМ':<34} {tot_calls:>6.0f} {tot_time:>8.2f}")
    return tot_calls, tot_time


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ocr.configure_tesseract()
    if not ocr.is_available():
        raise SystemExit("tesseract недоступний")
    track_resolver, car_matcher, tv, cv = build_resolvers()

    print("\n========== ЕКРАН CAR SELECTION (ВЫБОР АВТО) ==========")
    current = ChallengeAccordionExtractor(track_resolver, car_matcher)
    fast = CarSelectionFastExtractor(track_resolver, car_matcher)
    a_calls, a_time = run_extractor("ПОТОЧНИЙ ChallengeAccordionExtractor", current, tv, cv)
    af_calls, af_time = run_extractor("ШВИДКИЙ CarSelectionFastExtractor (C6+B2)", fast, tv, cv)

    print("\n========== ЕКРАН RACE RESULT ==========")
    rr_calls, rr_time = run_header("ПОТОЧНИЙ RaceResultExtractor",
                                   RaceResultExtractor(car_matcher), cv, RACE_RESULT_EXPECTED)
    rrf_calls, rrf_time = run_header("ШВИДКИЙ RaceResultFastExtractor (B2/B3/B4)",
                                     RaceResultFastExtractor(car_matcher), cv, RACE_RESULT_EXPECTED)

    print("\n========== ЕКРАН CHALLENGE COMPLETE ==========")
    cc_calls, cc_time = run_header("ПОТОЧНИЙ ChallengeCompleteExtractor",
                                   ChallengeCompleteExtractor(car_matcher), cv, COMPLETE_EXPECTED)
    ccf_calls, ccf_time = run_header("ШВИДКИЙ ChallengeCompleteFastExtractor (B2-B5)",
                                     ChallengeCompleteFastExtractor(car_matcher), cv, COMPLETE_EXPECTED)

    def line(name, c0, c1, t0, t1):
        print(f"{name:<22} {c0:>5.0f}→{c1:<5.0f} ({c0/max(c1,1):>4.1f}×)   "
              f"{t0:>5.1f}s→{t1:<5.1f}s ({t0/max(t1,1e-9):>4.1f}×)")

    print("\n### ПІДСУМОК (виклики та час, поточний → швидкий)")
    line("Car selection", a_calls, af_calls, a_time, af_time)
    line("Race result", rr_calls, rrf_calls, rr_time, rrf_time)
    line("Challenge complete", cc_calls, ccf_calls, cc_time, ccf_time)
    tot0, tot1 = a_calls + rr_calls + cc_calls, af_calls + rrf_calls + ccf_calls
    tt0, tt1 = a_time + rr_time + cc_time, af_time + rrf_time + ccf_time
    line("РАЗОМ", tot0, tot1, tt0, tt1)


if __name__ == "__main__":
    main()
