from alu_helper.services.maps import MapsRepository, MapsService
from alu_helper.services.tracks import TracksRepository, TracksService


class AppContext:
    maps_service: MapsService
    tracks_service: TracksService

    def __init__(self):
        self.maps_repo = MapsRepository()
        self.maps_service = MapsService(self.maps_repo)

        self.tracks_repo = TracksRepository()
        self.tracks_service = TracksService(self.tracks_repo, self.maps_service)

APP_CONTEXT: AppContext = AppContext()