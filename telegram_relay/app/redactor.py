import re
from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.normalizer import NormalizedMessage


class _CompiledPattern:
    def __init__(self, field: str, pattern: str, replacement: str) -> None:
        self.field = field
        self._re = re.compile(pattern)
        self.replacement = replacement

    def apply(self, value: str) -> str:
        return self._re.sub(self.replacement, value)


class Redactor:
    def apply(
        self,
        msg: "NormalizedMessage",
        patterns: list[dict],
    ) -> "NormalizedMessage":
        if not patterns:
            return msg

        compiled = [
            _CompiledPattern(
                field=p["field"],
                pattern=p["pattern"],
                replacement=p.get("replace", "[REDACTED]"),
            )
            for p in patterns
        ]

        updates: dict = {}
        for cp in compiled:
            current = getattr(msg, cp.field, None)
            if isinstance(current, str):
                redacted = cp.apply(current)
                if redacted != current:
                    updates[cp.field] = redacted

        return replace(msg, **updates) if updates else msg
