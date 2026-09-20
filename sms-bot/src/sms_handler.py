import io
import csv
import logging
import os
import re
import threading
import time
import uuid
from urllib.parse import urlparse

import serial

from src.models.sms_message import SmsMessage
from src.mms.decoder import MmsNotification, RetrievedMms, decode_retrieved_mms
from src.mms.sms_pdu import decode_sms_deliver_pdu

logger = logging.getLogger(__name__)


_GSM7_ALPHABET = (
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ"
    "\x1bÆæßÉ !\"#¤%&'()*+,-./"
    "0123456789:;<=>?¡"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿"
    "abcdefghijklmnopqrstuvwxyzäöñüà"
)
_GSM7_BASIC = {
    character: index
    for index, character in enumerate(_GSM7_ALPHABET)
    if character != "\x1b"
}
_GSM7_EXTENSION = {
    "\f": 0x0A,
    "^": 0x14,
    "{": 0x28,
    "}": 0x29,
    "\\": 0x2F,
    "[": 0x3C,
    "~": 0x3D,
    "]": 0x3E,
    "|": 0x40,
    "€": 0x65,
}


# ---------------------------------------------------------------------------
# WAP binary helpers for direct-HTTP MMS sending
# ---------------------------------------------------------------------------

def _mms_uintvar(n: int) -> bytes:
    """Encode n as a WAP uintvar: 7 bits per byte, MSB = continuation flag."""
    if n == 0:
        return b"\x00"

    parts: list[int] = []
    while n:
        parts.append(n & 0x7F)
        n >>= 7

    parts.reverse()
    return bytes(
        b | (0x80 if i < len(parts) - 1 else 0)
        for i, b in enumerate(parts)
    )


def _mms_text(s: str) -> bytes:
    """Null-terminated ASCII text string."""
    return s.encode("ascii", errors="replace") + b"\x00"

def _mms_quoted_string(s: str) -> bytes:
    """WSP quoted-string: quote byte + ASCII + null terminator."""
    return b"\x22" + s.encode("ascii", errors="replace") + b"\x00"

def _mms_long_int(n: int) -> bytes:
    """WAP long-integer: one length byte followed by big-endian value bytes."""
    if n == 0:
        return b"\x01\x00"

    value: list[int] = []
    while n:
        value.append(n & 0xFF)
        n >>= 8

    value.reverse()
    return bytes([len(value)] + value)


# WAP-230-WSP well-known content-type short integers.
# application/smil has no standard WAP short code — always encoded as text-string.
_MMS_MIME_CODE: dict[str, int] = {
    "text/plain": 0x83,
    "image/gif": 0x9D,
    "image/jpeg": 0x9E,
    "image/png": 0xA0,
}

# Image MIME type → file extension used in SMIL src attribute
_MMS_IMG_EXT: dict[str, str] = {
    "image/jpeg": "img.jpg",
    "image/png": "img.png",
    "image/gif": "img.gif",
}


def _mms_from_address(number: str) -> bytes:
    """
    Encode an explicit From address in OMA MMS WAP binary format.

    Structure: field-code 0x89 + value-length + Address-Present-Token (0x80)
               + null-terminated address string.

    Normally we prefer Insert-Address-Token instead, so the MMSC inserts the
    sender. Explicit From is only used when MMS_FROM_NUMBER is configured.
    """
    addr_bytes = (number + "/TYPE=PLMN\x00").encode("ascii", errors="replace")
    value = bytes([0x80]) + addr_bytes  # 0x80 = Address-Present-Token
    n = len(value)

    # WAP value-length: 0-30 => single byte; 31+ => 0x1F + uintvar
    if n <= 30:
        length_bytes = bytes([n])
    else:
        length_bytes = bytes([0x1F]) + _mms_uintvar(n)

    return b"\x89" + length_bytes + value


def _mms_mime(mime_type: str) -> bytes:
    code = _MMS_MIME_CODE.get(mime_type.lower())
    if code is not None:
        return bytes([code])
    return (mime_type + "\x00").encode("ascii", errors="replace")


def _wap_content_id(cid: str) -> bytes:
    """
    Encode a Content-ID part-header in WAP binary format.

    WSP header field code for Content-ID is 0x40 → short-form 0xC0.
    Value is a plain null-terminated text-string (no WSP quoted-string
    wrapper) so it matches the start param in Content-Type bytewise.
    Using quoted-string encoding here while the start param uses a plain
    text-string caused phones to fail resolving the SMIL start part.
    """
    return b"\xc0" + cid.encode("ascii", errors="replace") + b"\x00"


def _wap_content_location(location: str) -> bytes:
    """
    Encode a Content-Location part-header in WAP binary format.

    WSP header field code 0x0E → short-form 0x8E.
    Value is a text-string, null-terminated.

    The SMIL src attributes reference these filenames, for example img.jpg
    and txt.txt.
    """
    return b"\x8e" + location.encode("ascii", errors="replace") + b"\x00"


def _build_smil(has_text: bool, has_image: bool, img_src: str = "img.jpg") -> bytes:
    """Build a minimal SMIL 1.0 presentation document for an MMS message."""
    regions: list[str] = []
    par_elements: list[str] = []

    if has_image and has_text:
        regions.append('<region id="image" fit="meet" height="80%" width="100%"/>')
        regions.append('<region id="text" height="20%" width="100%"/>')
        par_elements.append(f'<img src="{img_src}" region="image"/>')
        par_elements.append('<text src="txt.txt" region="text"/>')
    elif has_image:
        regions.append('<region id="image" fit="meet" height="100%" width="100%"/>')
        par_elements.append(f'<img src="{img_src}" region="image"/>')
    elif has_text:
        regions.append('<region id="text" height="100%" width="100%"/>')
        par_elements.append('<text src="txt.txt" region="text"/>')

    region_block = "\n    ".join(regions)
    par_block = "\n    ".join(par_elements)

    smil = (
        "<?xml version=\"1.0\"?>\n"
        "<smil>\n"
        " <head>\n"
        "  <layout>\n"
        "   <root-layout/>\n"
        f"   {region_block}\n"
        "  </layout>\n"
        " </head>\n"
        " <body>\n"
        '  <par dur="5000ms">\n'
        f"   {par_block}\n"
        "  </par>\n"
        " </body>\n"
        "</smil>"
    )
    return smil.encode("utf-8")


def _build_mms_pdu(
    to_number: str,
    message: str,
    media_bytes: bytes | None,
    mime_type: str = "image/jpeg",
    from_number: str | None = None,
) -> bytes:
    """
    Build a WAP binary OMA MMS m-send-req PDU for direct HTTP delivery.

    OMA MMS header field codes:
      0x8C Message-Type
      0x98 Transaction-Id
      0x8D MMS-Version
      0x85 Date
      0x97 To
      0x89 From
      0x84 Content-Type

    The message body is application/vnd.wap.multipart.related with SMIL as the
    start part. Each part has Content-Type, Content-Location and Content-ID.
    """
    img_src = _MMS_IMG_EXT.get(mime_type.lower(), "img.jpg")

    # Build content parts:
    # (WAP content-type, Content-ID, Content-Location filename, data)
    content_parts: list[tuple[bytes, str, str, bytes]] = []

    if message:
        content_parts.append(
            (
                _mms_mime("text/plain"),
                "<txt>",
                "txt.txt",
                message.encode("utf-8"),
            )
        )

    if media_bytes:
        content_parts.append(
            (
                _mms_mime(mime_type),
                "<img>",
                img_src,
                media_bytes,
            )
        )

    # SMIL goes first. It is the multipart/related start part.
    smil_bytes = _build_smil(
        has_text=bool(message),
        has_image=bool(media_bytes),
        img_src=img_src,
    )

    all_parts: list[tuple[bytes, str, str, bytes]] = [
        (
            _mms_mime("application/smil"),
            "<smil>",
            "smil.smil",
            smil_bytes,
        ),
        *content_parts,
    ]

    # Encode WAP multipart body:
    # nEntries + (HeadersLen + DataLen + Headers + Data)*
    body = _mms_uintvar(len(all_parts))

    for content_type, cid, cloc, data in all_parts:
        headers = (
            content_type
            + _wap_content_location(cloc)
            + _wap_content_id(cid)
        )

        body += _mms_uintvar(len(headers))
        body += _mms_uintvar(len(data))
        body += headers
        body += data

    tx_id = uuid.uuid4().hex[:12]

    # Content-Type: application/vnd.wap.multipart.related
    #   type  param (code 0x09 → short 0x89): "application/smil" as text-string
    #   start param (code 0x0A → short 0x8A): "<smil>" as plain null-terminated
    #                                          text-string (no WSP quoted-string
    #                                          wrapper) so it matches the bare
    #                                          Content-ID value exactly.
    #
    # FIX: Previously the start value was encoded via _mms_quoted_string which
    # added a leading 0x22 WSP quote byte, making the param value "<smil>"
    # while the Content-ID field stored the value as a quoted-string whose
    # logical value is also <smil>. Some MMSCs compare these bytewise rather
    # than logically, so the extra 0x22 caused a mismatch. Using a plain
    # null-terminated text-string for both the start param and the CID value
    # (after stripping the WSP quoted-string wrapper) gives consistent matching.
    #
    # 0xB3 = application/vnd.wap.multipart.related
    mt_params = (
        b"\x89" + b"application/smil\x00"   # type  param: text-string
        + b"\x8a" + b"<smil>\x00"           # start param: plain text-string
    )
    mt_value = bytes([0xB3]) + mt_params
    mt_vlen = len(mt_value)

    if mt_vlen <= 30:
        content_type_field = b"\x84" + bytes([mt_vlen]) + mt_value
    else:
        content_type_field = b"\x84\x1f" + _mms_uintvar(mt_vlen) + mt_value

    pdu = b"\x8c\x80"                                      # Message-Type: m-send-req
    pdu += b"\x98" + _mms_text(tx_id)                       # Transaction-Id
    pdu += b"\x8d\x92"                                      # MMS-Version: 1.2
    pdu += b"\x85" + _mms_long_int(int(time.time()) + (3600 * 2))             # Date (+1h to compensate Sonim DST bug: device applies CET instead of CEST)
    pdu += b"\x97" + _mms_text(to_number + "/TYPE=PLMN")    # To

    if from_number:
        pdu += _mms_from_address(from_number)                # From: explicit MSISDN
    else:
        pdu += b"\x89\x01\x81"                              # From: Insert-Address-Token

    pdu += b"\x8a\x80"                                      # Message-Class: Personal
    pdu += b"\x8f\x81"                                      # Priority: Normal
    pdu += b"\x86\x81"                                      # Delivery-Report: No
    pdu += b"\x90\x81"                                      # Read-Reply: No

    # X-Mms-Expiry: relative 7 days.
    # Field code 0x88, value-length byte, 0x81 = relative token, then Long-integer seconds.
    # Must use Long-integer (not uintvar): WSP Integer-value encoding requires it.
    exp_val = b"\x81" + _mms_long_int(7 * 24 * 3600)
    pdu += b"\x88" + bytes([len(exp_val)]) + exp_val

    pdu += content_type_field

    logger.debug("send_mms: PDU headers+body hex: %s", (pdu + body).hex())
    logger.debug("send_mms: top-level content-type field hex: %s", content_type_field.hex())

    return pdu + body


class SMSHandler:
    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 115200):
        self._port = port
        self._baudrate = baudrate
        self.ser = serial.Serial(port, baudrate, timeout=2)
        self._modem_lock = threading.RLock()
        self._own_number: str = ""
        self._last_successful_send: float | None = None
        self._last_send_error: str = ""
        self._last_send_uncertain: bool = False
        self._last_call_by_number: dict[str, float] = {}
        logger.info("Initializing modem")
        self.init_modem()

    # -----------------------------------------------------------------------
    # Generic serial / AT helpers
    # -----------------------------------------------------------------------

    def _read_until(self, markers: list[str], timeout: float = 5) -> str:
        """
        Read modem response until one of the marker strings appears, or timeout.

        latin-1 is used intentionally so bytes are preserved 1:1 when QIRD
        returns binary-ish data. Normal AT responses are ASCII-compatible.
        """
        end_time = time.time() + timeout
        data = ""

        while time.time() < end_time:
            n = self.ser.in_waiting
            if n:
                data += self.ser.read(n).decode("latin-1", errors="ignore")
                for marker in markers:
                    if marker in data:
                        return data
            else:
                time.sleep(0.05)

        return data

    def flush_serial(self) -> None:
        self.ser.reset_input_buffer()

    def _recover_serial_locked(self) -> bool:
        """Replace a failed USB serial descriptor and reinitialize the modem."""
        logger.warning("Reconnecting to modem on %s", self._port)
        try:
            self.ser.close()
        except Exception:
            logger.debug("Could not close failed modem descriptor", exc_info=True)

        try:
            self.ser = serial.Serial(self._port, self._baudrate, timeout=2)
            self.init_modem()
        except (OSError, serial.SerialException):
            logger.exception("Could not reconnect to modem on %s", self._port)
            try:
                self.ser.close()
            except Exception:
                pass
            return False

        logger.info("Reconnected to modem on %s", self._port)
        return True

    def cancel_pending_input(self) -> None:
        """Cancel pending SMS/TCP input mode if the modem is stuck waiting for data."""
        try:
            self.ser.write(b"\x1b")  # ESC
            time.sleep(0.2)
            self.ser.write(b"\r")
            time.sleep(0.2)
        except Exception:
            logger.exception("Failed to cancel pending modem input")

    def send_at(self, command: str, timeout: float = 3, flush: bool = True) -> str:
        """
        Send an AT command and read until OK/ERROR.

        For normal SMS/admin commands, flushing before the command is fine.
        During MMS socket transfer, use send_at_no_flush() instead so we do not
        discard important +QIURC notifications from the modem.
        """
        if flush:
            self.flush_serial()

        self.ser.write((command + "\r").encode("ascii", errors="replace"))
        return self._read_until(["\nOK", "\nERROR", "ERROR"], timeout=timeout)

    def send_at_no_flush(self, command: str, timeout: float = 5) -> str:
        """Send AT command without clearing pending modem URCs first."""
        return self.send_at(command, timeout=timeout, flush=False)

    # -----------------------------------------------------------------------
    # Modem init
    # -----------------------------------------------------------------------

    def init_modem(self) -> None:
        # Toggle DTR to reset modem serial state.
        self.ser.dtr = False
        time.sleep(0.5)
        self.ser.dtr = True
        time.sleep(1)

        # Cancel any pending input mode.
        self.ser.write(b"\x1B\x1A\r")
        time.sleep(0.5)
        self.ser.reset_input_buffer()

        # Disable echo with raw write.
        self.ser.write(b"ATE0\r")
        time.sleep(1)
        self.ser.reset_input_buffer()

        # Verify modem responds.
        for attempt in range(3):
            response = self.send_at("AT", timeout=2)
            if "OK" in response:
                logger.info("Modem ready (attempt %d)", attempt + 1)
                break

            logger.warning(
                "Modem not responding (attempt %d): %s",
                attempt + 1,
                response.strip(),
            )
        else:
            logger.error("Modem failed to respond after 3 attempts")

        # Wait for SIM.
        logger.info("Waiting for SIM ready")
        for attempt in range(10):
            resp = self.send_at("AT+CPIN?", timeout=3)
            if "+CPIN: READY" in resp:
                logger.info("SIM ready (attempt %d)", attempt + 1)
                break

            logger.warning("SIM not ready (attempt %d): %s", attempt + 1, resp.strip())
            time.sleep(2)
        else:
            logger.error("SIM not ready after 10 attempts — storage commands may fail")

        logger.info("Setting text mode")
        self.send_at("AT+CMGF=1")

        logger.info("Setting character set to UCS2")
        resp = self.send_at('AT+CSCS="UCS2"')
        if "OK" not in resp:
            logger.error(
                "AT+CSCS=UCS2 failed — Norwegian characters may not work: %s",
                resp.strip(),
            )

        logger.info("Setting SIM storage")
        resp = self.send_at('AT+CPMS="SM","SM","SM"')
        if "ERROR" in resp:
            logger.error("Failed to set SIM storage: %s", resp.strip())
        else:
            logger.info("SIM storage set: %s", resp.strip())

        logger.info("Disabling notifications")
        self.send_at("AT+CNMI=0,0,0,0,0")

        logger.info("Waiting for network registration")
        for attempt in range(30):
            resp = self.send_at("AT+CREG?", timeout=3)
            if "+CREG: 1" in resp or "+CREG: 5" in resp or ",1" in resp or ",5" in resp:
                logger.info("Network registered (attempt %d): %s", attempt + 1, resp.strip())
                break

            logger.debug("Network not registered yet (attempt %d): %s", attempt + 1, resp.strip())
            time.sleep(2)
        else:
            logger.warning("Network not registered after 60s — continuing anyway")

        logger.info("Signal: %s", self.send_at("AT+CSQ", timeout=2).strip())
        logger.info("Network: %s", self.send_at("AT+CREG?", timeout=2).strip())
        logger.info("Storage: %s", self.send_at('AT+CPMS?', timeout=2).strip())

        # Query own MSISDN for diagnostics only.
        # We do not auto-use it as MMS From because some MMSCs prefer
        # Insert-Address-Token.
        cnum_resp = self.send_at("AT+CNUM", timeout=3)
        m_cnum = re.search(r'\+CNUM:\s*"[^"]*","([^"]+)"', cnum_resp)

        if m_cnum:
            self._own_number = m_cnum.group(1)
            logger.info("Own MSISDN: %s", self._own_number)
        else:
            logger.warning(
                "AT+CNUM did not return a number — MMS will use Insert-Address-Token: %s",
                cnum_resp.strip(),
            )

        logger.info("Modem initialization complete")

    # -----------------------------------------------------------------------
    # SMS read / delete
    # -----------------------------------------------------------------------

    def read_messages(self) -> list[SmsMessage | MmsNotification]:
        with self._modem_lock:
            try:
                return self._read_messages_locked()
            except (OSError, serial.SerialException):
                logger.exception("Serial I/O failed while polling stored messages")
                self._recover_serial_locked()
                return []

    def _read_messages_locked(self) -> list[SmsMessage | MmsNotification]:
        # PDU mode is required to retain the binary WAP-push payload used for
        # inbound MMS. It also lets one parser handle both text SMS and MMS
        # notifications without first corrupting binary messages in text mode.
        try:
            mode_response = self.send_at("AT+CMGF=0", timeout=3)
            if "ERROR" in mode_response:
                logger.error("Could not enter SMS PDU mode: %s", mode_response.strip())
                return []
            response = self.send_at("AT+CMGL=4", timeout=10)
            if "ERROR" in response:
                logger.error("CMGL failed in PDU mode: %s", response.strip())
                return []
            if response.strip():
                logger.debug("CMGL PDU raw: %s", repr(response))
            return self.parse_pdu_messages(response)
        finally:
            # Outbound SMS code uses text mode with UCS-2 phone numbers and
            # payloads, so always restore that state before releasing the lock.
            self.send_at("AT+CMGF=1", timeout=3)
            self.send_at('AT+CSCS="UCS2"', timeout=3)

    @staticmethod
    def parse_pdu_messages(response: str) -> list[SmsMessage | MmsNotification]:
        messages: list[SmsMessage | MmsNotification] = []
        status_names = {
            "0": "REC UNREAD",
            "1": "REC READ",
            "2": "STO UNSENT",
            "3": "STO SENT",
        }
        lines = response.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line.startswith("+CMGL:"):
                i += 1
                continue
            try:
                parts = next(csv.reader([line.split(":", 1)[1]], skipinitialspace=True))
                index = parts[0].strip()
                raw_status = parts[1].strip().strip('"').upper()
                status = status_names.get(raw_status, raw_status)
                pdu_hex = lines[i + 1].strip()
            except (IndexError, csv.Error):
                logger.warning("Could not parse PDU CMGL entry: %r", line)
                i += 1
                continue
            i += 2
            if not status.startswith("REC "):
                continue
            try:
                messages.append(decode_sms_deliver_pdu(pdu_hex, index=index, status=status))
            except (ValueError, IndexError) as exc:
                # Keep the raw modem entry in storage. It may be a format we do
                # not support yet and must not be silently destroyed.
                logger.warning("Could not decode stored SMS index %s: %s", index, exc)
        return messages

    @staticmethod
    def _decode_ucs2(hexstr: str) -> str:
        """Decode a UCS-2 big-endian hex string from the modem."""
        try:
            return bytes.fromhex(hexstr).decode("utf-16-be")
        except (ValueError, UnicodeDecodeError):
            return hexstr

    def parse_messages(self, response: str) -> list[SmsMessage]:
        messages: list[SmsMessage] = []
        lines = response.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            if line.startswith("+CMGL:"):
                try:
                    header = line.split(":", 1)[1].strip()
                    parts = next(csv.reader([header], skipinitialspace=True))
                except (IndexError, csv.Error):
                    logger.warning("Could not parse CMGL header: %r", line)
                    i += 1
                    continue

                if len(parts) < 3:
                    logger.warning("Incomplete CMGL header: %r", line)
                    i += 1
                    continue

                index = parts[0].strip()
                status = parts[1].strip().strip('"').upper()

                # CMGL=ALL can also return STO SENT and STO UNSENT entries. They
                # are not inbound commands and must never be executed.
                if not status.startswith("REC "):
                    i += 2
                    continue

                sender = self._decode_ucs2(parts[2].strip().strip('"'))
                date = parts[4].strip().strip('"') if len(parts) >= 5 else ""

                raw_text = lines[i + 1].strip() if i + 1 < len(lines) else ""
                text = self._decode_ucs2(raw_text)

                messages.append(
                    SmsMessage(
                        index=index,
                        sender=sender,
                        date=date,
                        text=text,
                        status=status,
                    )
                )
                i += 2
            else:
                i += 1

        return messages

    def delete_message(self, index: str) -> bool:
        with self._modem_lock:
            try:
                return self._delete_message_locked(index)
            except (OSError, serial.SerialException):
                logger.exception("Serial I/O failed while deleting message %s", index)
                self._recover_serial_locked()
                return False

    def _delete_message_locked(self, index: str) -> bool:
        logger.info("Deleting message index %s", index)
        response = self.send_at(f"AT+CMGD={index}", timeout=5)
        logger.info("Delete response: %s", response.strip())
        return "OK" in response and "ERROR" not in response

    def poll_incoming_calls(self) -> list[str]:
        """Hang up configured one-ring triggers and return their caller numbers once."""
        with self._modem_lock:
            try:
                response = self.send_at("AT+CLCC", timeout=3)
            except (OSError, serial.SerialException):
                logger.exception("Serial I/O failed while polling incoming calls")
                self._recover_serial_locked()
                return []
            numbers: list[str] = []
            now = time.time()
            for line in response.splitlines():
                # +CLCC: <id>,<dir>,<stat>,<mode>,<mpty>,"<number>",<type>
                match = re.search(r'\+CLCC:\s*\d+\s*,\s*1\s*,\s*4\s*,[^\"]*"([^\"]+)"', line)
                if not match:
                    continue
                number = match.group(1)
                if re.fullmatch(r"[0-9A-Fa-f]+", number or "") and len(number) % 4 == 0:
                    number = self._decode_ucs2(number)
                if now - self._last_call_by_number.get(number, 0) < 60:
                    continue
                self._last_call_by_number[number] = now
                numbers.append(number)
            if numbers:
                try:
                    self.send_at("ATH", timeout=3)
                except (OSError, serial.SerialException):
                    logger.exception("Serial I/O failed while hanging up incoming call")
                    self._recover_serial_locked()
            self._last_call_by_number = {
                number: seen for number, seen in self._last_call_by_number.items()
                if now - seen < 300
            }
            return numbers

    # -----------------------------------------------------------------------
    # SMS send
    # -----------------------------------------------------------------------

    def _send_sms_chunk(self, recipient: str, chunk: str, use_gsm7: bool) -> bool:
        """Send a single SMS chunk."""
        self.flush_serial()
        self.ser.write(f'AT+CMGS="{recipient}"\r'.encode("ascii"))

        prompt = self._read_until([">"], timeout=5)
        if ">" not in prompt:
            logger.error("No SMS prompt received: %s", prompt.strip())
            return False

        self.flush_serial()
        # Append a sacrificial trailing space before Ctrl-Z. Some modem firmware
        # drops the final character in its input buffer; the space absorbs that.
        if use_gsm7:
            body = self._gsm7_encode(chunk)
            if body is None:
                raise ValueError("GSM-7 chunk contains an unsupported character")
            self.ser.write(body + b" \x1a")
        else:
            ucs2_hex = chunk.encode("utf-16-be").hex().upper()
            self.ser.write((ucs2_hex + "0020\x1A").encode("ascii"))

        # From this point the modem may have accepted the part even if its
        # acknowledgement is lost or sms-hub is interrupted.
        self._last_send_uncertain = True

        response = self._read_until(["\nOK", "\nERROR", "+CMGS:", "ERROR"], timeout=60)
        if "\nOK" in response or "+CMGS:" in response:
            return True

        logger.error("Failed to send SMS: %s", response.strip())
        return False

    def send_sms(self, number: str, message: str) -> bool:
        with self._modem_lock:
            self._last_send_uncertain = False
            result = self._send_sms_locked(number, message)
            if result:
                self._last_successful_send = time.time()
                self._last_send_error = ""
                self._last_send_uncertain = False
            else:
                self._last_send_error = "modem did not accept SMS"
            return result

    @property
    def last_send_uncertain(self) -> bool:
        """Whether the most recent failed send may have reached the carrier."""
        return self._last_send_uncertain

    def get_health(self) -> dict:
        """Probe modem, SIM, and mobile-network readiness."""
        with self._modem_lock:
            try:
                modem_response = self.send_at("AT", timeout=2)
                modem_ready = "OK" in modem_response
                sim_response = self.send_at("AT+CPIN?", timeout=3)
                sim_ready = "+CPIN: READY" in sim_response

                registration_response = self.send_at("AT+CEREG?", timeout=3)
                if "+CEREG:" not in registration_response:
                    registration_response = self.send_at("AT+CREG?", timeout=3)
                registration_match = re.search(
                    r"\+(?:CE|C)REG:\s*(?:\d+\s*,\s*)?(\d+)", registration_response
                )
                registration = int(registration_match.group(1)) if registration_match else -1
                network_ready = registration in (1, 5)

                signal_response = self.send_at("AT+CSQ", timeout=3)
                signal_match = re.search(r"\+CSQ:\s*(\d+)", signal_response)
                signal = int(signal_match.group(1)) if signal_match else None
                ready = modem_ready and sim_ready and network_ready
                return {
                    "ready": ready,
                    "modem": modem_ready,
                    "sim": sim_ready,
                    "network": network_ready,
                    "registration": registration,
                    "signal": signal,
                    "last_successful_send": self._last_successful_send,
                    "last_send_error": self._last_send_error,
                    "error": "" if ready else "modem, SIM, or network is not ready",
                }
            except Exception as exc:
                logger.exception("Modem health probe failed")
                return {
                    "ready": False,
                    "modem": False,
                    "sim": False,
                    "network": False,
                    "signal": None,
                    "last_successful_send": self._last_successful_send,
                    "last_send_error": self._last_send_error,
                    "error": str(exc),
                }

    def _send_sms_locked(self, number: str, message: str) -> bool:
        logger.info("Sending SMS to %s: %s", number, message)
        use_gsm7 = self._gsm7_encode(message) is not None
        charset = "GSM" if use_gsm7 else "UCS2"
        response = self.send_at(f'AT+CSCS="{charset}"', timeout=3)
        if "OK" not in response:
            logger.error("Could not select %s for outbound SMS: %s", charset, response.strip())
            return False

        recipient = number if use_gsm7 else number.encode("utf-16-be").hex().upper()
        # GSM-7 has 160 septets and UCS-2 has 70 code units. Reserve one unit
        # for the sacrificial trailing space appended by _send_sms_chunk.
        chunk_size = 159 if use_gsm7 else 69
        chunks: list[str] = []

        while message:
            prefix_end = self._encoded_prefix_end(message, chunk_size, use_gsm7)
            if prefix_end == len(message):
                chunks.append(message)
                break

            split_at = max(
                message.rfind(" ", 0, prefix_end + 1),
                message.rfind("\n", 0, prefix_end + 1),
            )
            if split_at <= 0:
                split_at = prefix_end

            chunks.append(message[:split_at])
            message = message[split_at:].lstrip()

        for idx, chunk in enumerate(chunks):
            logger.info("Sending part %d/%d", idx + 1, len(chunks))
            if not self._send_sms_chunk(recipient, chunk, use_gsm7):
                return False
            self._last_send_uncertain = True

            if idx < len(chunks) - 1:
                time.sleep(1)

        logger.info("Message sent successfully")
        return True

    @staticmethod
    def _encoded_prefix_end(text: str, max_units: int, use_gsm7: bool) -> int:
        """Return the largest prefix fitting in the selected SMS encoding."""
        units = 0
        for index, character in enumerate(text):
            if use_gsm7:
                encoded = SMSHandler._gsm7_encode(character)
                if encoded is None:
                    return index
                character_units = len(encoded)
            else:
                character_units = len(character.encode("utf-16-be")) // 2
            if units + character_units > max_units:
                return index
            units += character_units
        return len(text)

    @staticmethod
    def _gsm7_encode(text: str) -> bytes | None:
        encoded = bytearray()
        for character in text:
            if character in _GSM7_BASIC:
                encoded.append(_GSM7_BASIC[character])
            elif character in _GSM7_EXTENSION:
                encoded.extend((0x1B, _GSM7_EXTENSION[character]))
            else:
                return None
        return bytes(encoded)

    # -----------------------------------------------------------------------
    # MMS helper methods
    # -----------------------------------------------------------------------

    def _compress_jpeg_if_needed(
        self,
        media_bytes: bytes,
        media_mime_type: str,
        max_bytes: int,
    ) -> bytes:
        if "jpeg" not in media_mime_type.lower() and "jpg" not in media_mime_type.lower():
            return media_bytes

        if len(media_bytes) <= max_bytes:
            return media_bytes

        try:
            from PIL import Image

            img = Image.open(io.BytesIO(media_bytes))
            quality = 75

            while quality >= 30:
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=quality, optimize=True)

                if buf.tell() <= max_bytes:
                    compressed = buf.getvalue()
                    logger.debug(
                        "send_mms: compressed to %d bytes (quality=%d)",
                        len(compressed),
                        quality,
                    )
                    return compressed

                quality -= 10

            width, height = img.size
            scale = (max_bytes / len(media_bytes)) ** 0.5
            new_size = (
                max(1, int(width * scale)),
                max(1, int(height * scale)),
            )

            img = img.resize(new_size, Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=60, optimize=True)
            resized = buf.getvalue()

            logger.debug("send_mms: resized to %d bytes", len(resized))
            return resized

        except Exception as exc:
            logger.warning("send_mms: image compression failed, using original: %s", exc)
            return media_bytes

    def _query_send_state(self, conn_id: int) -> tuple[int, int, int] | None:
        """
        Query Quectel TCP send counters.

        Returns:
            (total_send_length, acked_bytes, unacked_bytes)
        """
        resp = self.send_at_no_flush(f"AT+QISEND={conn_id},0", timeout=5)
        logger.debug("send_mms: QISEND state raw: %s", resp.strip())

        m = re.search(r"\+QISEND:\s*(\d+),(\d+),(\d+)", resp)
        if not m:
            return None

        return int(m.group(1)), int(m.group(2)), int(m.group(3))

    def _wait_for_tcp_drain(
        self,
        conn_id: int,
        max_unacked: int = 4096,
        timeout: float = 30,
    ) -> bool:
        """Wait until modem TCP unacked bytes are below threshold."""
        end_time = time.time() + timeout

        while time.time() < end_time:
            state = self._query_send_state(conn_id)
            if state is None:
                # Some firmware variants may not support this query properly.
                # Do not fail the send only because diagnostics are unavailable.
                return True

            total, acked, unacked = state
            logger.debug(
                "send_mms: TCP send state total=%d acked=%d unacked=%d",
                total,
                acked,
                unacked,
            )

            if unacked <= max_unacked:
                return True

            time.sleep(0.5)

        logger.warning(
            "send_mms: TCP drain timeout; unacked bytes stayed above %d",
            max_unacked,
        )
        return False

    def _log_pdp_diagnostics(self, context_id: int) -> None:
        """Best-effort diagnostic dump when the PDP context drops."""
        try:
            logger.error(
                "send_mms: CEER after PDP drop: %s",
                self.send_at_no_flush("AT+CEER", timeout=5).strip(),
            )
        except Exception:
            logger.exception("send_mms: failed reading CEER")

        try:
            logger.error(
                "send_mms: CGACT after PDP drop: %s",
                self.send_at_no_flush("AT+CGACT?", timeout=5).strip(),
            )
        except Exception:
            logger.exception("send_mms: failed reading CGACT")

        try:
            logger.error(
                "send_mms: QIACT after PDP drop: %s",
                self.send_at_no_flush("AT+QIACT?", timeout=5).strip(),
            )
        except Exception:
            logger.exception("send_mms: failed reading QIACT")

    def _log_socket_diagnostics(self, conn_id: int) -> None:
        """Best-effort diagnostic dump before closing a failing socket."""
        try:
            logger.error(
                "send_mms: QISTATE: %s",
                self.send_at_no_flush(f"AT+QISTATE=1,{conn_id}", timeout=5).strip(),
            )
        except Exception:
            logger.exception("send_mms: failed reading QISTATE")

        try:
            logger.error(
                "send_mms: QISEND state: %s",
                self.send_at_no_flush(f"AT+QISEND={conn_id},0", timeout=5).strip(),
            )
        except Exception:
            logger.exception("send_mms: failed reading QISEND state")

        try:
            logger.error(
                "send_mms: QIGETERROR: %s",
                self.send_at_no_flush("AT+QIGETERROR", timeout=5).strip(),
            )
        except Exception:
            logger.exception("send_mms: failed reading QIGETERROR")

        try:
            logger.error(
                "send_mms: QIRD after failure: %s",
                repr(self.send_at_no_flush(f"AT+QIRD={conn_id},1500", timeout=5)[:500]),
            )
        except Exception:
            logger.exception("send_mms: failed reading QIRD")

    def _read_qird_payload(
        self,
        conn_id: int,
        max_bytes: int = 1500,
        timeout: float = 10,
    ) -> bytes | None:
        """Read one QIRD response without interpreting its binary payload."""
        self.ser.write(f"AT+QIRD={conn_id},{max_bytes}\r".encode("ascii"))
        deadline = time.time() + timeout
        response = bytearray()
        payload_start: int | None = None
        payload_length: int | None = None

        while time.time() < deadline:
            available = self.ser.in_waiting
            if available:
                response.extend(self.ser.read(available))

                if payload_start is None:
                    match = re.search(rb"\+QIRD:\s*(\d+)\r?\n", response)
                    if match:
                        payload_length = int(match.group(1))
                        payload_start = match.end()
                    elif b"\r\nERROR\r\n" in response:
                        logger.error("receive_mms: QIRD failed: %r", bytes(response))
                        return None

                if payload_start is not None and payload_length is not None:
                    payload_end = payload_start + payload_length
                    if len(response) >= payload_end:
                        trailer = response[payload_end:]
                        if b"\r\nERROR" in trailer:
                            logger.error("receive_mms: QIRD failed: %r", bytes(response))
                            return None
                        if b"\r\nOK" in trailer:
                            return bytes(response[payload_start:payload_end])
            else:
                time.sleep(0.05)

        logger.error(
            "receive_mms: timed out reading QIRD response (received %d bytes)",
            len(response),
        )
        return None

    def _read_http_response(self, conn_id: int, timeout_rounds: int = 20) -> bytes:
        """Read a binary HTTP response from the modem socket using QIRD."""
        http_response = bytearray()
        empty_rounds = 0

        for _ in range(timeout_rounds):
            payload = self._read_qird_payload(conn_id)
            if payload is None:
                break

            if not payload:
                empty_rounds += 1
                if b"\r\n\r\n" in http_response:
                    break
                if empty_rounds >= 10:
                    break
                time.sleep(0.5)
                continue

            empty_rounds = 0
            http_response.extend(payload)

            header_end = http_response.find(b"\r\n\r\n")
            if header_end >= 0:
                length_match = re.search(
                    rb"(?im)^Content-Length:\s*(\d+)",
                    http_response[:header_end],
                )
                if length_match:
                    expected = int(length_match.group(1))
                    if len(http_response[header_end + 4:]) >= expected:
                        break

        return bytes(http_response)

    def _send_socket_bytes(
        self,
        conn_id: int,
        payload: bytes,
        chunk_size: int,
        max_unacked: int,
    ) -> bool:
        offset = 0
        while offset < len(payload):
            chunk = payload[offset:offset + chunk_size]
            self.ser.write(f"AT+QISEND={conn_id},{len(chunk)}\r".encode("ascii"))
            prompt = self._read_until([">", "ERROR", "+QIURC:"], timeout=30)
            if ">" not in prompt:
                self.cancel_pending_input()
                logger.error("MMS HTTP request did not receive a QISEND prompt: %r", prompt)
                return False
            self.ser.write(chunk)
            result = self._read_until(
                ["SEND OK", "SEND FAIL", "ERROR", "+QIURC:"],
                timeout=90,
            )
            if "SEND OK" not in result:
                logger.error("MMS HTTP socket send failed: %r", result)
                return False
            offset += len(chunk)
            self._wait_for_tcp_drain(conn_id, max_unacked=max_unacked, timeout=30)
        return True

    @staticmethod
    def _decode_chunked_http_body(body: bytes) -> bytes:
        decoded = bytearray()
        pos = 0
        while pos < len(body):
            line_end = body.find(b"\n", pos)
            if line_end < 0:
                raise ValueError("truncated chunk size")
            size_line = body[pos:line_end]
            if size_line.endswith(b"\r"):
                size_line = size_line[:-1]
            size_text = size_line.split(b";", 1)[0].strip()
            size = int(size_text, 16)
            pos = line_end + 1
            if size == 0:
                return bytes(decoded)
            if pos + size > len(body):
                raise ValueError("truncated HTTP chunk")
            decoded.extend(body[pos:pos + size])
            pos += size
            if body[pos:pos + 2] == b"\r\n":
                pos += 2
            elif body[pos:pos + 1] == b"\n":
                pos += 1
            else:
                context = body[pos:pos + 16].hex()
                raise ValueError(
                    f"invalid HTTP chunk delimiter at byte {pos}: {context}"
                )
        raise ValueError("chunked HTTP response has no terminating chunk")

    def retrieve_mms(self, notification: MmsNotification) -> RetrievedMms | None:
        with self._modem_lock:
            try:
                raw = self._download_mms_locked(notification.content_location)
                if raw is None:
                    return None
                return decode_retrieved_mms(raw, fallback_caption=notification.subject)
            except Exception as exc:
                logger.exception(
                    "receive_mms: failed to retrieve/decode transaction %s: %s",
                    notification.transaction_id,
                    exc,
                )
                return None

    def _download_mms_locked(self, content_location: str) -> bytes | None:
        """Download an inbound MMS PDU through the carrier MMS bearer."""
        parsed = urlparse(content_location)
        if parsed.scheme.lower() != "http" or not parsed.hostname:
            logger.error("receive_mms: unsupported content location: %s", content_location)
            return None

        mms_apn = os.environ.get("MMS_APN", "mms").strip()
        mms_context = int(os.environ.get("MMS_CONTEXT_ID", "3"))
        proxy_host = os.environ.get("MMS_PROXY_HOST", "").strip()
        proxy_port_raw = os.environ.get("MMS_PROXY_PORT", "").strip()
        proxy_port = int(proxy_port_raw) if proxy_port_raw else None
        max_bytes = int(os.environ.get("MMS_RECEIVE_MAX_BYTES", str(5 * 1024 * 1024)))
        tcp_chunk = int(os.environ.get("MMS_TCP_CHUNK", "1024"))
        max_unacked = int(os.environ.get("MMS_MAX_UNACKED", "4096"))
        user_agent = os.environ.get("MMS_USER_AGENT", "Android-Mms/2.0").strip()
        wap_profile = os.environ.get("MMS_WAP_PROFILE", "").strip()

        host = parsed.hostname
        port = parsed.port or 80
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        connect_host = proxy_host or host
        connect_port = proxy_port or port
        request_target = content_location if proxy_host else path

        headers = [
            f"GET {request_target} HTTP/1.1",
            f"Host: {host}",
            "Accept: application/vnd.wap.mms-message, */*",
            f"User-Agent: {user_agent}",
            "Connection: close",
        ]
        if wap_profile:
            headers.append(f"X-WAP-Profile: {wap_profile}")
        request_bytes = ("\r\n".join(headers) + "\r\n\r\n").encode("ascii")

        conn_id = 0
        try:
            self.send_at('AT+CSCS="IRA"', timeout=3)
            self.send_at(f"AT+QICLOSE={conn_id}", timeout=10)
            self.send_at(f"AT+QIDEACT={mms_context}", timeout=45)
            self.send_at(
                f'AT+QICSGP={mms_context},1,"{mms_apn}","","",1',
                timeout=5,
            )
            activated = self.send_at(f"AT+QIACT={mms_context}", timeout=160)
            if "ERROR" in activated:
                logger.error("receive_mms: could not activate MMS PDP context: %s", activated.strip())
                return None

            self.flush_serial()
            self.ser.write(
                (
                    f'AT+QIOPEN={mms_context},{conn_id},"TCP",'
                    f'"{connect_host}",{connect_port},0,0\r'
                ).encode("ascii")
            )
            opened = self._read_until(["+QIOPEN:", "ERROR"], timeout=160)
            match = re.search(r"\+QIOPEN:\s*\d+,(\d+)", opened)
            if not match or match.group(1) != "0":
                logger.error("receive_mms: QIOPEN failed: %s", opened.strip())
                return None

            if not self._send_socket_bytes(conn_id, request_bytes, tcp_chunk, max_unacked):
                return None
            response = self._read_http_response(
                conn_id,
                timeout_rounds=max(20, (max_bytes // 1500) + 10),
            )
            header_end = response.find(b"\r\n\r\n")
            if header_end < 0:
                logger.error("receive_mms: invalid HTTP response")
                return None
            header_bytes = response[:header_end]
            status_match = re.search(rb"HTTP/1\.[01]\s+(\d+)", header_bytes)
            if not status_match or int(status_match.group(1)) != 200:
                logger.error("receive_mms: MMSC GET failed: %r", header_bytes[:500])
                return None
            body = response[header_end + 4:]
            if b"transfer-encoding: chunked" in header_bytes.lower():
                body = self._decode_chunked_http_body(body)
            if len(body) > max_bytes:
                logger.error("receive_mms: payload exceeds %d-byte limit", max_bytes)
                return None
            content_length = re.search(rb"(?im)^Content-Length:\s*(\d+)", header_bytes)
            if content_length and len(body) < int(content_length.group(1)):
                logger.error(
                    "receive_mms: incomplete body (%d/%s bytes)",
                    len(body),
                    content_length.group(1).decode("ascii"),
                )
                return None
            logger.info("receive_mms: downloaded %d bytes", len(body))
            return body
        finally:
            try:
                self.send_at(f"AT+QICLOSE={conn_id}", timeout=10)
                self.send_at(f"AT+QIDEACT={mms_context}", timeout=20)
                self.send_at('AT+CSCS="UCS2"', timeout=3)
            except Exception:
                logger.exception("receive_mms: failed to restore modem state")

    # -----------------------------------------------------------------------
    # MMS send
    # -----------------------------------------------------------------------

    def send_mms(
        self,
        number: str,
        message: str,
        media_bytes: bytes,
        media_mime_type: str = "image/jpeg",
    ) -> bool:
        with self._modem_lock:
            self._last_send_uncertain = False
            result = self._send_mms_locked(number, message, media_bytes, media_mime_type)
            if result:
                self._last_successful_send = time.time()
                self._last_send_error = ""
                self._last_send_uncertain = False
            else:
                self._last_send_error = "modem did not accept MMS"
            return result

    def _send_mms_locked(
        self,
        number: str,
        message: str,
        media_bytes: bytes,
        media_mime_type: str = "image/jpeg",
    ) -> bool:
        """
        Build a WAP binary MMS PDU and POST it to the carrier MMSC via raw TCP.

        Required environment variables:
          MMS_MMSC_URL   Example: http://mms.media
          MMS_APN        Example: mms

        Optional environment variables:
          MMS_CONTEXT_ID       Default: 3
          MMS_MAX_BYTES        Default: 307200
          MMS_TCP_CHUNK        Default: 1024
          MMS_MAX_UNACKED      Default: 4096
          MMS_PROXY_HOST       Optional MMS proxy host
          MMS_PROXY_PORT       Optional MMS proxy port
          MMS_FROM_NUMBER      Optional explicit From number
        """
        mmsc_url = os.environ.get("MMS_MMSC_URL", "").strip()
        mms_apn = os.environ.get("MMS_APN", "mms").strip()
        mms_context = int(os.environ.get("MMS_CONTEXT_ID", "3"))

        mms_proxy_host = os.environ.get("MMS_PROXY_HOST", "").strip()
        mms_proxy_port_raw = os.environ.get("MMS_PROXY_PORT", "").strip()
        mms_proxy_port = int(mms_proxy_port_raw) if mms_proxy_port_raw else None

        # Prefer explicit From address so the MMSC can identify the sender and
        # generate a WAP Push notification to the recipient.
        # Priority: MMS_FROM_NUMBER env var > SIM's own MSISDN > Insert-Address-Token.
        mms_from_number = os.environ.get("MMS_FROM_NUMBER", "").strip() or None
        if mms_from_number is None and self._own_number:
            mms_from_number = self._own_number
            logger.debug("send_mms: using SIM MSISDN as From: %s", mms_from_number)

        max_mms_bytes = int(os.environ.get("MMS_MAX_BYTES", str(300 * 1024)))
        tcp_chunk = int(os.environ.get("MMS_TCP_CHUNK", "1024"))
        max_unacked = int(os.environ.get("MMS_MAX_UNACKED", "4096"))

        if not mmsc_url:
            logger.error("send_mms: MMS_MMSC_URL is not configured — cannot send MMS")
            return False

        if tcp_chunk < 128 or tcp_chunk > 1460:
            logger.warning("send_mms: invalid MMS_TCP_CHUNK=%d, using 1024", tcp_chunk)
            tcp_chunk = 1024

        if media_bytes and "png" in media_mime_type.lower():
            try:
                from PIL import Image

                buf = io.BytesIO()
                Image.open(io.BytesIO(media_bytes)).convert("RGB").save(buf, format="JPEG", quality=85, optimize=True)
                media_bytes = buf.getvalue()
                media_mime_type = "image/jpeg"
                logger.debug("send_mms: converted PNG to JPEG (%d bytes)", len(media_bytes))
            except Exception as exc:
                logger.warning("send_mms: PNG→JPEG conversion failed, using original: %s", exc)

        media_bytes = self._compress_jpeg_if_needed(
            media_bytes=media_bytes,
            media_mime_type=media_mime_type,
            max_bytes=max_mms_bytes,
        )

        logger.info(
            "Sending MMS to %s (%d bytes, %s)",
            number,
            len(media_bytes),
            media_mime_type,
        )

        pdu = _build_mms_pdu(
            to_number=number,
            message=message,
            media_bytes=media_bytes,
            mime_type=media_mime_type,
            from_number=mms_from_number,
        )

        parsed = urlparse(mmsc_url)
        host = parsed.hostname or mmsc_url
        port = parsed.port or 80
        path = parsed.path or "/"

        if parsed.query:
            path += "?" + parsed.query

        # If an MMS proxy is configured, open TCP to the proxy and use an
        # absolute request target. Without proxy, open TCP directly to MMSC and
        # use the normal origin-form path.
        connect_host = mms_proxy_host or host
        connect_port = mms_proxy_port or port
        request_target = mmsc_url if mms_proxy_host else path

        mms_user_agent = os.environ.get("MMS_USER_AGENT", "Android-Mms/2.0").strip()
        mms_wap_profile = os.environ.get("MMS_WAP_PROFILE", "").strip()             

        http_headers = [
            f"POST {request_target} HTTP/1.1",
            f"Host: {host}",
            "Content-Type: application/vnd.wap.mms-message",
            f"Content-Length: {len(pdu)}",
            "Accept: application/vnd.wap.mms-message",
            f"User-Agent: {mms_user_agent}",
            "Connection: close",
        ]

        if mms_wap_profile:
            http_headers.append(f"X-WAP-Profile: {mms_wap_profile}")

        http_req = ("\r\n".join(http_headers) + "\r\n\r\n").encode("ascii") + pdu

        logger.debug(
            "send_mms: MMSC host=%s port=%d path=%s connect_host=%s connect_port=%d "
            "proxy=%s pdu=%d bytes http_req=%d bytes chunk=%d max_unacked=%d",
            host,
            port,
            path,
            connect_host,
            connect_port,
            bool(mms_proxy_host),
            len(pdu),
            len(http_req),
            tcp_chunk,
            max_unacked,
        )

        conn_id = 0
        success = False

        try:
            # Use IRA while doing internet/socket commands. Restore UCS2 in finally.
            self.send_at('AT+CSCS="IRA"', timeout=3)

            # Start from a clean MMS PDP/socket state.
            self.send_at(f"AT+QICLOSE={conn_id}", timeout=10)
            self.send_at(f"AT+QIDEACT={mms_context}", timeout=45)
            time.sleep(1)

            # Bring up MMS PDP context on the carrier MMS APN.
            resp = self.send_at(
                f'AT+QICSGP={mms_context},1,"{mms_apn}","","",1',
                timeout=5,
            )
            if "ERROR" in resp:
                logger.warning(
                    "send_mms: QICSGP context %d: %s",
                    mms_context,
                    resp.strip(),
                )

            resp = self.send_at(f"AT+QIACT={mms_context}", timeout=160)
            logger.debug("send_mms: QIACT %d: %s", mms_context, resp.strip())

            resp = self.send_at("AT+QIACT?", timeout=5)
            logger.debug("send_mms: QIACT?: %s", resp.strip())

            # Close any stale connection on this ID from a previous failed attempt.
            self.send_at(f"AT+QICLOSE={conn_id}", timeout=10)

            self.flush_serial()
            self.ser.write(
                (
                    f'AT+QIOPEN={mms_context},{conn_id},"TCP",'
                    f'"{connect_host}",{connect_port},0,0\r'
                ).encode("ascii")
            )

            resp = self._read_until(["+QIOPEN:", "ERROR", "ERROR"], timeout=160)
            logger.debug("send_mms: QIOPEN response: %s", resp.strip())

            if '"pdpdeact"' in resp:
                logger.error(
                    "send_mms: PDP context %d was deactivated during QIOPEN: %s",
                    mms_context,
                    resp.strip(),
                )
                self._log_pdp_diagnostics(mms_context)
                return False

            m = re.search(r"\+QIOPEN:\s*\d+,(\d+)", resp)
            if not m or m.group(1) != "0":
                logger.error("send_mms: QIOPEN failed: %s", resp.strip())
                self._log_socket_diagnostics(conn_id)
                return False

            logger.info(
                "send_mms: socket open, starting upload to %s:%d, request size=%d",
                connect_host,
                connect_port,
                len(http_req),
            )

            offset = 0

            while offset < len(http_req):
                chunk = http_req[offset:offset + tcp_chunk]

                logger.debug(
                    "send_mms: requesting QISEND prompt offset=%d chunk=%d",
                    offset,
                    len(chunk),
                )

                self.ser.write(f"AT+QISEND={conn_id},{len(chunk)}\r".encode("ascii"))
                prompt = self._read_until([">", "ERROR", "+QIURC:"], timeout=30)
                logger.debug("send_mms: QISEND prompt response: %r", prompt)

                if ">" not in prompt:
                    logger.error(
                        "send_mms: QISEND no prompt at offset %d/%d: %r",
                        offset,
                        len(http_req),
                        prompt.strip(),
                    )

                    self.cancel_pending_input()
                    self._log_socket_diagnostics(conn_id)
                    return False

                self.ser.write(chunk)
                # The MMSC may receive this request even if the response never
                # makes it back to us. Do not automatically resend on failure.
                self._last_send_uncertain = True

                sr = self._read_until(
                    ["SEND OK", "OK", "SEND FAIL", "ERROR", "+QIURC:"],
                    timeout=90,
                )
                logger.debug("send_mms: QISEND send response: %r", sr)

                if not sr.strip():
                    sr = self._read_until(
                        ["SEND OK", "OK", "SEND FAIL", "ERROR", "+QIURC:"],
                        timeout=5,
                    )
                    logger.debug("send_mms: QISEND late send response: %r", sr)

                if "+QIURC:" in sr:
                    logger.warning(
                        "send_mms: modem URC during send at offset %d/%d: %s",
                        offset,
                        len(http_req),
                        sr.strip(),
                    )

                    early_resp = self._read_http_response(conn_id, timeout_rounds=5)
                    if early_resp:
                        logger.error("send_mms: early HTTP response: %r", early_resp[:500])

                    self._log_socket_diagnostics(conn_id)
                    return False

                chunk_end = offset + len(chunk)
                chunk_accepted = "SEND OK" in sr

                if not chunk_accepted and "OK" in sr:
                    state = self._query_send_state(conn_id)
                    if state:
                        total, acked, unacked = state
                        if total >= chunk_end and acked >= chunk_end:
                            logger.debug(
                                "send_mms: QISEND returned plain OK, but counters confirm "
                                "chunk accepted: total=%d acked=%d unacked=%d",
                                total,
                                acked,
                                unacked,
                            )
                            chunk_accepted = True

                if not chunk_accepted:
                    logger.error(
                        "send_mms: QISEND failed at offset %d/%d: %s",
                        offset,
                        len(http_req),
                        sr.strip(),
                    )
                    self._log_socket_diagnostics(conn_id)
                    return False

                offset += len(chunk)

                self._wait_for_tcp_drain(
                    conn_id=conn_id,
                    max_unacked=max_unacked,
                    timeout=30,
                )

                time.sleep(0.05)

            logger.info("send_mms: finished uploading HTTP request, %d bytes", len(http_req))

            # Give the MMSC a moment to respond, then read HTTP response headers.
            time.sleep(2)
            http_resp_text = self._read_http_response(conn_id)

            m_status = re.search(r"HTTP/1\.[01]\s+(\d+)", http_resp_text)
            if not m_status:
                logger.error("send_mms: no HTTP status in response: %r", http_resp_text[:500])
                return False

            http_status = int(m_status.group(1))
            header_end = http_resp_text.find("\r\n\r\n")
            headers = http_resp_text[:header_end] if header_end >= 0 else http_resp_text

            if http_status in (200, 201, 202, 204, 206):
                body_start = header_end + 4 if header_end >= 0 else 0
                body_bytes = http_resp_text[body_start:].encode("latin-1")

                logger.debug(
                    "send_mms: MMSC response headers: %r",
                    headers.strip(),
                )

                if body_bytes:
                    logger.debug(
                        "send_mms: m-send-conf body (%d bytes): %s",
                        len(body_bytes),
                        body_bytes.hex(),
                    )

                    # Response-Status field code 0x92.
                    # Values:
                    # 0x80 = OK
                    # 0x81 = Error-unspecified
                    # 0x82 = Error-service-denied
                    # 0x83 = Error-message-format-corrupt
                    # 0x84 = Error-sending-address-unresolved
                    # 0x85 = Error-message-not-found
                    # 0x86 = Error-network-problem
                    # 0x87 = Error-content-not-accepted
                    # 0x88 = Error-unsupported-message
                    rs_names = {
                        0x80: "OK",
                        0x81: "Error-unspecified",
                        0x82: "Error-service-denied",
                        0x83: "Error-message-format-corrupt",
                        0x84: "Error-sending-address-unresolved",
                        0x85: "Error-message-not-found",
                        0x86: "Error-network-problem",
                        0x87: "Error-content-not-accepted",
                        0x88: "Error-unsupported-message",
                    }

                    for i in range(len(body_bytes) - 1):
                        # Skip 0x92 that follows 0x8D because that is MMS-Version 1.2,
                        # not the Response-Status field.
                        if body_bytes[i] == 0x92 and (i == 0 or body_bytes[i - 1] != 0x8D):
                            rs_val = body_bytes[i + 1]
                            rs_name = rs_names.get(rs_val, f"Unknown-0x{rs_val:02x}")

                            if rs_val == 0x80:
                                logger.info("send_mms: m-send-conf Response-Status: %s", rs_name)
                            else:
                                logger.error(
                                    "send_mms: m-send-conf Response-Status: %s (0x%02x) — "
                                    "MMS may not be delivered to %s",
                                    rs_name,
                                    rs_val,
                                    number,
                                )
                            break

                    # Message-Id field code 0x8B — null-terminated ASCII string.
                    mid_pos = body_bytes.find(b"\x8b")
                    if mid_pos >= 0 and mid_pos + 1 < len(body_bytes):
                        nul = body_bytes.find(b"\x00", mid_pos + 1)
                        if nul > mid_pos + 1:
                            message_id = body_bytes[mid_pos + 1:nul].decode(
                                "ascii",
                                errors="replace",
                            )
                            logger.info(
                                "send_mms: MMSC Message-Id: %s (use for carrier delivery trace)",
                                message_id,
                            )

                logger.info(
                    "send_mms: MMS accepted by MMSC for %s — HTTP %d",
                    number,
                    http_status,
                )
                success = True
                return True

            logger.error(
                "send_mms: MMSC returned HTTP %d for %s — response: %r",
                http_status,
                number,
                headers.strip(),
            )
            return False

        except Exception as exc:
            logger.exception("send_mms: exception during MMS send: %s", exc)
            return False

        finally:
            try:
                self.send_at(f"AT+QICLOSE={conn_id}", timeout=10)
            except Exception:
                logger.exception("send_mms: failed to close TCP connection")

            try:
                self.send_at(f"AT+QIDEACT={mms_context}", timeout=10)
            except Exception:
                logger.exception("send_mms: failed to deactivate MMS context")

            try:
                self.send_at('AT+CSCS="UCS2"', timeout=3)
            except Exception:
                logger.exception("send_mms: failed to restore UCS2 character set")

            if not success:
                logger.error("send_mms: failed for %s", number)

    def close(self) -> None:
        with self._modem_lock:
            self.ser.close()
