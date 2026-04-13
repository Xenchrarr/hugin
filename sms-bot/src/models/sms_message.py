from dataclasses import dataclass


@dataclass
class SmsMessage:
    index: str
    sender: str
    date: str
    text: str
