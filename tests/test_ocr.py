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


def test_read_rank():
    assert ocr.read_rank(make_text_image("4,045")) == 4045


def test_read_name():
    text = ocr.read_name(make_text_image("ULTIMA RS"))
    assert "ULTIMA" in text.upper()
