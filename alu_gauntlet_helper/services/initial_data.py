import os

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.maps import Map
from alu_gauntlet_helper.services.tracks import TrackView
from alu_gauntlet_helper.utils.utils import copy_resource_to_data, DATA_PATH_MAPS, DATA_PATH_TRACKS


def init_data():
    """Одноразовий сід карт і треків; авто синхронізуються з бандла на кожному старті."""
    for name, name_ru in map_names:
        icon_file = f"{name}.png"
        icon_path = copy_resource_to_data(f"icons/maps/{icon_file}", os.path.join(DATA_PATH_MAPS, icon_file))
        APP_CONTEXT.maps_service.save(Map(name=name, name_ru=name_ru, icon=icon_path or ""))
    for track in tracks:
        track.icon = _bundled_track_icon(track.map_name, track.name)
        track.icon_preview = _bundled_track_preview(track.map_name, track.name)
        APP_CONTEXT.tracks_service.save(track)


def _bundled_track_icon(map_name: str, track_name: str) -> str:
    icon_file = f"{map_name} - {track_name}.png"
    return copy_resource_to_data(f"icons/tracks/routes/{icon_file}", os.path.join(DATA_PATH_TRACKS, icon_file)) or ""


def _bundled_track_preview(map_name: str, track_name: str) -> str:
    icon_file = f"{map_name} - {track_name}.png"
    # окрема підтека, щоб імʼя превʼю не конфліктувало з повною іконкою в data/tracks
    return copy_resource_to_data(f"icons/tracks/routes_preview/{icon_file}",
                                 os.path.join(DATA_PATH_TRACKS, "preview", icon_file)) or ""


def sync_track_icons():
    """Кожен старт: підтягує іконку та превʼю маршруту з бандла для треків без власної.

    Не додає й не воскрешає видалені треки і не чіпає вже встановлені (зокрема правки користувача).
    """
    for track in APP_CONTEXT.tracks_service.get_all_views():
        if track.icon and track.icon_preview:
            continue
        changed = False
        if not track.icon:
            icon_path = _bundled_track_icon(track.map_name, track.name)
            if icon_path:
                track.icon = icon_path
                changed = True
        if not track.icon_preview:
            preview_path = _bundled_track_preview(track.map_name, track.name)
            if preview_path:
                track.icon_preview = preview_path
                changed = True
        if changed:
            APP_CONTEXT.tracks_service.repo.update(track)


# (англ. назва, рос. назва з гри). Порожній рос. → показ англійською.
map_names = [
    ("Auckland", "Окленд"),
    ("Buenos Aires", "Буэнос-Айрес"),
    ("Cairo", "Каир"),
    ("Greenland", "Гренландия"),
    ("Himalayas", "Гималаи"),
    ("Nevada", "Невада"),
    ("New York", "Нью-Йорк"),
    ("Norway", "Норвегия"),
    ("Osaka", "Осака"),
    ("Paris", "Париж"),
    ("Rome", "Рим"),
    ("San Francisco", "Сан-Франциско"),
    ("Scotland", "Шотландия"),
    ("Shanghai", "Шанхай"),
    ("Singapore", "Сингапур"),
    ("The Caribbean", "Карибы"),
    ("Tuscany", "Тоскана"),
    ("U.S. Midwest", "Ср. Запад США"),
]


# https://asphalt9.info/asphalt9/game-mode/tracks/
# console.log([...document.querySelectorAll('#tablepress-11 tbody tr')]
#     .map(tr => 'TrackView(map_name="' + tr.querySelector('.column-2').textContent + '", name="' + (tr.querySelector('.column-3 a')?.text || tr.querySelector('.column-3').textContent) + '")')
#     .reduce((a, b) => a + ",\n" + b))
tracks = [
    TrackView(map_name="Auckland", name="Hairpin Finish", name_ru="Крутой Финиш"),
    TrackView(map_name="Auckland", name="Straight Sprint", name_ru="Спринт по Прямой"),
    TrackView(map_name="Buenos Aires", name="La Boca", name_ru="La Boca"),
    TrackView(map_name="Buenos Aires", name="Water Run", name_ru="Водный Заезд"),
    TrackView(map_name="Cairo", name="A Kings Revival", name_ru="Возвращение Короля"),
    TrackView(map_name="Cairo", name="Gezira Island", name_ru="Остров Гезира"),
    TrackView(map_name="Greenland", name="Ice Breakers", name_ru="Ледоломы"),
    TrackView(map_name="Greenland", name="Out of the Center", name_ru="Из Центра"),
    TrackView(map_name="Himalayas", name="Freefall", name_ru="Свободное Падение"),
    TrackView(map_name="Himalayas", name="Leap of Faith", name_ru="Прыжок Веры"),
    TrackView(map_name="Nevada", name="Bridge to Bridge", name_ru="От Моста к Мосту"),
    TrackView(map_name="Nevada", name="Tunnel Sprint", name_ru="Туннельный Спринт"),
    TrackView(map_name="New York", name="A Run in the Park", name_ru="Пробежка по Парку"),
    # TrackView(map_name="New York", name="Friendly Neighborhood", name_ru=""),
    TrackView(map_name="New York", name="Wall Street Ride", name_ru="Поездка по Уолл-Стрит"),
    TrackView(map_name="Norway", name="Future Fusion", name_ru="Синтез Будущего"),
    TrackView(map_name="Norway", name="Rocketing to the Future", name_ru="Вперед в Будущее"),
    TrackView(map_name="Osaka", name="Meiji Rush", name_ru="Натиск Мэйдзи"),
    TrackView(map_name="Osaka", name="Namba Park", name_ru="Парк Намба"),
    TrackView(map_name="Paris", name="Along the Seine", name_ru="Вдоль Сены"),
    # TrackView(map_name="Paris", name="Metro", name_ru=""),
    TrackView(map_name="Paris", name="Notre Dame", name_ru="Нотр-Дам"),
    TrackView(map_name="Rome", name="Roman Byroads", name_ru="Римские Тропы"),
    TrackView(map_name="Rome", name="Roman Tumble", name_ru="Римские Качели"),
    TrackView(map_name="San Francisco", name="Railroad Bustle", name_ru="Железная Дорога"),
    TrackView(map_name="San Francisco", name="The Tunnel", name_ru="Тоннель"),
    TrackView(map_name="Scotland", name="Ghost Ships", name_ru="Летучий Голландец"),
    TrackView(map_name="Scotland", name="Rocky Valley", name_ru="Каньон"),
    TrackView(map_name="Shanghai", name="Double Roundabout", name_ru="Двойное Кольцо"),
    TrackView(map_name="Shanghai", name="Paris of the East", name_ru="Восточный Париж"),
    TrackView(map_name="Singapore", name="Urban Rush", name_ru="Городская Спешка"),
    TrackView(map_name="Singapore", name="Waterslide Whirl", name_ru="Водоворот"),
    TrackView(map_name="The Caribbean", name="Hell Vale", name_ru="Адская Долина"),
    # TrackView(map_name="The Caribbean", name="Islet Race", name_ru=""),
    TrackView(map_name="The Caribbean", name="Resort Dash", name_ru="Курортный Прорыв"),
    # TrackView(map_name="Tuscany", name="Versatile Trail", name_ru=""),
    TrackView(map_name="Tuscany", name="Vineyard Voyage", name_ru="Вояж по Виноградникам"),
    TrackView(map_name="Tuscany", name="Riverine Launch", name_ru="Старт на Берегу Реки"),
    TrackView(map_name="U.S. Midwest", name="Its a Twister", name_ru="Вот Это Поворот!"),
    TrackView(map_name="U.S. Midwest", name="Trainspotter", name_ru="Рельсы")
]
