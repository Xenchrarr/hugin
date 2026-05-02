import os
from typing import Any

from pydantic import BaseModel, Field


class TelegramConfig(BaseModel):
    api_id: int
    api_hash: str
    phone_number: str
    db_encryption_key: str


class RetryConfig(BaseModel):
    max_attempts: int = 3
    backoff_seconds: float = 2.0


class DestinationConfig(BaseModel):
    id: str
    type: str
    # webhook fields
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    timeout: float = 10.0
    retry: RetryConfig = Field(default_factory=RetryConfig)
    # sms fields (and any future type extras)
    config: dict[str, Any] = Field(default_factory=dict)


class AppConfig(BaseModel):
    telegram: TelegramConfig


def load_telegram_config() -> TelegramConfig:
    """Load Telegram credentials from environment variables only."""
    return TelegramConfig(
        api_id=int(os.environ["TELEGRAM_API_ID"]),
        api_hash=os.environ["TELEGRAM_API_HASH"],
        phone_number=os.environ["TELEGRAM_PHONE_NUMBER"],
        db_encryption_key=os.environ["DB_ENCRYPTION_KEY"],
    )
