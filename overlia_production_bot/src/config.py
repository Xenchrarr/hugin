import os


class Settings:
    TELEGRAM_API_KEY: str = os.environ.get("TELEGRAM_API_KEY", "")
    YR_ID: str = os.environ.get("YR_ID", "")
    NIKOLAI_YR_ID: str = os.environ.get("NIKOLAI_YR_ID", "")
    CORE_API_URL: str = os.environ.get("CORE_API_URL", "http://hugin-core:5100")
    ALLOWED_USER_IDS: set[int] = {
        int(uid.strip())
        for uid in os.environ.get("ALLOWED_USER_IDS", "").split(",")
        if uid.strip()
    }


settings = Settings()
