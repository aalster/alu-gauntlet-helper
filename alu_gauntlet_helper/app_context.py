from alu_gauntlet_helper.services.assistant import AssistantService
from alu_gauntlet_helper.services.cars import CarsRepository, CarsService
from alu_gauntlet_helper.services.maps import MapsRepository, MapsService
from alu_gauntlet_helper.services.races import RacesService, RacesRepository
from alu_gauntlet_helper.services.session_manager import SessionManager
from alu_gauntlet_helper.services.settings import SettingsService, SettingsRepository
from alu_gauntlet_helper.services.tracks import TracksRepository, TracksService


class AppContext:
    settings: SettingsService
    maps_service: MapsService
    tracks_service: TracksService
    cars_service: CarsService
    races_service: RacesService
    assistant: AssistantService
    session_manager: SessionManager

    def __init__(self):
        self.settings = SettingsService(SettingsRepository())
        self.maps_service = MapsService(MapsRepository())
        self.tracks_service = TracksService(TracksRepository(), self.maps_service)
        self.cars_service = CarsService(CarsRepository())
        self.races_service = RacesService(RacesRepository(), self.tracks_service, self.cars_service)
        self.assistant = AssistantService(self.races_service, self.cars_service)
        self.session_manager = SessionManager(auto_pick=self.assistant.auto_pick)

APP_CONTEXT: AppContext = AppContext()