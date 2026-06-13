import base64
from pathlib import Path

from PyQt6.QtGui import QImage

from alu_gauntlet_helper.views.components.common import image_preview_html

REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTE_ICON = REPO_ROOT / "resources" / "icons" / "tracks" / "routes" / "Rome - Roman Tumble.png"  # 439x439


def _decode_preview(html: str) -> QImage:
    # фікс вшиває вже відмасштабоване зображення як data-URI, а не доручає
    # масштабування рушію тултипа (той робить швидкий nearest-neighbor скейл)
    assert html.startswith('<img src="data:image/png;base64,'), html[:60]
    b64 = html.split("base64,", 1)[1].split('"', 1)[0]
    img = QImage()
    img.loadFromData(base64.b64decode(b64), "PNG")
    assert not img.isNull()
    return img


def test_preview_prescaled_to_target_width():
    html = image_preview_html(str(ROUTE_ICON), width=360)
    img = _decode_preview(html)
    # 439 -> 360: піксельний розмір вже цільовий, Qt не дораховує скейл
    assert (img.width(), img.height()) == (360, 360)


def test_preview_does_not_upscale_small_image(tmp_path):
    small = tmp_path / "small.png"
    QImage(120, 80, QImage.Format.Format_ARGB32).save(str(small))
    html = image_preview_html(str(small), width=360)
    img = _decode_preview(html)
    assert (img.width(), img.height()) == (120, 80)


def test_preview_empty_for_missing_file(tmp_path):
    assert image_preview_html(str(tmp_path / "nope.png")) == ""
