from dataclasses import dataclass


@dataclass
class MediaRelayResult:
    handled: bool
    response: str = ""
