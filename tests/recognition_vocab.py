"""Спільний словник для тестів/бенчмарку розпізнавання: реальні треки й авто.

Будує TrackResolver і car-matcher з тих самих даних, що йдуть у застосунок
(`initial_data.tracks` + `resources/data/cars.json`), щоб тести розпізнавання
працювали на повному наборі назв (укр./рос.), а не на куцому хардкоді.
"""
import json
from pathlib import Path
from types import SimpleNamespace

from alu_gauntlet_helper.screen_recognition.matching import TrackResolver, build_car_matcher
from alu_gauntlet_helper.services.initial_data import map_names, tracks as _TRACKS

_CARS_JSON = Path(__file__).resolve().parent.parent / "resources" / "data" / "cars.json"

_MAP_RU = {en: ru for en, ru in map_names}


def track_views():
    """TrackView-подібні об'єкти з назвами карти/треку обома мовами."""
    views = []
    for i, t in enumerate(_TRACKS):
        views.append(SimpleNamespace(
            id=i, name=t.name, name_ru=t.name_ru,
            map_name=t.map_name, map_name_ru=_MAP_RU.get(t.map_name, ""),
        ))
    return views


def track_label(views, track_id):
    """(map_name, name) для людиночитного звіту/ассертів."""
    for v in views:
        if v.id == track_id:
            return v.map_name, v.name
    return None


def car_views():
    data = json.loads(_CARS_JSON.read_text(encoding="utf-8"))
    cars = []
    for i, c in enumerate(data):
        name = f"{c.get('brand', '')} {c.get('model', '')}".strip()
        cars.append(SimpleNamespace(id=i, name=name))
    return cars


def car_label(cars, car_id):
    for c in cars:
        if c.id == car_id:
            return c.name
    return None


def build_resolvers():
    """(track_resolver, car_matcher, track_views, car_views) на реальному словнику."""
    tv = track_views()
    cv = car_views()
    return TrackResolver(tv), build_car_matcher(cv), tv, cv
