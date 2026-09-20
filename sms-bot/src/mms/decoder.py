from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class MmsNotification:
    index: str
    status: str
    sender: str
    date: str
    transaction_id: str
    content_location: str
    subject: str = ""


@dataclass
class RetrievedMms:
    image_bytes: bytes
    image_mime: str
    caption: str = ""


def decode_uintvar(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    for _ in range(5):
        if offset >= len(data):
            raise ValueError("truncated uintvar")
        byte = data[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, offset
    raise ValueError("uintvar is too long")


def _ascii_string_after(data: bytes, field: int) -> str:
    pos = data.find(bytes([field]))
    if pos < 0 or pos + 1 >= len(data):
        return ""
    pos += 1
    first = data[pos]
    if first <= 30:
        end = min(len(data), pos + 1 + first)
        value = data[pos + 1:end]
        if value and value[0] >= 0x80:
            value = value[1:]
    else:
        end = data.find(b"\x00", pos)
        value = data[pos:end if end >= 0 else len(data)]
    return value.rstrip(b"\x00").decode("utf-8", errors="replace")


def decode_mms_notification(wap_push: bytes) -> tuple[str, str, str, str]:
    """Return transaction id, original sender, content URL and subject."""
    if len(wap_push) < 4:
        raise ValueError("truncated WAP push")
    if wap_push[1] not in (0x06, 0x07):
        raise ValueError("not a WSP push PDU")

    header_length, offset = decode_uintvar(wap_push, 2)
    mms_offset = offset + header_length
    if mms_offset >= len(wap_push):
        raise ValueError("WSP push has no MMS payload")
    mms = wap_push[mms_offset:]
    if b"\x8c\x82" not in mms:
        raise ValueError("not an MMS notification indication")

    url_match = re.search(rb"https?://[^\x00\r\n]+", mms)
    if not url_match:
        raise ValueError("MMS notification has no content location")

    sender_match = re.search(rb"(\+?[0-9]{5,20})/TYPE=PLMN", mms)
    sender = sender_match.group(1).decode("ascii") if sender_match else ""
    transaction_id = _ascii_string_after(mms, 0x98)
    subject = _ascii_string_after(mms, 0x96)
    return transaction_id, sender, url_match.group(0).decode("ascii"), subject


def _part_mime(headers: bytes, payload: bytes) -> str:
    lower = headers.lower()
    if payload.startswith(b"\xff\xd8\xff") or b"image/jpeg" in lower or b"image/jpg" in lower:
        return "image/jpeg"
    if payload.startswith(b"\x89PNG\r\n\x1a\n") or b"image/png" in lower:
        return "image/png"
    if payload.startswith((b"GIF87a", b"GIF89a")) or b"image/gif" in lower:
        return "image/gif"
    if b"text/plain" in lower or headers[:1] == b"\x83":
        return "text/plain"
    return "application/octet-stream"


def _parse_multipart_at(data: bytes, offset: int) -> list[tuple[bytes, bytes]] | None:
    try:
        count, pos = decode_uintvar(data, offset)
        if count < 1 or count > 16:
            return None
        parts: list[tuple[bytes, bytes]] = []
        for _ in range(count):
            headers_len, pos = decode_uintvar(data, pos)
            payload_len, pos = decode_uintvar(data, pos)
            if headers_len < 1 or pos + headers_len + payload_len > len(data):
                return None
            headers = data[pos:pos + headers_len]
            pos += headers_len
            payload = data[pos:pos + payload_len]
            pos += payload_len
            parts.append((headers, payload))
        if any(byte not in b"\x00\r\n" for byte in data[pos:]):
            return None
        return parts
    except (IndexError, ValueError):
        return None


def decode_retrieved_mms(data: bytes, fallback_caption: str = "") -> RetrievedMms:
    """Extract the first supported image and optional text from an MMS PDU.

    The MMS header set varies by carrier, so the decoder locates a structurally
    valid WAP multipart body rather than relying on a fixed header order.
    """
    candidates: list[tuple[bytes, bytes]] | None = None
    for offset in range(len(data)):
        parsed = _parse_multipart_at(data, offset)
        if parsed and any(_part_mime(h, p).startswith("image/") for h, p in parsed):
            candidates = parsed
            break
    if not candidates:
        raise ValueError("MMS payload contains no supported multipart image")

    image = b""
    image_mime = ""
    caption = ""
    for headers, payload in candidates:
        mime = _part_mime(headers, payload)
        if mime.startswith("image/") and not image:
            image = payload
            image_mime = mime
        elif mime == "text/plain" and not caption:
            caption = payload.decode("utf-8", errors="replace").strip("\x00\r\n ")

    if not image:
        raise ValueError("MMS payload contains no supported image")
    return RetrievedMms(image_bytes=image, image_mime=image_mime, caption=caption or fallback_caption)
