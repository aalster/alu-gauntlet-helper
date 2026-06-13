import json

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.utils.utils import get_resource_path

CARS_RESOURCE_FILE = "data/cars.json"


def load_bundled_cars() -> list[dict]:
    path = get_resource_path(CARS_RESOURCE_FILE)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        print(f"Failed to load bundled cars list {path}: {e}")
        return []


def sync_bundled_cars():
    """Апсерт авто з бандленого знімка на кожному старті — підхоплює оновлення бандла.

    Оновлення знімка та іконок — вручну, див. docs/updating-cars-data.md."""
    APP_CONTEXT.cars_service.sync_from_asec(load_bundled_cars())
