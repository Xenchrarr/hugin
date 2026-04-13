import re
import shlex

from src.models.parsed_command import ParsedCommand

RE_AUTH_PIN = re.compile(r"(?:\s|^)#(?P<pin>\d{4,8})\s*$")
RE_NAMED = re.compile(r"^(?P<k>[A-Za-z]\w*)(?:=|:)(?P<v>.+)$")
RE_FLAG = re.compile(r"^(?P<s>[+-])(?P<f>[A-Za-z]\w*)$")


def extract_pin(text: str) -> tuple[str, str | None]:
    m = RE_AUTH_PIN.search(text)
    if not m:
        return text, None
    return text[: m.start()].rstrip(), m.group("pin")


def tokenize(text: str) -> list[str]:
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def parse(text: str) -> ParsedCommand:
    raw = text
    text = text.strip()
    if not text:
        raise ValueError("empty message")

    text, pin = extract_pin(text)
    tokens = tokenize(text)
    if not tokens:
        raise ValueError("empty message")

    path = tokens[0].lower()

    # Handle old-style "cmd:text" or "cmd:" (backward compat with colon syntax)
    if ':' in path:
        cmd_part, _, remainder = path.partition(':')
        path = cmd_part
        if remainder:
            tokens.insert(1, remainder)

    positional: list[str] = []
    named: dict[str, str] = {}
    flags: dict[str, bool] = {}

    for token in tokens[1:]:
        fm = RE_FLAG.match(token)
        if fm:
            flags[fm.group("f").lower()] = fm.group("s") == "+"
            continue

        nm = RE_NAMED.match(token)
        if nm:
            named[nm.group("k").lower()] = nm.group("v").strip("\"'")
            continue

        positional.append(token)

    return ParsedCommand(
        path=path,
        positional=positional,
        named=named,
        flags=flags,
        pin=pin,
        raw=raw,
    )
