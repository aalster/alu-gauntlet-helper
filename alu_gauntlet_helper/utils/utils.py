import os
import sys
import uuid
from datetime import datetime, timezone

from PyQt6 import QtCore
from PyQt6.QtCore import QIODeviceBase, Qt, QPointF
from PyQt6.QtGui import QIcon, QPainter, QColor, QImage, QPixmap


def get_resource_path(relative_path: str) -> str:
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, "resources", relative_path)

DATA_PATH_MAPS = "data/maps"

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
