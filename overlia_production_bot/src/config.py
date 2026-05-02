import os


class Settings:
    TELEGRAM_API_KEY: str = os.environ.get("TELEGRAM_API_KEY", "")
    NIKOLAI_TELEGRAM_ID: str = os.environ.get("NIKOLAI_TELEGRAM_ID", "")
    CORE_API_URL: str = os.environ.get("CORE_API_URL", "http://hugin-core:5100")


settings = Settings()
