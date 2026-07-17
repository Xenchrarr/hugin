import os


class Settings:
    CAMERA_IP: str = os.environ.get("CAMERA_IP", "")
    TIBBER_ACCESS_TOKEN: str = os.environ.get("TIBBER_ACCESS_TOKEN", "")
    HA_URL: str = os.environ.get("HA_URL", "http://homeassistant.local:8123")
    HA_TOKEN: str = os.environ.get("HA_TOKEN", "")
    SIMPLENOTE_EMAIL: str = os.environ.get("SIMPLENOTE_EMAIL", "")
    SIMPLENOTE_PASSWORD: str = os.environ.get("SIMPLENOTE_PASSWORD", "")
    SIMPLENOTE_SHOPPING_LIST_KEY: str = os.environ.get("SIMPLENOTE_SHOPPING_LIST_KEY", "")
    SIMPLENOTE_IDEAS_KEY: str = os.environ.get("SIMPLENOTE_IDEAS_KEY", "")
    ENERGY_DATABASE_URL: str = os.environ.get(
        "ENERGY_DATABASE_URL",
        "postgresql://energy:energy@energy-postgres:5432/energy",
    )
    TIMEZONE: str = os.environ.get("TIMEZONE", "Europe/Oslo")
    ORCHESTRATOR_API_URL: str = os.environ.get("ORCHESTRATOR_API_URL", "http://orchestrator:6000")
    SERVICE_KEY: str = os.environ.get("SERVICE_KEY", "")
    PRIMARY_USER_ID: int = int(os.environ.get("PRIMARY_USER_ID", "1"))
    TELEGRAM_BOT_URL: str = os.environ.get("TELEGRAM_BOT_URL", "http://overlia-power-bot:5060")
    GOOGLE_CALENDAR_ICAL_URLS: list[str] = [
        u.strip()
        for u in os.environ.get("GOOGLE_CALENDAR_ICAL_URLS", "").split(",")
        if u.strip()
    ]


settings = Settings()
