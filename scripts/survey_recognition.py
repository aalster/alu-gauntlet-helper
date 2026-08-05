"""Обстеження розпізнавання на ВСІХ наявних скріншотах (фікстури + captures).

Проганяє бойовий конвеєр (екстрактори в продакшен-порядку, як у
CaptureController._build_engine) по кожному PNG у tests/fixtures/ та
tests/fixtures/captures/, рахує OCR-виклики (всього і кириличні), час,
переможний екстрактор і розпізнані поля зі скорами. Пише markdown-звіт.

Запуск (з кореня, .venv):
  .\\.venv\\Scripts\\python.exe -m scripts.survey_recognition [-o docs/recognition-survey.md]
"""
import argparse
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alu_gauntlet_helper.screen_recognition import ocr  # noqa: E402
from alu_gauntlet_helper.screen_recognition.map_icon_matcher import MapIconMatcher  # noqa: E402
from alu_gauntlet_helper.screen_recognition.screens.before_race import BeforeRaceExtractor  # noqa: E402
from alu_gauntlet_helper.screen_recognition.screens.challenge_accordion import (  # noqa: E402
    ChallengeAccordionExtractor,
)
from alu_gauntlet_helper.screen_recognition.screens.challenge_complete import (  # noqa: E402
    ChallengeCompleteExtractor,
)
from alu_gauntlet_helper.screen_recognition.screens.opponent_scout import OpponentScoutExtractor  # noqa: E402
from alu_gauntlet_helper.screen_recognition.screens.race_result import RaceResultExtractor  # noqa: E402
from tests.recognition_vocab import build_resolvers, car_label, track_label  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
# Скрипт працює без БД (як тести) — іконки карт беремо напряму з ресурсів,
# так само, як matcher() у tests/test_map_icon_matcher.py.
MAP_ICONS = Path(__file__).resolve().parent.parent / "resources" / "icons" / "maps"


def build_map_matcher() -> MapIconMatcher:
    return MapIconMatcher(SimpleNamespace(id=i, icon=str(p), name=p.stem)
                          for i, p in enumerate(sorted(MAP_ICONS.glob("*.png"))))


class OcrCounter:
    """Рахує OCR-виклики через єдину точку ocr._run_ocr, окремо кириличні."""

    def __enter__(self):
        self.count = 0
        self.rus = 0
        self._orig = ocr._run_ocr

        def wrapped(image, lang="eng", psm=7, whitelist=""):
            self.count += 1
            if lang == "rus":
                self.rus += 1
            return self._orig(image, lang=lang, psm=psm, whitelist=whitelist)

        ocr._run_ocr = wrapped
        return self

    def __exit__(self, *exc):
        ocr._run_ocr = self._orig


def fmt_time(ms):
    if ms is None:
        return "—"
    return f"{ms // 60000}:{ms % 60000 // 1000:02d}.{ms % 1000:03d}"


def fmt_guess(guess, label_fn):
    if guess is None:
        return "—"
    return f"{label_fn(guess.value)} ({guess.score:.2f})"


def describe_captures(caps, tv, cv):
    lines = []
    for c in caps:
        track = fmt_guess(c.track, lambda v: " - ".join(track_label(tv, v) or ("?",)))
        car = fmt_guess(c.car, lambda v: car_label(cv, v))
        lines.append(f"  - race={c.race_number} track={track} car={car} "
                     f"rank={c.rank if c.rank is not None else '—'} time={fmt_time(c.time)} lang={c.game_language}")
    return lines


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--out", default="docs/recognition-survey.md")
    args = parser.parse_args()

    ocr.configure_tesseract()
    if not ocr.is_available():
        raise SystemExit("tesseract недоступний")
    track_resolver, car_matcher, tv, cv = build_resolvers()
    map_matcher = build_map_matcher()

    extractors = [
        RaceResultExtractor(car_matcher),
        ChallengeCompleteExtractor(car_matcher),
        BeforeRaceExtractor(track_resolver, car_matcher),
        OpponentScoutExtractor(track_resolver, map_matcher),
        ChallengeAccordionExtractor(track_resolver, car_matcher),
    ]

    images = sorted(FIXTURES.glob("*.png")) + sorted((FIXTURES / "captures").glob("*.png"))
    out_path = Path(__file__).resolve().parent.parent / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    details = []
    for path in images:
        rel = path.relative_to(FIXTURES).as_posix()
        img = cv2.imread(str(path))
        if img is None:
            summary_rows.append((rel, "—", "READ FAIL", 0, 0, 0.0, ""))
            continue
        h, w = img.shape[:2]

        winner = None
        caps = []
        breakdown = []  # (extractor, calls, rus, time, статус)
        total_calls = total_rus = total_time = 0
        for ex in extractors:
            with OcrCounter() as cnt:
                t0 = time.perf_counter()
                try:
                    res = ex.extract(img)
                    status = f"{len(res)} captures" if res else "reject"
                except Exception as e:
                    res = []
                    status = f"ERROR {type(e).__name__}: {e}"
                dt = time.perf_counter() - t0
            breakdown.append((ex.name, cnt.count, cnt.rus, dt, status))
            total_calls += cnt.count
            total_rus += cnt.rus
            total_time += dt
            if res:
                winner = ex.name
                caps = res
                break

        cap_lines = describe_captures(caps, tv, cv)
        summary_rows.append((rel, f"{w}x{h}", winner or "NOT RECOGNIZED",
                             total_calls, total_rus, total_time,
                             "; ".join(l.strip("  - ") for l in cap_lines)))
        detail = [f"## {rel}  ({w}x{h})",
                  f"Переможець: **{winner or 'NOT RECOGNIZED'}** — "
                  f"{total_calls} OCR-викликів ({total_rus} rus), {total_time:.1f}s", ""]
        detail.append("| екстрактор | виклики | rus | час,s | статус |")
        detail.append("|---|---|---|---|---|")
        for name, calls, rus, dt, status in breakdown:
            detail.append(f"| {name} | {calls} | {rus} | {dt:.1f} | {status} |")
        if cap_lines:
            detail.append("")
            detail.append("Захоплення:")
            detail.extend(cap_lines)
        details.append("\n".join(detail))
        print(f"{rel:<50} {winner or 'NOT RECOGNIZED':<18} {total_calls:>4} calls {total_time:>6.1f}s")

        # проміжний запис — щоб звіт був корисним і до завершення повного прогону
        write_report(out_path, summary_rows, details)

    write_report(out_path, summary_rows, details)
    print(f"\nЗвіт: {out_path}")


def write_report(out_path, summary_rows, details):
    lines = ["# Обстеження розпізнавання (всі скріншоти)", "",
             "Бойовий порядок екстракторів: race_result → challenge_complete → "
             "before_race → challenge_accordion.", "",
             "| файл | розмір | екран | виклики | rus | час,s | результат |",
             "|---|---|---|---|---|---|---|"]
    for rel, size, screen, calls, rus, dt, caps in summary_rows:
        dt_s = f"{dt:.1f}" if isinstance(dt, float) else dt
        lines.append(f"| {rel} | {size} | {screen} | {calls} | {rus} | {dt_s} | {caps} |")
    lines.append("")
    lines.extend(details)
    out_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
