import os

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.cars_sync import load_bundled_cars
from alu_gauntlet_helper.services.maps import Map
from alu_gauntlet_helper.services.tracks import TrackView
from alu_gauntlet_helper.utils.utils import copy_resource_to_data, DATA_PATH_MAPS


def init_data():
    for name in map_names:
        icon_file = f"{name}.png"
        icon_path = copy_resource_to_data(f"icons/maps/{icon_file}", os.path.join(DATA_PATH_MAPS, icon_file))
        APP_CONTEXT.maps_service.save(Map(name=name, icon=icon_path or ""))
    APP_CONTEXT.cars_service.sync_from_asec(load_bundled_cars())
    for track in tracks:
        APP_CONTEXT.tracks_service.save(track)


map_names = [
    "Auckland", "Buenos Aires", "Cairo", "Greenland", "Himalayas", "Nevada",
    "New York", "Norway", "Osaka", "Paris", "Rome", "San Francisco",
    "Scotland", "Shanghai", "Singapore", "The Caribbean", "Tuscany", "U.S. Midwest",
]


# https://asphalt9.info/asphalt9/game-mode/tracks/
# console.log([...document.querySelectorAll('#tablepress-11 tbody tr')]
#     .map(tr => 'TrackView(map_name="' + tr.querySelector('.column-2').textContent + '", name="' + (tr.querySelector('.column-3 a')?.text || tr.querySelector('.column-3').textContent) + '")')
#     .reduce((a, b) => a + ",\n" + b))
tracks = [
    TrackView(map_name="Auckland", name="Hairpin Finish"),
    TrackView(map_name="Auckland", name="Straight Sprint"),
    TrackView(map_name="Buenos Aires", name="La Boca"),
    TrackView(map_name="Buenos Aires", name="Water Run"),
    TrackView(map_name="Cairo", name="A Kings Revival"),
    TrackView(map_name="Cairo", name="Gezira Island"),
    TrackView(map_name="Greenland", name="Ice Breakers"),
    TrackView(map_name="Greenland", name="Out of the Center"),
    TrackView(map_name="Himalayas", name="Freefall"),
    TrackView(map_name="Himalayas", name="Leap of Faith"),
    TrackView(map_name="Nevada", name="Bridge to Bridge"),
    TrackView(map_name="Nevada", name="Tunnel Sprint"),
    TrackView(map_name="New York", name="A Run in the Park"),
    TrackView(map_name="New York", name="Friendly Neighborhood"),
    TrackView(map_name="New York", name="Wall Street Ride"),
    TrackView(map_name="Norway", name="Future Fusion"),
    TrackView(map_name="Norway", name="Rocketing to the Future"),
    TrackView(map_name="Osaka", name="Meiji Rush"),
    TrackView(map_name="Osaka", name="Namba Park"),
    TrackView(map_name="Paris", name="Along the Seine"),
    TrackView(map_name="Paris", name="Metro"),
    TrackView(map_name="Paris", name="Notre Dame"),
    TrackView(map_name="Rome", name="Roman Byroads"),
    TrackView(map_name="Rome", name="Roman Tumble"),
    TrackView(map_name="San Francisco", name="Railroad Bustle"),
    TrackView(map_name="San Francisco", name="The Tunnel"),
    TrackView(map_name="Scotland", name="Ghost Ships"),
    TrackView(map_name="Scotland", name="Rocky Valley"),
    TrackView(map_name="Shanghai", name="Double Roundabout"),
    TrackView(map_name="Shanghai", name="Paris of the East"),
    TrackView(map_name="Singapore", name="Urban Rush"),
    TrackView(map_name="Singapore", name="Waterslide Whirl"),
    TrackView(map_name="The Caribbean", name="Hell Vale"),
    TrackView(map_name="The Caribbean", name="Islet Race"),
    TrackView(map_name="The Caribbean", name="Resort Dash"),
    TrackView(map_name="Tuscany", name="Versatile Trail"),
    TrackView(map_name="Tuscany", name="Vineyard Voyage"),
    TrackView(map_name="Tuscany", name="Riverine Launch"),
    TrackView(map_name="U.S. Midwest", name="Its a Twister"),
    TrackView(map_name="U.S. Midwest", name="Trainspotter")
]
