"""Калібрування ROI: малює регіони поверх скріншота і друкує OCR-результати.

Використання (з кореня проєкту):
  .\\.venv\\Scripts\\python.exe -m scripts.debug_recognition <скріншот.png> [--variant before|after] [--panel N] [--grid]
"""
import argparse
import sys

import cv2

from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.regions import (
    ACCORDION_AFTER_PANELS, ACCORDION_BEFORE_PANELS, ACCORDION_HEADER,
    AFTER_PLAYER_CAR, AFTER_PLAYER_RANK, AFTER_PLAYER_TIME, AFTER_TRACK_NAME,
    BEFORE_TRACK_NAME,
)

VARIANTS = {
    "before": {
        "panels": ACCORDION_BEFORE_PANELS,
        "subs": {
            "header": ACCORDION_HEADER,
            "track": BEFORE_TRACK_NAME,
        },
    },
    "after": {
        "panels": ACCORDION_AFTER_PANELS,
        "subs": {
            "header": ACCORDION_HEADER,
            "track": AFTER_TRACK_NAME,
            "player_car": AFTER_PLAYER_CAR,
            "player_rank": AFTER_PLAYER_RANK,
            "player_time": AFTER_PLAYER_TIME,
        },
    },
}

OCR_READERS = {
    "header": lambda img: ocr.read_text(img, "RACE12345"),
    "track": ocr.read_name,
    "player_car": ocr.read_name,
    "player_rank": ocr.read_rank,
    "player_time": ocr.read_time,
}


def draw_rect(img, rel_rect, label, color):
    x, y, w, h = rel_rect.to_abs(img.shape[1], img.shape[0])
    cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
    cv2.putText(img, label, (x, max(y - 4, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)


def draw_grid(img, step=0.05):
    h, w = img.shape[:2]
    for i in range(1, int(1 / step)):
        x, y = int(i * step * w), int(i * step * h)
        cv2.line(img, (x, 0), (x, h), (80, 80, 80), 1)
        cv2.line(img, (0, y), (w, y), (80, 80, 80), 1)
        cv2.putText(img, f"{i * step:.2f}", (x + 2, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1)
        cv2.putText(img, f"{i * step:.2f}", (2, y + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("--variant", choices=("before", "after"), default="before",
                        help="який набір регіонів малювати")
    parser.add_argument("--panel", type=int, default=1, choices=range(1, 6),
                        help="панель (1..5), для якої деталізувати суброгіони")
    parser.add_argument("--grid", action="store_true", help="малювати сітку координат")
    args = parser.parse_args()

    ocr.configure_tesseract()
    img = cv2.imread(args.image)
    if img is None:
        raise SystemExit(f"Не вдалося прочитати {args.image}")
    annotated = img.copy()

    if args.grid:
        draw_grid(annotated)

    variant = VARIANTS[args.variant]
    for i, panel in enumerate(variant["panels"]):
        draw_rect(annotated, panel, f"panel_{i + 1}", (0, 255, 0))
        header_text = ocr.read_text(panel.sub(ACCORDION_HEADER).crop(img), "RACE12345")
        print(f"panel_{i + 1} header OCR: {header_text!r}")

    panel = variant["panels"][args.panel - 1]
    for name, sub in variant["subs"].items():
        draw_rect(annotated, panel.sub(sub), name, (0, 200, 255))
        print(f"panel_{args.panel}/{name}: {OCR_READERS[name](panel.sub(sub).crop(img))!r}")

    out_path = args.image.rsplit(".", 1)[0] + "_annotated.png"
    cv2.imwrite(out_path, annotated)
    print(f"Збережено {out_path}")


if __name__ == "__main__":
    main()
