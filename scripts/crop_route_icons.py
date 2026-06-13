"""Готує іконки маршрутів: обрізає картку, прибирає індикатор тривалості, центрує на квадраті.

Конвеєр для кожного файлу:
  1. Обрізка по темній картці — прибирає білі поля й підпис із назвою (найбільша зв'язна
     non-white область).
  2. Видалення індикатора тривалості («30''» з дужкою в правому нижньому куті) — заливка
     місця кольором фону. Якщо маршрут налазить на індикатор, безпечно прибрати його не
     можна → файл лишається незмінним і потрапляє у список на ручну обробку.
  3. Центрування контенту (самого маршруту) на квадратному полотні 1:1 з невеликими полями.

Скрипт ідемпотентний: повторний запуск на вже обробленому файлі нічого не змінює (картка
без полів, індикатора нема, контент уже центрований).

Використання (з кореня проєкту):
  # обробити всі іконки на місці (типово resources/icons/tracks/routes)
  .\\.venv\\Scripts\\python.exe -m scripts.crop_route_icons

  # окремі файли або інша тека
  .\\.venv\\Scripts\\python.exe -m scripts.crop_route_icons "resources/icons/tracks/routes/The Caribbean - Hell Vale.png"

  # прев'ю в окрему теку, не чіпаючи оригінали
  .\\.venv\\Scripts\\python.exe -m scripts.crop_route_icons --out _preview

  # лише показати, що буде зроблено
  .\\.venv\\Scripts\\python.exe -m scripts.crop_route_icons --dry-run

Код виходу: 1, якщо хоч один файл пропущено через перекриття індикатора маршрутом.
"""
import argparse
import os
import sys

import cv2
import numpy as np

DEFAULT_DIR = "resources/icons/tracks/routes"
WHITE_THRESHOLD = 230   # яскравіше за це — біле тло/футер
CONTENT_DIST = 25       # відхилення від фону, щоб вважати піксель контентом (маршрутом)
MARGIN_FRAC = 0.05      # поле навколо контенту на квадраті, частка від його більшої сторони


class OverlapError(Exception):
    """Маршрут перекриває індикатор тривалості — безпечно прибрати його не можна."""


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


def background_color(img):
    """Рівний колір фону картки (BGR) за медіаною фонових пікселів."""
    rgb = img[:, :, ::-1].astype(int)
    corner = np.median(rgb[0:15, 0:15].reshape(-1, 3), axis=0)
    dist = np.abs(rgb - corner).sum(axis=2)
    bg = rgb[dist < 12]
    col = np.median(bg, axis=0) if len(bg) > 100 else corner
    return col[::-1].astype(np.uint8)  # -> BGR


def card_bbox(img, white_threshold: int = WHITE_THRESHOLD):
    """Bounding box (x, y, w, h) найбільшої зв'язної темної області або None."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mask = (gray < white_threshold).astype(np.uint8)
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if count <= 1:
        return None
    idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))  # пропускаємо label 0 (тло)
    s = stats[idx]
    return (int(s[cv2.CC_STAT_LEFT]), int(s[cv2.CC_STAT_TOP]),
            int(s[cv2.CC_STAT_WIDTH]), int(s[cv2.CC_STAT_HEIGHT]))


def crop_to_card(img):
    box = card_bbox(img)
    if box is None:
        return img
    x, y, w, h = box
    return img[y:y + h, x:x + w]


def indicator_box(img, pad: int = 6):
    """Bounding box (x0, y0, x1, y1) індикатора тривалості в правому нижньому куті, або None.

    Дужка індикатора — єдиний сірий (низька насиченість) елемент; маршрут лише фіолетовий
    або білий. Шукаємо сірі зв'язні компоненти, чиї центроїди лежать у правому нижньому куті.
    """
    h, w = img.shape[:2]
    rgb = img[:, :, ::-1].astype(int)
    bg = np.median(rgb[0:15, 0:15].reshape(-1, 3), axis=0)
    sat = rgb.max(axis=2) - rgb.min(axis=2)
    bright = rgb.max(axis=2)
    dist = np.abs(rgb - bg).sum(axis=2)
    gray = ((sat < 32) & (bright > 80) & (bright < 200) & (dist > 35)).astype(np.uint8)

    count, _, stats, cent = cv2.connectedComponentsWithStats(gray, connectivity=8)
    box = None
    for i in range(1, count):
        cx, cy = cent[i]
        if cx > 0.78 * w and cy > 0.78 * h and stats[i, cv2.CC_STAT_AREA] > 60:
            x, y = stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP]
            x1, y1 = x + stats[i, cv2.CC_STAT_WIDTH], y + stats[i, cv2.CC_STAT_HEIGHT]
            b = [int(x), int(y), int(x1), int(y1)]
            box = b if box is None else [min(box[0], b[0]), min(box[1], b[1]),
                                         max(box[2], b[2]), max(box[3], b[3])]
    if box is None:
        return None
    # справжня дужка індикатора велика (~125x103); дрібні сірі гліфи (стрілка напрямку »)
    # — не індикатор
    if box[2] - box[0] < 70 or box[3] - box[1] < 60:
        return None
    return (max(0, box[0] - pad), max(0, box[1] - pad),
            min(w, box[2] + pad), min(h, box[3] + pad))


def route_overlaps_indicator(img, box) -> bool:
    """True, якщо маршрут (фіолетова або біла лінія) заходить у прямокутник індикатора."""
    h, w = img.shape[:2]
    x0, y0, x1, y1 = box
    rgb = img[:, :, ::-1].astype(int)
    sat = rgb.max(axis=2) - rgb.min(axis=2)
    bright = rgb.max(axis=2)

    # фіолетова лінія маршруту = насичені пікселі всередині рамки
    purple = (sat > 55) & (bright > 70)
    if int(purple[y0:y1, x0:x1].sum()) > 40:
        return True

    # біла лінія маршруту = білий компонент, що перетинає межу рамки
    # (цифри «30''» і гліф точок повністю всередині, тож межі не перетинають)
    white = ((bright > 200) & (sat < 45)).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(white, connectivity=8)
    inside = set(np.unique(labels[y0:y1, x0:x1])) - {0}
    ex = 12
    ex0, ey0, ex1, ey1 = max(0, x0 - ex), max(0, y0 - ex), min(w, x1 + ex), min(h, y1 + ex)
    for lab in inside:
        bx, by = stats[lab, cv2.CC_STAT_LEFT], stats[lab, cv2.CC_STAT_TOP]
        bx1, by1 = bx + stats[lab, cv2.CC_STAT_WIDTH], by + stats[lab, cv2.CC_STAT_HEIGHT]
        if bx < ex0 or by < ey0 or bx1 > ex1 or by1 > ey1:
            return True
    return False


def remove_indicator(img):
    """Заливає індикатор тривалості кольором фону. Кидає OverlapError, якщо маршрут налазить."""
    box = indicator_box(img)
    if box is None:
        return img
    if route_overlaps_indicator(img, box):
        raise OverlapError()
    x0, y0, x1, y1 = box
    img = img.copy()
    img[y0:y1, x0:x1] = background_color(img)
    return img


def center_square(img, margin_frac: float = MARGIN_FRAC):
    """Центрує контент (маршрут) на квадратному полотні 1:1 з полями навколо."""
    bg = background_color(img)
    rgb = img[:, :, ::-1].astype(int)
    dist = np.abs(rgb - bg[::-1].astype(int)).sum(axis=2)
    ys, xs = np.where(dist > CONTENT_DIST)
    if len(xs) == 0:
        return img

    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    cw, ch = x1 - x0, y1 - y0
    side = max(cw, ch)
    margin = round(side * margin_frac)
    canvas = side + 2 * margin

    out = np.empty((canvas, canvas, 3), dtype=np.uint8)
    out[:] = bg
    ox, oy = (canvas - cw) // 2, (canvas - ch) // 2
    out[oy:oy + ch, ox:ox + cw] = img[y0:y1, x0:x1]
    return out


def process(img, margin_frac: float = MARGIN_FRAC):
    """Повний конвеєр. Кидає OverlapError, якщо індикатор не можна безпечно прибрати."""
    img = crop_to_card(img)
    img = remove_indicator(img)
    img = center_square(img, margin_frac)
    return img


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
    parser = argparse.ArgumentParser(description="Готує іконки маршрутів (обрізка, індикатор, квадрат 1:1).")
    parser.add_argument("paths", nargs="*", default=[DEFAULT_DIR],
                        help=f"файли або теки з .png (типово: {DEFAULT_DIR})")
    parser.add_argument("--out", metavar="DIR",
                        help="зберігати в цю теку замість перезапису оригіналів")
    parser.add_argument("--margin", type=float, default=MARGIN_FRAC,
                        help=f"поле навколо контенту, частка більшої сторони (типово {MARGIN_FRAC})")
    parser.add_argument("--dry-run", action="store_true", help="лише показати, що буде зроблено")
    args = parser.parse_args()

    if args.out:
        os.makedirs(args.out, exist_ok=True)

    files = collect_files(args.paths)
    done = 0
    overlaps = []
    for path in files:
        img = imread_unicode(path)
        if img is None:
            print(f"Не вдалося прочитати: {path}")
            continue

        name = os.path.basename(path)
        try:
            out = process(img, args.margin)
        except OverlapError:
            overlaps.append(name)
            print(f"{name}: ПРОПУЩЕНО — маршрут перекриває індикатор, оброби вручну")
            continue

        print(f"{name}: {img.shape[1]}x{img.shape[0]} -> {out.shape[1]}x{out.shape[0]}")
        if args.dry_run:
            done += 1
            continue

        dst = os.path.join(args.out, name) if args.out else path
        if imwrite_unicode(dst, out):
            done += 1
        else:
            print(f"Не вдалося записати: {dst}")

    print(f"\nГотово: {done}/{len(files)} файлів")
    if overlaps:
        print(f"На ручну обробку ({len(overlaps)}): {', '.join(overlaps)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
