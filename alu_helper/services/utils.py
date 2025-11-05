import os
import sys

def get_resource_path(relative_path: str) -> str:
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, "resources", relative_path)

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
        return None

# for test in ["01:02.300", "1:02.3", "1:2.3", "02.3", "1:02", "02", "2"]:
#     print(test + " -> " + str(parse_time(test)) + " -> " + format_time(parse_time(test)))
