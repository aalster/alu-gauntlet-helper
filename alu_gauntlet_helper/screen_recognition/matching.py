import re

from rapidfuzz import fuzz, process

from alu_gauntlet_helper.models import FieldGuess

# Лишаємо латиницю, кирилицю й цифри; .upper() нормалізує регістр обох абеток.
_NORMALIZE_RE = re.compile(r"[^A-ZА-ЯЁ0-9]")


def normalize(text: str) -> str:
    return _NORMALIZE_RE.sub("", text.upper())


class VocabularyMatcher:
    """Fuzzy-зіставлення OCR-тексту з відомими назвами (порівняння без пробілів)."""

    def __init__(self, vocab: list[tuple[int, str]], threshold: float = 75.0):
        self.threshold = threshold
        # один id може мати кілька синонімів — дедуплікація на виході
        self._ids = [item_id for item_id, _ in vocab]
        self._choices = {i: normalize(name) for i, (_, name) in enumerate(vocab)}

    def match(self, text: str, limit: int = 3) -> FieldGuess | None:
        query = normalize(text)
        if not query:
            return None

        raw = process.extract(query, self._choices, scorer=fuzz.ratio,
                              score_cutoff=self.threshold, limit=None)
        best_by_id: dict[int, float] = {}
        for _choice, score, key in raw:
            item_id = self._ids[key]
            if score > best_by_id.get(item_id, 0):
                best_by_id[item_id] = score

        if not best_by_id:
            return None

        candidates = sorted(best_by_id.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        candidates = [(item_id, score / 100) for item_id, score in candidates]
        return FieldGuess(value=candidates[0][0], score=candidates[0][1], candidates=candidates)


class TrackResolver:
    """Розпізнає трек з центрального блоку панелі: статична назва карти +
    marquee-фрагмент назви треку. Фрагмент будь-якої фази прокрутки —
    підрядок подвоєної назви треку."""

    # рядок вважається частиною назви карти, якщо так схожий на її фрагмент
    _MAP_LINE_CUTOFF = 85.0
    # коротший фрагмент — шум, а не назва треку
    _MIN_FRAGMENT_LEN = 4

    # NOTE: _best_map compares on the 0..100 rapidfuzz scale (threshold is stored
    # as 0..100 and passed directly to rapidfuzz); resolve() divides scores by 100
    # to work on the 0..1 scale used by FieldGuess.
    _EXACT_MATCH_SCORE = 0.95
    _SINGLE_TRACK_SCORE = 0.85
    _AMBIGUITY_CAP = 0.60
    _AMBIGUITY_WINDOW = 0.05

    def __init__(self, track_views, threshold: float = 75.0):
        self.threshold = threshold
        # normalized map name -> list[(track_id, normalized track name)].
        # Індексуємо і англ., і рос. назву карти; під кожним ключем — назва треку
        # тією ж мовою (на RU-екрані і карта, і трек російською). Мова визначається
        # автоматично з того, який ключ карти збігся з OCR-текстом.
        self._maps: dict[str, list[tuple[int, str]]] = {}
        for t in track_views:
            map_ru = getattr(t, "map_name_ru", "")
            name_ru = getattr(t, "name_ru", "")
            variants = [(t.map_name, t.name)]
            if map_ru:
                # трек без перекладу → у грі під рос. картою лишається англ. назва
                variants.append((map_ru, name_ru or t.name))
            for map_name, track_name in variants:
                norm_map = normalize(map_name)
                if not norm_map:
                    continue
                self._maps.setdefault(norm_map, []).append((t.id, normalize(track_name)))
        self._fallback = build_track_matcher(track_views)

    def _best_map(self, norm_text: str) -> str | None:
        # Guard against short OCR noise: partial_ratio aligns the shorter string
        # inside the longer, so 2-3 chars like "NO" score 100 against "NORWAY".
        if len(norm_text) < self._MIN_FRAGMENT_LEN:
            return None
        # На рівному скорі перемагає ДОВША назва карти. Коли назва треку містить
        # назву іншої карти (трек "Paris of the East" на карті Shanghai), і
        # "PARIS", і "SHANGHAI" дають partial_ratio=100 як підрядки тексту; за
        # строгого ">" перемогла б перша за порядком (карти в БД алфавітні —
        # Paris перед Shanghai), даючи хибну карту. Справжня карта присутня в
        # тексті повністю й довша за випадковий короткий збіг.
        best_map, best_key = None, (0.0, 0)
        for norm_map in self._maps:
            key = (fuzz.partial_ratio(norm_map, norm_text), len(norm_map))
            if key > best_key:
                best_map, best_key = norm_map, key
        return best_map if best_key[0] >= self.threshold else None

    @staticmethod
    def _strip_map(lines: list[str], norm_map: str) -> str:
        """Вирізає з рядків частини, що збігаються з назвою карти; решта —
        marquee-фрагмент назви треку. Працює і коли карта+трек в одному рядку."""
        remainder = []
        for line in lines:
            norm_line = normalize(line)
            if not norm_line:
                continue
            al = fuzz.partial_ratio_alignment(
                norm_map, norm_line, score_cutoff=TrackResolver._MAP_LINE_CUTOFF)
            if al is not None:
                norm_line = norm_line[:al.dest_start] + norm_line[al.dest_end:]
            remainder.append(norm_line)
        return "".join(remainder)

    def resolve(self, center_text: str) -> FieldGuess | None:
        norm_text = normalize(center_text)
        if not norm_text:
            return None

        norm_map = self._best_map(norm_text)
        if norm_map is None:
            # карту не видно — стара поведінка: глобальний fuzzy-матчинг
            return self._fallback.match(center_text)

        tracks = self._maps[norm_map]
        fragment = self._strip_map(center_text.splitlines(), norm_map)

        if len(fragment) < self._MIN_FRAGMENT_LEN:
            if len(tracks) == 1:
                # карта з єдиним треком визначає його сама по собі
                track_id = tracks[0][0]
                return FieldGuess(value=track_id, score=self._SINGLE_TRACK_SCORE,
                                  candidates=[(track_id, self._SINGLE_TRACK_SCORE)])
            return None  # карти замало: наступний кадр добере фрагмент

        scored = []
        for track_id, norm_name in tracks:
            doubled = norm_name * 2  # будь-яка фаза прокрутки — підрядок подвоєної назви
            if fragment in doubled:
                score = self._EXACT_MATCH_SCORE
            else:
                score = fuzz.partial_ratio(fragment, doubled) / 100
            scored.append((track_id, score))
        scored.sort(key=lambda kv: kv[1], reverse=True)

        best_id, best_score = scored[0]
        if best_score < self.threshold / 100:
            if len(tracks) == 1:
                return FieldGuess(value=best_id, score=self._SINGLE_TRACK_SCORE,
                                  candidates=[(best_id, self._SINGLE_TRACK_SCORE)])
            return None
        if len(scored) > 1 and best_score - scored[1][1] <= self._AMBIGUITY_WINDOW:
            # неоднозначність: повертаємо, але з низьким скором — рев'ю підсвітить
            best_score = min(best_score, self._AMBIGUITY_CAP)
        return FieldGuess(value=best_id, score=best_score, candidates=scored)


def build_track_matcher(track_views) -> VocabularyMatcher:
    """track_views: list[TrackView]. Синоніми: «назва треку» і «карта + трек»,
    англ. і рос. (один id, дедуплікація на виході VocabularyMatcher)."""
    vocab = []
    for t in track_views:
        vocab.append((t.id, t.name))
        vocab.append((t.id, f"{t.map_name} {t.name}"))
        name_ru = getattr(t, "name_ru", "")
        if name_ru:
            map_ru = getattr(t, "map_name_ru", "") or t.map_name
            vocab.append((t.id, name_ru))
            vocab.append((t.id, f"{map_ru} {name_ru}"))
    return VocabularyMatcher(vocab)


def build_car_matcher(cars) -> VocabularyMatcher:
    """cars: list[Car]."""
    return VocabularyMatcher([(c.id, c.name) for c in cars])
