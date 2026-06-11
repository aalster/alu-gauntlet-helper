import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from alu_gauntlet_helper.screen_recognition import ocr

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


def test_read_rank():
    assert ocr.read_rank(make_text_image("4,045")) == 4045


def test_read_name():
    text = ocr.read_name(make_text_image("ULTIMA RS"))
    assert "ULTIMA" in text.upper()
