import logging
import os

from src.api.core import HuginCoreClient

logger = logging.getLogger(__name__)

_core = HuginCoreClient(os.environ.get("CORE_API_URL", "http://hugin-core:5100"))


def add_to_shopping_list(text_to_append: str) -> bool:
    result = _core.add_to_shopping_list(text_to_append)
    return result is not None


def get_shopping_list():
    content = _core.get_shopping_list()
    if content is None:
        raise Exception("Failed to fetch shopping list from core API")
    return content


def remove_from_shopping_list(item: str) -> bool:
    return _core.remove_from_shopping_list(item)
