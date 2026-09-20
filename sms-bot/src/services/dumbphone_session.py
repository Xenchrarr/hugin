from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


# GSM-7 responses fit in one physical SMS after reserving the modem's trailing
# workaround character. Other scripts automatically fall back to UCS-2.
_MAX_PAGE_LENGTH = 159
_SESSION_TTL_SECONDS = 6 * 60 * 60


def _split_text(text: str, limit: int = _MAX_PAGE_LENGTH) -> list[str]:
    text = text.strip()
    if len(text) <= limit:
        return [text]

    # Reserve room for a marker such as " (123/123)".
    body_limit = limit - 15
    pages: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= body_limit:
            pages.append(remaining)
            break
        split_at = max(
            remaining.rfind("\n", 0, body_limit + 1),
            remaining.rfind(" ", 0, body_limit + 1),
        )
        if split_at < body_limit // 2:
            split_at = body_limit
        pages.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()

    total = len(pages)
    return [f"{page} ({index}/{total})" for index, page in enumerate(pages, 1)]


@dataclass
class _Session:
    pages: list[str] = field(default_factory=list)
    page_index: int = 0
    last_command: str = ""
    updated_at: float = field(default_factory=time.time)


class DumbphoneSessionService:
    """Small in-memory interaction state for paging and repeat commands."""

    def __init__(self) -> None:
        self._sessions: dict[str, _Session] = {}
        self._lock = threading.Lock()

    def _get(self, sender: str) -> _Session:
        now = time.time()
        session = self._sessions.get(sender)
        if session is None or now - session.updated_at > _SESSION_TTL_SECONDS:
            session = _Session()
            self._sessions[sender] = session
        session.updated_at = now
        return session

    def remember_command(self, sender: str, command: str) -> None:
        with self._lock:
            self._get(sender).last_command = command

    def last_command(self, sender: str) -> str:
        with self._lock:
            return self._get(sender).last_command

    def first_page(self, sender: str, text: str) -> str:
        pages = _split_text(text)
        with self._lock:
            session = self._get(sender)
            session.pages = pages
            session.page_index = 0
        return pages[0]

    def move(self, sender: str, delta: int) -> str:
        with self._lock:
            session = self._get(sender)
            if not session.pages:
                return "Nothing to page through."
            target = session.page_index + delta
            if target < 0:
                return "Already at the first page."
            if target >= len(session.pages):
                return "No more pages."
            session.page_index = target
            return session.pages[target]

    def cancel(self, sender: str) -> str:
        with self._lock:
            self._sessions.pop(sender, None)
        return "Cancelled."


sessions = DumbphoneSessionService()
