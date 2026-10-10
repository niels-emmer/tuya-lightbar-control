from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent.parent / ".env"
# override=False: real environment variables win over .env, so injected
# secrets are never shadowed by a stale .env file.
load_dotenv(_ENV_FILE, override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # Tuya device
    device_id: str = ""
    device_ip: str = ""
    device_key: str = ""
    device_version: float = 3.5

    # Weather location — first-run seed for settings.json only. After the first
    # start the UI-editable settings.json is authoritative for the rain and
    # air_quality effects (see settings_store.weather()).
    weather_lat: float = 52.92
    weather_lon: float = 6.43

    # nanoclaw-cyd-monitor daemon (~/nanoclaw-monitor) — serves Claude Pro
    # session/weekly rate-limit usage. No auth token: LAN-open by default.
    claude_usage_url: str = "http://127.0.0.1:8787/usage"

    # API key — shared secret required on /api/* and the docs routes.
    # Empty string disables auth (local dev / trusted LAN only); set it in
    # production. See SECURITY.md.
    api_key: str = ""

    # MQTT broker — DSMR P1 smart-meter reader (daniel-jong/esp8266_p1meter).
    # Publishes watts to sensors/power/p1meter/actual_consumption.
    mqtt_host: str = "192.168.101.252"
    mqtt_port: int = 1883
    mqtt_topic: str = "sensors/power/p1meter/actual_consumption"


@lru_cache
def get_settings() -> Settings:
    return Settings()
