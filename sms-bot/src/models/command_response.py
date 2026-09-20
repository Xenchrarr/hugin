from dataclasses import dataclass, field


@dataclass
class CommandResponse:
    text: str
    image_bytes: bytes | None = None
    image_mime: str = "image/png"
    ack_hub_delivery_ids: list[int] = field(default_factory=list)
