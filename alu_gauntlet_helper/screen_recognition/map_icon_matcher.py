"""Матчинг іконки карти на панелі скаут-екрана з еталонами resources/icons/maps.

Еталони — 180×180 RGBA: білий гліф бейджа з альфою. На панелі іконка — той
самий білий гліф на фіолетовому градієнті, розмір ≈ 55–85% висоти зони, позиція
трохи плаває, тому шаблон проганяється в кількох масштабах, а зсув знаходить
сам matchTemplate. Форми бейджів різні (гексагон/квадрат/пентагон/щит/коло) —
TM_CCOEFF_NORMED дає правильній карті реально 0.55–0.94 (виміряно по всіх 15
панелях трьох фікстур opponent_tracks/opponent_times_1/opponent_times_2), а
мінімальний марджин до другого кандидата — лише ~0.03 (2 з 15 панелей), тож
поріг MIN_SCORE=0.5, а неоднозначні збіги гасяться AMBIGUITY-гардом нижче,
а не завищеним порогом."""
from typing import Iterable

import cv2
import numpy as np

from alu_gauntlet_helper.models import FieldGuess

MIN_SCORE = 0.5      # нижче — вважаємо, що іконки в кропі немає
SCALES = (0.55, 0.65, 0.75, 0.85)  # висота шаблону в частках висоти кропу
MIN_TEMPLATE_PX = 20  # дрібніший ресайз втрачає гліф — масштаб пропускається
CANDIDATE_LIMIT = 3
# Неоднозначність — як у TrackResolver._AMBIGUITY_*: близькі перший і другий
# кандидати гасимо зниженим скором, а не None (правильні матчі теж бувають
# із малим марджином — рішення лишаємо споживачам за score).
AMBIGUITY_WINDOW = 0.05
AMBIGUITY_CAP = 0.6


class MapIconMatcher:
    """Зіставляє кроп зони іконки з еталонами всіх карт; будується один раз
    на захоплення (як словники матчерів у _build_engine)."""

    def __init__(self, maps: Iterable):
        # map_id -> grayscale-композит гліфа на чорному (альфа = маска яскравості)
        self._templates: dict[int, np.ndarray] = {}
        self._names: dict[int, str] = {}
        for m in maps:
            icon = getattr(m, "icon", "")
            if not icon:
                continue
            try:
                # cv2.imread мовчки падає на не-ASCII шляхах у Windows, тому
                # imdecode (конвенція репо, як у capture_controller.recognize_file)
                img = cv2.imdecode(np.fromfile(icon, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            except OSError:
                continue  # відсутній файл — пропускаємо еталон
            if img is None or img.ndim != 3 or img.shape[2] != 4:
                continue
            alpha = img[..., 3].astype(np.float32) / 255.0
            gray = cv2.cvtColor(img[..., :3], cv2.COLOR_BGR2GRAY).astype(np.float32)
            self._templates[m.id] = (gray * alpha).astype(np.uint8)
            self._names[m.id] = getattr(m, "name", "")

    def match(self, roi_bgr: np.ndarray) -> FieldGuess | None:
        if not self._templates or roi_bgr.size == 0:
            return None
        roi = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
        rh, rw = roi.shape
        scores: dict[int, float] = {}
        for map_id, template in self._templates.items():
            best = 0.0
            for scale in SCALES:
                side = int(rh * scale)
                if side < MIN_TEMPLATE_PX or side > min(rh, rw):
                    continue
                resized = cv2.resize(template, (side, side), interpolation=cv2.INTER_AREA)
                result = cv2.matchTemplate(roi, resized, cv2.TM_CCOEFF_NORMED)
                best = max(best, float(result.max()))
            scores[map_id] = best
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:CANDIDATE_LIMIT]
        if not ranked or ranked[0][1] < MIN_SCORE:
            return None
        score = ranked[0][1]
        if len(ranked) >= 2 and ranked[0][1] - ranked[1][1] < AMBIGUITY_WINDOW:
            # неоднозначність — знижений скор, як у TrackResolver
            score = min(ranked[0][1], AMBIGUITY_CAP)
        return FieldGuess(value=ranked[0][0], score=score, candidates=ranked)

    def name_of(self, map_id: int) -> str:
        """Назва карти за id — для звуження пошуку треку до треків цієї карти."""
        return self._names.get(map_id, "")
