import os


class Settings:
    GROWATT_USERNAME: str = os.environ.get("GROWATT_USERNAME", "")
    GROWATT_PASSWORD: str = os.environ.get("GROWATT_PASSWORD", "")
    YR_ID: str = os.environ.get("YR_ID", "")
    CAMERA_IP: str = os.environ.get("CAMERA_IP", "")
    TIBBER_ACCESS_TOKEN: str = os.environ.get("TIBBER_ACCESS_TOKEN", "")
    HA_URL: str = os.environ.get("HA_URL", "http://homeassistant.local:8123")
    HA_TOKEN: str = os.environ.get("HA_TOKEN", "")
    SIMPLENOTE_EMAIL: str = os.environ.get("SIMPLENOTE_EMAIL", "")
    SIMPLENOTE_PASSWORD: str = os.environ.get("SIMPLENOTE_PASSWORD", "")
    SIMPLENOTE_SHOPPING_LIST_KEY: str = os.environ.get("SIMPLENOTE_SHOPPING_LIST_KEY", "")
    ENERGY_DATABASE_URL: str = os.environ.get(
        "ENERGY_DATABASE_URL",
        "postgresql://energy:energy@energy-postgres:5432/energy",
    )
    TIMEZONE: str = os.environ.get("TIMEZONE", "Europe/Oslo")


settings = Settings()
