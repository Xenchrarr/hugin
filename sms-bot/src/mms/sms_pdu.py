from __future__ import annotations

from datetime import datetime

from src.mms.decoder import MmsNotification, decode_mms_notification
from src.models.sms_message import SmsMessage


_GSM7 = (
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ !\"#¤%&'()*+,-./"
    "0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿"
    "abcdefghijklmnopqrstuvwxyzäöñüà"
)
_GSM7_EXT = {0x0A: "\f", 0x14: "^", 0x28: "{", 0x29: "}", 0x2F: "\\", 0x3C: "[", 0x3D: "~", 0x3E: "]", 0x40: "|", 0x65: "€"}


def _semi_octets(data: bytes, digits: int) -> str:
    result = ""
    for byte in data:
        result += f"{byte & 0x0F:X}{byte >> 4:X}"
    return result[:digits].replace("F", "")


def _timestamp(data: bytes) -> str:
    if len(data) != 7:
        return ""
    values = [_semi_octets(bytes([b]), 2) for b in data[:6]]
    try:
        return datetime(
            2000 + int(values[0]), int(values[1]), int(values[2]),
            int(values[3]), int(values[4]), int(values[5]),
        ).isoformat()
    except ValueError:
        return ""


def _decode_gsm7(data: bytes, count: int, bit_offset: int = 0) -> str:
    chars: list[str] = []
    escaped = False
    for i in range(count):
        bit = bit_offset + i * 7
        byte_index = bit // 8
        shift = bit % 8
        if byte_index >= len(data):
            break
        value = (data[byte_index] >> shift) & 0x7F
        if shift > 1 and byte_index + 1 < len(data):
            value |= (data[byte_index + 1] << (8 - shift)) & 0x7F
        if escaped:
            chars.append(_GSM7_EXT.get(value, "?"))
            escaped = False
        elif value == 0x1B:
            escaped = True
        else:
            chars.append(_GSM7[value] if value < len(_GSM7) else "?")
    return "".join(chars)


def _application_port(udh: bytes) -> int | None:
    pos = 0
    while pos + 2 <= len(udh):
        iei = udh[pos]
        length = udh[pos + 1]
        value = udh[pos + 2:pos + 2 + length]
        if len(value) != length:
            break
        if iei == 0x05 and length == 4:
            return int.from_bytes(value[:2], "big")
        if iei == 0x04 and length == 2:
            return value[0]
        pos += 2 + length
    return None


def decode_sms_deliver_pdu(
    pdu_hex: str,
    index: str,
    status: str,
) -> SmsMessage | MmsNotification:
    pdu = bytes.fromhex(pdu_hex.strip())
    if not pdu:
        raise ValueError("empty SMS PDU")
    pos = 1 + pdu[0]
    first_octet = pdu[pos]
    pos += 1
    if first_octet & 0x03 != 0:
        raise ValueError("PDU is not SMS-DELIVER")

    address_len = pdu[pos]
    toa = pdu[pos + 1]
    pos += 2
    address_bytes = (address_len + 1) // 2
    sender = _semi_octets(pdu[pos:pos + address_bytes], address_len)
    if toa & 0x70 == 0x10:
        sender = "+" + sender
    pos += address_bytes

    pos += 1  # PID
    dcs = pdu[pos]
    pos += 1
    date = _timestamp(pdu[pos:pos + 7])
    pos += 7
    user_length = pdu[pos]
    pos += 1
    user_data = pdu[pos:]

    udh = b""
    payload = user_data
    header_octets = 0
    if first_octet & 0x40:
        if not user_data:
            raise ValueError("UDHI set with empty user data")
        header_octets = user_data[0] + 1
        if header_octets > len(user_data):
            raise ValueError("truncated SMS user-data header")
        udh = user_data[1:header_octets]
        payload = user_data[header_octets:]

    if _application_port(udh) == 2948:
        transaction_id, original_sender, url, subject = decode_mms_notification(payload)
        return MmsNotification(
            index=index,
            status=status,
            sender=original_sender,
            date=date,
            transaction_id=transaction_id,
            content_location=url,
            subject=subject,
        )

    coding = dcs & 0x0C
    if coding == 0x08:
        text = payload.decode("utf-16-be", errors="replace")
    elif coding == 0x04:
        text = payload.decode("latin-1", errors="replace")
    else:
        header_septets = (header_octets * 8 + 6) // 7
        septets = max(0, user_length - header_septets)
        padding = (7 - (header_octets * 8) % 7) % 7 if header_octets else 0
        text = _decode_gsm7(payload, septets, padding)

    return SmsMessage(index=index, sender=sender, date=date, text=text, status=status)
