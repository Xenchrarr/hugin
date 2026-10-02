import re


def normalize_phone(number: str) -> str:
    """Canonicalize common E.164 presentation variants without guessing a country."""
    value = str(number or "").strip()
    if not value:
        return ""
    compact = re.sub(r"[\s().-]", "", value)
    if compact.startswith("00"):
        compact = "+" + compact[2:]
    if compact.startswith("+"):
        return compact if compact[1:].isdigit() else value
    return compact if compact.isdigit() else value

