from alu_gauntlet_helper.database import connect
from pydantic import BaseModel


class Settings(BaseModel):
    initial_data_loaded: bool = False
    window_geometry: str = ""
    window_state: str = ""

    show_tray_icon: bool = False
    close_to_tray: bool = False
    start_minimized: bool = False

class SettingsRepository:

    def save(self, key: str, value: str):
        with connect() as conn:
            conn.execute("INSERT OR REPLACE INTO settings(`key`, value) VALUES (:key, :value)", {"key": key, "value": value})

    def get_all(self):
        with connect() as conn:
            rows = conn.execute("SELECT * FROM settings").fetchall()
            data = {row["key"]: row["value"] for row in rows}
            return Settings(**data)


class SettingsService:
    cache = None

    def __init__(self, repo: SettingsRepository):
        self.repo = repo

    def save(self, settings: Settings):
        for key, value1 in self.get().model_dump().items():
            value2 = getattr(settings, key)
            if value1 != value2:
                self.repo.save(key, str(value2))
        self.cache = None

    def get(self) -> Settings:
        if not self.cache:
            self.cache = self.repo.get_all()
        return Settings(**self.cache.model_dump())