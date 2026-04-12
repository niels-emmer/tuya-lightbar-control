from pathlib import Path
from functools import lru_cache
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent.parent / ".env"
load_dotenv(_ENV_FILE, override=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # Tuya device
    device_id: str = ""
    device_ip: str = ""
    device_key: str = ""
    device_version: float = 3.5

    # Weather location (for future weather mode)
    weather_lat: float = 52.37
    weather_lon: float = 4.89


@lru_cache
def get_settings() -> Settings:
    return Settings()
