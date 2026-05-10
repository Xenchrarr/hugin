from dataclasses import dataclass, field


@dataclass
class CommandResponse:
    text: str
    image_bytes: bytes | None = None
    image_mime: str = "image/png"
