import logging

from simplenote import Simplenote

from src.config import settings

logger = logging.getLogger(__name__)


def _get_client() -> Simplenote:
    return Simplenote(settings.SIMPLENOTE_EMAIL, settings.SIMPLENOTE_PASSWORD)


def add_to_shopping_list(text_to_append: str):
    text = f"\n{text_to_append}"
    _append_to_note_with_key(settings.SIMPLENOTE_SHOPPING_LIST_KEY, text)


def get_shopping_list() -> str:
    note = _get_note(settings.SIMPLENOTE_SHOPPING_LIST_KEY)
    return note["content"]


def remove_from_shopping_list(item: str) -> bool:
    key = settings.SIMPLENOTE_SHOPPING_LIST_KEY
    note = _get_note(key)
    lines = note["content"].split("\n")
    item_lower = item.lower().strip()
    new_lines = [l for l in lines if l.strip().lower() != item_lower]
    if len(new_lines) == len(lines):
        return False
    note["content"] = "\n".join(new_lines)
    _update_note(note, key)
    return True


def _append_to_note_with_key(key, text_to_append):
    note = _get_note(key)
    note["content"] += f"{text_to_append}"
    _update_note(note, key)


def _update_note(note, key):
    sn = _get_client()
    updated_note, status = sn.update_note(note)
    if status == 0:
        logger.info("Note '%s' updated successfully", key)
    else:
        logger.error("Failed to update note '%s'", key)


def _get_note(note_key):
    sn = _get_client()
    note, status = sn.get_note(note_key)
    if status != 0:
        logger.error("Failed to fetch note '%s'", note_key)
        raise Exception(f"Failed to fetch note '{note_key}'")
    return note
