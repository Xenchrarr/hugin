from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.commands.base_command import BaseCommand

logger = logging.getLogger(__name__)


def _distance(a: str, b: str) -> int:
    """Damerau-Levenshtein distance (supports transpositions)."""
    la, lb = len(a), len(b)
    d: dict[tuple[int, int], int] = {}
    for i in range(-1, la + 1):
        d[i, -1] = i + 1
    for j in range(-1, lb + 1):
        d[-1, j] = j + 1
    for i in range(la):
        for j in range(lb):
            cost = 0 if a[i] == b[j] else 1
            d[i, j] = min(
                d[i - 1, j] + 1,
                d[i, j - 1] + 1,
                d[i - 1, j - 1] + cost,
            )
            if i > 0 and j > 0 and a[i] == b[j - 1] and a[i - 1] == b[j]:
                d[i, j] = min(d[i, j], d[i - 2, j - 2] + 1)
    return d[la - 1, lb - 1]


class CommandResolver:
    def __init__(self) -> None:
        self._commands: dict[str, BaseCommand] = {}

    @property
    def commands(self) -> dict[str, BaseCommand]:
        return dict(self._commands)

    def register(self, path: str, handler: BaseCommand) -> None:
        self._commands[path.lower()] = handler

    def resolve(self, path: str) -> tuple[BaseCommand | None, list[str]]:
        path = path.lower()

        # 1. Exact match
        if path in self._commands:
            return self._commands[path], []

        known = list(self._commands.keys())

        # 2. Unique prefix match
        prefix_matches = [k for k in known if k.startswith(path)]
        if len(prefix_matches) == 1:
            logger.debug("Prefix match: %s -> %s", path, prefix_matches[0])
            return self._commands[prefix_matches[0]], []
        if len(prefix_matches) > 1:
            return None, prefix_matches

        # 3. Damerau-Levenshtein distance 1 (includes transpositions)
        close = [k for k in known if _distance(path, k) <= 1]
        if len(close) == 1:
            logger.debug("Levenshtein match: %s -> %s", path, close[0])
            return self._commands[close[0]], []
        if len(close) > 1:
            return None, close

        # 4. No match — suggest closest (distance <= 2) for hint
        suggestions = [k for k in known if _distance(path, k) <= 2]
        return None, suggestions
