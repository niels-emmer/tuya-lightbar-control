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
    weather_lat: float = 52.37
    weather_lon: float = 4.89

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

    # Polestar EV — charging state for the polestar effect. The Polestar API is
    # reverse-engineered (pypolestar); empty username/password disables the
    # effect (it shows a heartbeat). POLESTAR_VIN is optional: when empty the
    # first vehicle on the account is used. Each poll performs a full login, so
    # the interval is deliberately long (seconds).
    polestar_username: str = ""
    polestar_password: str = ""
    polestar_vin: str = ""
    polestar_poll_interval: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()
