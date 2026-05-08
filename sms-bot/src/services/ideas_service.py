import logging
import os

from src.api.core import HuginCoreClient

logger = logging.getLogger(__name__)

_core = HuginCoreClient(os.environ.get("CORE_API_URL", "http://hugin-core:5100"))


def add_to_ideas(text_to_append: str):
    _core.add_to_ideas(text_to_append)


def get_ideas():
    content = _core.get_ideas()
    if content is None:
        raise Exception("Failed to fetch ideas from core API")
    return content
