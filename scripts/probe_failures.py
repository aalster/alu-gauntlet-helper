"""Точкова діагностика нерозпізнаних captures: що бачить OCR у регіонах якорів.

1. EN race_result: читання RACE_RESULT_HEADER по dy-зсувах, з whitelist і без,
   плюс обрізані варіанти (логотип клубу зліва може ламати psm 7).
2. before_race: частка білого по слотах індикатора + read_bright_digit.

Запуск: .\\.venv\\Scripts\\python.exe -m scripts.probe_failures
"""
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alu_gauntlet_helper.screen_recognition import ocr  # noqa: E402
from alu_gauntlet_helper.screen_recognition.regions import (  # noqa: E402
    BEFORE_RACE_MIN_WHITE_FRAC, BEFORE_RACE_SLOTS, BEFORE_RACE_WHITE_THRESHOLD,
    RACE_RESULT_HEADER, RelRect,
)
from alu_gauntlet_helper.screen_recognition.screens.base import HEADER_DY_OFFSETS  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

RACE_RESULT_FAILS = [
    "captures/capture_1784451941416937700.png",
    "captures/capture_1784538557283999600.png",
    "captures/capture_1784627025726575700.png",
    "captures/capture_1784794715365495300.png",
    "captures/capture_1784799351890838400.png",
    "captures/capture_1784881514278377300.png",
    "captures/capture_1784882769017084400.png",
    "race_result_4_lost.png",       # контроль: розпізнається
    "race_result_ru_1_won.png",     # контроль RU
]

BEFORE_RACE_FAILS = [
    "captures/capture_1785420973341703600.png",
    "captures/capture_1784795086089408800.png",  # контроль: розпізнається (race 3)
]


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ocr.configure_tesseract()
    if not ocr.is_available():
        raise SystemExit("tesseract недоступний")

    print("=== race_result: RACE_RESULT_HEADER, EN whitelist read ===")
    for name in RACE_RESULT_FAILS:
        img = cv2.imread(str(FIXTURES / name))
        print(f"\n--- {name}")
        for dy in HEADER_DY_OFFSETS:
            region = RACE_RESULT_HEADER.shifted(0.0, dy)
            wl = ocr.read_text(region.crop(img), "RACE12345")
            print(f"  dy={dy:+.2f}  whitelist={wl!r}")
        # без whitelist і обрізані варіанти (тільки dy=0)
        raw = ocr.read_text(RACE_RESULT_HEADER.crop(img))
        print(f"  dy=0 raw (без whitelist)     ={raw!r}")
        for trim in (0.15, 0.22, 0.30):
            sub = RACE_RESULT_HEADER.sub(RelRect(trim, 0.0, 1 - trim, 1.0))
            wl = ocr.read_text(sub.crop(img), "RACE12345")
            print(f"  dy=0 trim={trim:.2f} whitelist={wl!r}")

    print("\n=== before_race: слоти індикатора ===")
    for name in BEFORE_RACE_FAILS:
        img = cv2.imread(str(FIXTURES / name))
        print(f"\n--- {name}")
        for i, slot in enumerate(BEFORE_RACE_SLOTS):
            roi = slot.crop(img)
            frac = float((roi.min(axis=2) > BEFORE_RACE_WHITE_THRESHOLD).mean())
            digit = ocr.read_bright_digit(roi) if frac >= BEFORE_RACE_MIN_WHITE_FRAC else None
            print(f"  slot {i + 1}: white_frac={frac:.4f} "
                  f"{'(кандидат)' if frac >= BEFORE_RACE_MIN_WHITE_FRAC else '':<11} digit={digit}")


if __name__ == "__main__":
    main()
