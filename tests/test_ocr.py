from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from alu_gauntlet_helper.screen_recognition import ocr
from alu_gauntlet_helper.screen_recognition.regions import RACE_RESULT_PLAYER_TIME

FIXTURES = Path(__file__).parent / "fixtures"
TESSERACT_OK = ocr.configure_tesseract() and ocr.is_available()
pytestmark = pytest.mark.skipif(not TESSERACT_OK, reason="tesseract не знайдено")


def make_text_image(text: str) -> np.ndarray:
    """Світлий текст на темно-синьому тлі — як у грі."""
    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except OSError:
        font = ImageFont.load_default(size=48)
    img = Image.new("RGB", (640, 100), (24, 32, 90))
    ImageDraw.Draw(img).text((20, 20), text, font=font, fill=(255, 255, 255))
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def test_read_time():
    assert ocr.read_time(make_text_image("00:22.797")) == 22797


def test_read_time_garbage_returns_none():
    assert ocr.read_time(make_text_image("HELLO")) is None


@pytest.mark.parametrize("alpha", [0.0, 0.2, 0.35, 0.5, 0.8])
def test_read_time_under_red_glow_pulse(alpha):
    """Регресія: червоне сяйво під часом програної гонки на живому екрані
    пульсує. На проміжній інтенсивності (~0.2-0.35) Otsu у сірому каналі
    заливає відкриту верхівку «4», і "00:24.182" читалось як 26182 —
    валідний за форматом, але хибний збіг. Голосування каналів (сірий /
    max / min) має повертати правильний час на будь-якій фазі пульсації."""
    fixture = FIXTURES / "race_result_4_lost.png"
    if not fixture.exists():
        pytest.skip("немає фікстури")
    crop = RACE_RESULT_PLAYER_TIME.crop(cv2.imread(str(fixture)))

    h, w = crop.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    dist = np.sqrt(((xx - w * 0.45) / (w * 0.5)) ** 2 + ((yy - h * 0.6) / (h * 0.6)) ** 2)
    falloff = np.clip(1.0 - dist, 0, 1)[..., None] * alpha
    red = np.full_like(crop, (40, 30, 230))
    glow = (crop * (1 - falloff) + red * falloff).astype(np.uint8)

    assert ocr.read_time(glow) == 24182


def make_plate_image(text: str = "", plate: bool = True, edge_bar: bool = False) -> np.ndarray:
    """Ігрова плашка часу: чорний паралелограм на блакитному тлі, світлі цифри.

    edge_bar=True домальовує темну смугу фону сторінки на всю ширину внизу —
    як на car_selection_ru_1_sf, де така смуга БІЛЬША за плашку за площею."""
    try:
        font = ImageFont.truetype("arialbd.ttf", 44)
    except OSError:
        font = ImageFont.load_default(size=44)
    img = Image.new("RGB", (620, 190), (210, 170, 90))  # блакитний фон (BGR-подібний)
    draw = ImageDraw.Draw(img)
    if plate:
        # похилі краї, як у грі
        draw.polygon([(120, 40), (500, 32), (485, 120), (105, 128)], fill=(10, 10, 10))
        if text:
            draw.text((190, 55), text, font=font, fill=(180, 240, 60))
    if edge_bar:
        draw.rectangle([(0, 138), (620, 190)], fill=(25, 20, 40))
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def test_read_time_plate():
    assert ocr.read_time_plate(make_plate_image("00:21.149")) == 21149


def test_read_time_plate_no_plate_returns_none():
    """Немає чорної плашки (BEFORE-варіант: справа лише фон) → None."""
    assert ocr.read_time_plate(make_plate_image(plate=False)) is None


def test_read_time_plate_empty_plate_returns_none():
    assert ocr.read_time_plate(make_plate_image("")) is None


def test_read_time_plate_empty_crop_returns_none():
    assert ocr.read_time_plate(np.zeros((0, 0, 3), dtype=np.uint8)) is None


def test_read_time_plate_ignores_edge_touching_bar():
    """Регресія (car_selection_ru_1_sf): темна смуга фону сторінки внизу зони
    БІЛЬША за плашку за площею — «найбільший темний компонент» обирав її, і час
    губився. Смуга перетинає зону наскрізь (торкається країв), а плашка завжди
    всередині зони з запасом — компоненти на краю відкидаються."""
    assert ocr.read_time_plate(make_plate_image("00:20.569", edge_bar=True)) == 20569


def test_read_time_plate_only_edge_bar_returns_none():
    assert ocr.read_time_plate(make_plate_image(plate=False, edge_bar=True)) is None


def test_read_rank():
    assert ocr.read_rank(make_text_image("4,045")) == 4045


def test_read_name():
    text = ocr.read_name(make_text_image("ULTIMA RS"))
    assert "ULTIMA" in text.upper()
