import json
import urllib.request
from datetime import datetime, timedelta, timezone

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.cars import USER_AGENT
from alu_gauntlet_helper.utils.utils import get_resource_path

CARS_LIST_URL = "https://asec.tools/.netlify/functions/carsList"
CARS_RESOURCE_FILE = "data/cars.json"
CARS_UPDATE_INTERVAL = timedelta(weeks=1)
FETCH_TIMEOUT_SECONDS = 10


def load_bundled_cars() -> list[dict]:
    path = get_resource_path(CARS_RESOURCE_FILE)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        print(f"Failed to load bundled cars list {path}: {e}")
        return []


def fetch_remote_cars() -> list[dict]:
    request = urllib.request.Request(CARS_LIST_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def update_cars_if_needed():
    """Refresh cars from asec.tools, at most once a week. Failures are non-fatal."""
    settings = APP_CONTEXT.settings.get()
    if settings.cars_updated_at:
        try:
            updated_at = datetime.fromisoformat(settings.cars_updated_at)
            if datetime.now(timezone.utc) - updated_at < CARS_UPDATE_INTERVAL:
                return
        except ValueError:
            print(f"Invalid cars_updated_at value: {settings.cars_updated_at}")

    try:
        entries = fetch_remote_cars()
    except Exception as e:
        print(f"Failed to fetch cars list from {CARS_LIST_URL}: {e}")
        return

    if not entries:
        return

    APP_CONTEXT.cars_service.sync_from_asec(entries)
    settings.cars_updated_at = datetime.now(timezone.utc).isoformat()
    APP_CONTEXT.settings.save(settings)
