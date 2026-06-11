import os
import sys
import uuid
from datetime import datetime, timezone

import math

from PyQt6 import QtCore
from PyQt6.QtCore import QIODeviceBase, Qt, QPointF, QSize
from PyQt6.QtGui import QIcon, QPainter, QColor, QImage, QPixmap, QImageReader


def get_resource_path(relative_path: str) -> str:
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, "resources", relative_path)

DATA_PATH_MAPS = "data/maps"
DATA_PATH_CARS = "data/cars"


def copy_resource_to_data(res_path: str, data_path: str) -> str | None:
    """Copy resource file to data directory. Returns destination path or None if source not found."""
    src = get_resource_path(res_path)
    if not os.path.exists(src):
        return None

    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    if not os.path.exists(data_path):
        import shutil
        shutil.copy(src, data_path)

    return data_path


def save_data_image(path: str, img: QImage, ext: str = "png") -> str:
    os.makedirs(path, exist_ok=True)
    result = os.path.join(path, uuid.uuid4().hex + "." + ext)
    img.save(result)
    return result

LOCAL_TZ = datetime.now().astimezone().tzinfo

def parse_utc_datetime(value):
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)
        except ValueError:
            print(f"Failed to parse datetime: {value}")
            return None
    return value

time_format_regex = r"^\d{0,2}:?\d{0,2}(?:\.\d{0,3})?$"

def format_time(ms: int) -> str:
    if not ms:
        return ""
    seconds = ms // 1000
    minutes = seconds // 60
    return f"{minutes:02}:{seconds % 60:02}.{ms % 1000:03}"

def parse_time(time: str) -> int:
    time = time.strip()
    if not time:
        return 0

    try:
        minutes = 0
        if ":" in time:
            minutes_str, time = time.split(":")
            minutes = int(minutes_str)

        millis = 0
        if "." in time:
            time, millis_str = time.split(".")
            millis = int(millis_str.ljust(3, "0"))

        seconds = int(time)
        return (minutes * 60 + seconds) * 1000 + millis
    except ValueError:
        return 0

def format_relative_time(dt: datetime) -> str:
    """Format a datetime as a relative phrase like '2 days ago'."""
    if not dt:
        return ""
    seconds = int((datetime.now(LOCAL_TZ) - dt).total_seconds())
    if seconds < 60:
        return "just now"

    minutes, hours, days = seconds // 60, seconds // 3600, seconds // 86400
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    if hours < 24:
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    if days < 7:
        return f"{days} day{'s' if days > 1 else ''} ago"
    if days < 30:
        weeks = days // 7
        return f"{weeks} week{'s' if weeks > 1 else ''} ago"
    if days < 365:
        months = days // 30
        return f"{months} month{'s' if months > 1 else ''} ago"
    years = days // 365
    return f"{years} year{'s' if years > 1 else ''} ago"

def format_time_delta(time_delta) -> str:
    total_minutes = int(time_delta.total_seconds() // 60)
    hours, minutes = divmod(total_minutes, 60)
    days, hours = divmod(hours, 24)

    day_str = ""
    if days > 0:
        day_str = f"{days} day, " if days == 1 else f"{days} days, "
    return f"{day_str}{hours:02}:{minutes:02}"

def pixmap_to_bytes(pixmap, format_="PNG"):
    ba = QtCore.QByteArray()
    buff = QtCore.QBuffer(ba)
    buff.open(QIODeviceBase.OpenModeFlag.WriteOnly)
    ok = pixmap.save(buff, format_)
    assert ok
    return ba.data()

def create_badged_icon(base_icon: QIcon, radius = 24, color = QColor(255, 50, 50)) -> QIcon:
    pixmap = base_icon.pixmap(128, 128)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    x = pixmap.width() - radius - 2
    y = 2 + radius

    painter.setBrush(color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(QPointF(x, y), radius, radius)
    painter.end()

    return QIcon(pixmap)

_pixmap_cache: dict[tuple[str, int, int], QPixmap] = {}

def load_pixmap_cover(path: str, w: int, h: int) -> QPixmap | None:
    """Load an image scaled and center-cropped to w*h, cached by (path, w, h)."""
    key = (path, w, h)
    cached = _pixmap_cache.get(key)
    if cached is not None:
        return cached

    reader = QImageReader(path)
    size = reader.size()
    if size.isValid() and size.width() > 0 and size.height() > 0:
        ratio = max(w / size.width(), h / size.height())
        reader.setScaledSize(QSize(math.ceil(size.width() * ratio), math.ceil(size.height() * ratio)))
    img = reader.read()
    if img.isNull():
        return None

    pixmap = pixmap_cover(QPixmap.fromImage(img), w, h)
    _pixmap_cache[key] = pixmap
    return pixmap


def pixmap_cover(img: QPixmap, w: int, h: int) -> QPixmap:
    iw, ih = img.width(), img.height()
    ratio_img = iw / ih
    ratio_target = w / h

    if ratio_img > ratio_target:
        new_height = h
        new_width = int(ratio_img * new_height)
    else:
        new_width = w
        new_height = int(new_width / ratio_img)

    pix = img.scaled(new_width, new_height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)

    x = (new_width - w) // 2
    y = (new_height - h) // 2
    return pix.copy(x, y, w, h)
