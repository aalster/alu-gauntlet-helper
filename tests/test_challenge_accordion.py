from pathlib import Path
from types import SimpleNamespace

import cv2
import pytest

from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.matching import TrackResolver, VocabularyMatcher
from alu_gauntlet_helper.screen_recognition.screens.challenge_accordion import ChallengeAccordionExtractor

FIXTURES = Path(__file__).parent / "fixtures"
TESSERACT_OK = ocr.configure_tesseract() and ocr.is_available()

# Словники-стаби: реальні назви з гри, які видно на фікстурних скріншотах.
# TrackResolver будується з TrackView-подібних об'єктів (id, name, map_name).
TRACK_SF_RAILROAD = 101
TRACK_NORWAY_FUSION = 102
TRACK_SHANGHAI_ROUNDABOUT = 103
TRACK_US_TWISTER = 104
TRACK_CAIRO_GEZIRA = 105
TRACK_PARIS_NOTRE_DAME = 106
TRACK_SF_CENTER = 107  # другий трек Сан-Франциско: дизамбігуація реально працює
TRACK_SHANGHAI_PARIS_EAST = 108  # назва містить чужу карту "Paris" — перевірка колізії


# Російські треки (для RU-фікстур): name_ru/map_name_ru обовʼязкові — TrackResolver
# індексує карту й треку обома мовами, і саме за рос. ключем карти впізнає RU-екран.
TRACK_NEVADA_BRIDGE = 110
TRACK_OSAKA_NAMBA = 111
TRACK_NY_WALL_STREET = 112
TRACK_SINGAPORE_URBAN = 113
TRACK_SCOTLAND_VALLEY = 114
TRACK_AUCKLAND_SPRINT = 115


def track_view(track_id: int, name: str, map_name: str, name_ru: str = "", map_name_ru: str = ""):
    return SimpleNamespace(id=track_id, name=name, map_name=map_name,
                           name_ru=name_ru, map_name_ru=map_name_ru)


TRACK_VIEWS = [
    track_view(TRACK_SF_RAILROAD, "Railroad Bustle", "San Francisco",
               "Железная Дорога", "Сан-Франциско"),
    track_view(TRACK_SF_CENTER, "Out of the Center", "San Francisco"),
    track_view(TRACK_NORWAY_FUSION, "Future Fusion", "Norway"),
    track_view(TRACK_SHANGHAI_ROUNDABOUT, "Double Roundabout", "Shanghai"),
    track_view(TRACK_SHANGHAI_PARIS_EAST, "Paris of the East", "Shanghai"),
    track_view(TRACK_US_TWISTER, "It's a Twister", "US Midwest"),
    track_view(TRACK_CAIRO_GEZIRA, "Gezira Island", "Cairo"),
    track_view(TRACK_PARIS_NOTRE_DAME, "Notre Dame", "Paris"),
    track_view(TRACK_NEVADA_BRIDGE, "Bridge to Bridge", "Nevada",
               "От Моста К Мосту", "Невада"),
    track_view(TRACK_OSAKA_NAMBA, "Namba Park", "Osaka", "Парк Намба", "Осака"),
    track_view(TRACK_NY_WALL_STREET, "Wall Street Ride", "New York",
               "Поездка По Уолл-Стрит", "Нью-Йорк"),
    track_view(TRACK_SINGAPORE_URBAN, "Urban Rush", "Singapore",
               "Городская Спешка", "Сингапур"),
    track_view(TRACK_SCOTLAND_VALLEY, "Rocky Valley", "Scotland", "Каньон", "Шотландия"),
    track_view(TRACK_AUCKLAND_SPRINT, "Straight Sprint", "Auckland",
               "Спринт По Прямой", "Окленд"),
]

# У словнику авто НАВМИСНО є й суперники з лівого боку панелей (Bugatti Chiron
# на after_1, W Motors Lykan на after_4, Ultima RS на before_5/race1 тощо):
# читання не того боку дало б ХИБНИЙ id і завалило тест.
CAR_ULTIMA_RS = 201
CAR_BUGATTI_CHIRON = 202
CAR_FERRARI_SF90 = 203
CAR_KOENIGSEGG_CCXR = 204
CAR_LYKAN_HYPERSPORT = 205
CAR_RIMAC_NEVERA_TA = 206
CAR_VANDA_DENDROBIUM = 207
CAR_VOCAB = [
    (CAR_ULTIMA_RS, "Ultima RS"),
    (CAR_BUGATTI_CHIRON, "Bugatti Chiron"),
    (CAR_FERRARI_SF90, "Ferrari SF90 Stradale"),
    (CAR_KOENIGSEGG_CCXR, "Koenigsegg CCXR"),
    (CAR_LYKAN_HYPERSPORT, "W Motors Lykan Hypersport"),
    (CAR_RIMAC_NEVERA_TA, "Rimac Nevera Time Attack"),
    (CAR_VANDA_DENDROBIUM, "Vanda Electrics Dendrobium"),
]


def make_extractor():
    return ChallengeAccordionExtractor(TrackResolver(TRACK_VIEWS), VocabularyMatcher(CAR_VOCAB))


def extract_one(fixture: str):
    img = cv2.imread(str(FIXTURES / fixture))
    captures = make_extractor().extract(img)
    assert len(captures) == 1
    return captures[0]


def fixture_guard(fixture: str):
    return pytest.mark.skipif(not (FIXTURES / fixture).exists(), reason="немає фікстури")


# --- AFTER: гонку їхали — дані ГРАВЦЯ з правого боку панелі ------------------

@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@fixture_guard("accordion_after_1.png")
def test_after_1_player_data():
    """Скріншот: RACE 1, WON; зліва суперник BUGATTI CHIRON 5,105, справа гравець
    FERRARI SF90 STRADALE 4,795; TIME TO BEAT 00:19.152, YOUR TIME 00:19.130."""
    c = extract_one("accordion_after_1.png")
    assert c.race_number == 1
    assert c.track and c.track.value == TRACK_SF_RAILROAD
    # Має бути авто ГРАВЦЯ (правий бік), а не суперника (лівий бік)
    assert c.car and c.car.value == CAR_FERRARI_SF90
    assert c.car.value != CAR_BUGATTI_CHIRON
    assert c.rank == 4795  # ранг гравця, не 5105 суперника
    assert c.time == 19130  # YOUR TIME, не 19152 (TIME TO BEAT)
    assert c.panel_image


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@fixture_guard("accordion_after_2.png")
def test_after_2_player_data():
    """Скріншот: RACE 2, WON; обидва боки KOENIGSEGG CCXR 4,998; трек U.S. MIDWEST
    IT'S A TWISTER; TIME TO BEAT 00:26.591, YOUR TIME 00:25.782."""
    c = extract_one("accordion_after_2.png")
    assert c.race_number == 2
    assert c.track and c.track.value == TRACK_US_TWISTER
    assert c.car and c.car.value == CAR_KOENIGSEGG_CCXR
    assert c.rank == 4998
    assert c.time == 25782  # YOUR TIME, не 26591 (TIME TO BEAT)


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@fixture_guard("accordion_after_4.png")
def test_after_4_lost_race_red_time():
    """Скріншот: RACE 4, LOST; зліва суперник W MOTORS LYKAN HYPERSPORT 4,683,
    справа гравець BUGATTI CHIRON 5,130; трек CAIRO GEZIRA ISLAND;
    TIME TO BEAT 00:24.164, YOUR TIME 00:24.182 ЧЕРВОНИМ (програна гонка)."""
    c = extract_one("accordion_after_4.png")
    assert c.race_number == 4
    assert c.track and c.track.value == TRACK_CAIRO_GEZIRA
    assert c.car and c.car.value == CAR_BUGATTI_CHIRON
    assert c.car.value != CAR_LYKAN_HYPERSPORT
    assert c.rank == 5130
    assert c.time == 24182  # червоний час читається через max-канальний фолбек OCR


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@fixture_guard("accordion_after_shanghai_paris_east.png")
def test_after_shanghai_paris_of_the_east_track():
    """Скріншот: RACE 1, WON; зліва суперник MITSUBISHI LANCER EVOLUTION 1,031,
    справа гравець BUGATTI CHIRON 5,130; карта SHANGHAI, трек PARIS OF THE EAST
    (назва на двох рядках і містить чужу карту "Paris"); TIME TO BEAT 00:37.672,
    YOUR TIME 00:26.665. Регресія: карта раніше плуталась із Paris і трек не
    розпізнавався взагалі."""
    c = extract_one("accordion_after_shanghai_paris_east.png")
    assert c.race_number == 1
    assert c.track and c.track.value == TRACK_SHANGHAI_PARIS_EAST
    assert c.car and c.car.value == CAR_BUGATTI_CHIRON
    assert c.rank == 5130
    assert c.time == 26665  # YOUR TIME, не 37672 (TIME TO BEAT)


# --- BEFORE: гонку ще не їхали — лише номер гонки і трек ---------------------
# Дані суперника (його авто і TIME TO BEAT) НЕ повертаються: саме їх раніше
# помилково зберігали як результат гравця.

@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@fixture_guard("accordion_before_1.png")
def test_before_1_no_opponent_data():
    """Скріншот: RACE 1, зліва суперник BUGATTI CHIRON 5,105, TIME TO BEAT
    00:19.152, справа SELECT CAR; трек SAN FRANCISCO RAILROAD BUSTLE."""
    c = extract_one("accordion_before_1.png")
    assert c.race_number == 1
    # Рядок треку — це маркі (рухомий рядок), на цьому кадрі він прокручений
    # до "BUSTLE   RAIL". TrackResolver упізнає карту SAN FRANCISCO, а фрагмент
    # шукає як підрядок ПОДВОЄНОЇ назви треку — тож і мід-скрол кадр дає трек.
    assert c.track and c.track.value == TRACK_SF_RAILROAD
    assert c.car is None
    assert c.rank is None  # не 5105 суперника
    assert c.time is None  # не 19152 (TIME TO BEAT суперника)
    assert c.panel_image


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@fixture_guard("accordion_before_3.png")
def test_before_3_no_opponent_data():
    """Скріншот: RACE 3, зліва суперник RIMAC NEVERA TIME ATTACK 4,835,
    TIME TO BEAT 00:19.736; трек NORWAY FUTURE FUSION."""
    c = extract_one("accordion_before_3.png")
    assert c.race_number == 3
    assert c.track and c.track.value == TRACK_NORWAY_FUSION
    assert c.car is None
    assert c.rank is None
    assert c.time is None


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@fixture_guard("accordion_before_5.png")
def test_before_5_no_opponent_data():
    """Скріншот: RACE 5, зліва суперник ULTIMA RS 4,644, TIME TO BEAT 00:30.847;
    трек SHANGHAI DOUBLE ROUNDABOUT."""
    c = extract_one("accordion_before_5.png")
    assert c.race_number == 5
    assert c.track and c.track.value == TRACK_SHANGHAI_ROUNDABOUT
    assert c.car is None
    assert c.rank is None
    assert c.time is None


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@fixture_guard("accordion_race1.png")
def test_old_fixture_race1_is_before_variant():
    """Стара фікстура (before-варіант, інший челендж): RACE 1, трек PARIS NOTRE
    DAME, суперник ULTIMA RS 4,644, TIME TO BEAT 00:22.797. Семантика ЗМІНЕНА:
    дані суперника більше не витягуються."""
    c = extract_one("accordion_race1.png")
    assert c.race_number == 1
    assert c.track and c.track.value == TRACK_PARIS_NOTRE_DAME
    assert c.car is None
    assert c.rank is None  # раніше тут помилково було 4644 (ранг суперника)
    assert c.time is None  # раніше тут помилково було 22797 (час суперника)


# --- RU: екран "ВЫБОР АВТО" (вибір авто) російською мовою ---------------------
# Той самий лейаут, що й англ. accordion: 5 панелей, одна розгорнута. Назви карт
# і треків кирилицею (авто лишаються англ.). Праворуч — обране авто гравця з
# рангом (час ще None — гонку не їхали). Перевіряє: двомовний якір "ГОНКА N",
# RU-резолв треку, авто англ., і авто-визначення мови гри (game_language == "ru").
# Калібрування дизамбігуації: коли розгорнуто гонку 4 чи 5, згорнуті колонки
# ліворуч стоять на позиціях нижчих індексів — справжню панель обираємо за треком.

@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
@pytest.mark.parametrize("fixture, race, track_id, car_id, rank", [
    ("accordion_ru_1_nevada.png", 1, TRACK_NEVADA_BRIDGE, CAR_BUGATTI_CHIRON, 5130),
    ("accordion_ru_2_osaka.png", 2, TRACK_OSAKA_NAMBA, CAR_VANDA_DENDROBIUM, 4099),
    ("accordion_ru_3_new_york.png", 3, TRACK_NY_WALL_STREET, CAR_KOENIGSEGG_CCXR, 4998),
    ("accordion_ru_4_singapore.png", 4, TRACK_SINGAPORE_URBAN, CAR_RIMAC_NEVERA_TA, 4835),
    ("accordion_ru_5_scotland.png", 5, TRACK_SCOTLAND_VALLEY, CAR_FERRARI_SF90, 4795),
    # Дві нові проблемні фікстури (повільне розпізнавання ~15 с/скрин — див.
    # docs/optimizing-recognition-speed.md). Поточний екстрактор їх ВСЕ Ж бере,
    # але дорого; швидкий шлях — у tests/test_car_selection_fast.py.
    ("car_selection_ru_1_sf.png", 1, TRACK_SF_RAILROAD, CAR_RIMAC_NEVERA_TA, 4835),
    ("car_selection_ru_2_auckland.png", 2, TRACK_AUCKLAND_SPRINT, CAR_FERRARI_SF90, 4795),
])
def test_ru_car_selection(fixture, race, track_id, car_id, rank):
    if not (FIXTURES / fixture).exists():
        pytest.skip("немає фікстури")
    c = extract_one(fixture)
    assert c.race_number == race
    assert c.track and c.track.value == track_id  # назва треку кирилицею
    assert c.car and c.car.value == car_id         # обране авто гравця (правий бік), англ.
    assert c.rank == rank
    assert c.time is None                           # гонку ще не їхали
    assert c.game_language == "ru"                  # мова визначена з якоря "ГОНКА N"


@pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")
def test_non_accordion_image_returns_empty():
    import numpy as np
    img = np.zeros((1600, 2560, 3), dtype=np.uint8)
    assert make_extractor().extract(img) == []
