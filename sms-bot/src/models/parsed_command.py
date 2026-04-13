from dataclasses import dataclass, field


@dataclass
class ParsedCommand:
    path: str
    positional: list[str] = field(default_factory=list)
    named: dict[str, str] = field(default_factory=dict)
    flags: dict[str, bool] = field(default_factory=dict)
    pin: str | None = None
    raw: str = ""
