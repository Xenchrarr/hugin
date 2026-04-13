import os

from .dev_config import DevConfig
from .production import ProductionConfig

_CONFIGS = {
    "development": DevConfig,
    "production": ProductionConfig,
}


class Config:
    def __init__(self):
        env = os.environ.get("FLASK_ENV", "production")
        cls = _CONFIGS.get(env, ProductionConfig)
        self.active = cls()
