"""Готує превʼю іконок маршрутів: квадратний кроп навколо білої лінії маршруту.

Повна іконка (`resources/icons/tracks/routes`) обрізана по всьому контенту картки —
біла лінія маршруту + фіолетова «місцевість» навколо. Часто маршрут витягнутий по
ширині й по висоті займає лише ~20%, тож на квадратній мініатюрі виглядає дрібним.

Цей скрипт вирізає квадрат, центрований на bbox **білих** пікселів (самої лінії
маршруту), з невеликим паддингом. Зображення не змінюється: у паддинг можуть потрапити
фіолетові дороги поряд — це нормально. Результат лягає в `resources/icons/tracks/routes_preview`
з тим самим імʼям файлу.

Використання (з кореня проєкту):
  # усі іконки -> routes_preview
  .\\.venv\\Scripts\\python.exe -m scripts.crop_route_preview

  # окремі файли
  .\\.venv\\Scripts\\python.exe -m scripts.crop_route_preview "resources/icons/tracks/routes/The Caribbean - Hell Vale.png"

  # інша тека виводу / тільки показати
  .\\.venv\\Scripts\\python.exe -m scripts.crop_route_preview --out _preview
  .\\.venv\\Scripts\\python.exe -m scripts.crop_route_preview --dry-run

Файли без білих пікселів пропускаються (превʼю не створюється — список покаже повну іконку).
"""
import argparse
import os
import sys

import cv2
import numpy as np

SRC_DIR = "resources/icons/tracks/routes"
DEFAULT_OUT = "resources/icons/tracks/routes_preview"
WHITE_BRIGHT = 200      # яскравіше за це + низька насиченість — біла лінія маршруту
WHITE_SAT = 45
MARGIN_FRAC = 0.08      # паддинг навколо білого bbox, частка більшої сторони


def imread_unicode(path: str):
    """cv2.imread, стійкий до не-ASCII шляхів на Windows."""
    data = np.fromfile(path, dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def imwrite_unicode(path: str, img) -> bool:
    ext = os.path.splitext(path)[1] or ".png"
    ok, buf = cv2.imencode(ext, img)
    if ok:
        buf.tofile(path)
    return ok


def white_bbox(img):
    """Bounding box (x0, y0, x1, y1) білих пікселів (лінії маршруту) або None."""
    bright = img.max(axis=2)
    sat = img.max(axis=2).astype(int) - img.min(axis=2)
    white = (bright > WHITE_BRIGHT) & (sat < WHITE_SAT)
    ys, xs = np.where(white)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def preview_crop(img, margin_frac: float = MARGIN_FRAC):
    """Квадратний кроп оригіналу навколо білого маршруту. None, якщо білого нема."""
    box = white_bbox(img)
    if box is None:
        return None
    h, w = img.shape[:2]
    x0, y0, x1, y1 = box
    side = max(x1 - x0, y1 - y0)
    margin = round(side * margin_frac)
    sq = min(side + 2 * margin, w, h)  # квадрат не може бути більшим за зображення

    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    sx = min(max(cx - sq // 2, 0), w - sq)  # зсув центру всередину при виході за межі
    sy = min(max(cy - sq // 2, 0), h - sq)
    return img[sy:sy + sq, sx:sx + sq]


def collect_files(paths: list[str]) -> list[str]:
    result = []
    for p in paths:
        if os.path.isdir(p):
            result += [os.path.join(p, f) for f in sorted(os.listdir(p)) if f.lower().endswith(".png")]
        elif os.path.isfile(p):
            result.append(p)
        else:
            print(f"Пропущено (не знайдено): {p}")
    return result


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Готує превʼю іконок маршрутів (квадратний кроп білої лінії).")
    parser.add_argument("paths", nargs="*", default=[SRC_DIR],
                        help=f"файли або теки з .png (типово: {SRC_DIR})")
    parser.add_argument("--out", metavar="DIR", default=DEFAULT_OUT,
                        help=f"тека виводу (типово: {DEFAULT_OUT})")
    parser.add_argument("--margin", type=float, default=MARGIN_FRAC,
                        help=f"паддинг навколо маршруту, частка більшої сторони (типово {MARGIN_FRAC})")
    parser.add_argument("--dry-run", action="store_true", help="лише показати, що буде зроблено")
    args = parser.parse_args()

    if not args.dry_run:
        os.makedirs(args.out, exist_ok=True)

    files = collect_files(args.paths)
    done = 0
    skipped = []
    for path in files:
        img = imread_unicode(path)
        if img is None:
            print(f"Не вдалося прочитати: {path}")
            continue

        name = os.path.basename(path)
        out = preview_crop(img, args.margin)
        if out is None:
            skipped.append(name)
            print(f"{name}: ПРОПУЩЕНО — немає білих пікселів маршруту")
            continue

        print(f"{name}: {img.shape[1]}x{img.shape[0]} -> {out.shape[1]}x{out.shape[0]}")
        if args.dry_run:
            done += 1
            continue

        dst = os.path.join(args.out, name)
        if imwrite_unicode(dst, out):
            done += 1
        else:
            print(f"Не вдалося записати: {dst}")

    print(f"\nГотово: {done}/{len(files)} файлів")
    if skipped:
        print(f"Без превʼю ({len(skipped)}): {', '.join(skipped)}")


if __name__ == "__main__":
    main()
