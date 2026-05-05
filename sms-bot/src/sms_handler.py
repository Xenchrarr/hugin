import logging
import serial
import time
import uuid

from src.models.sms_message import SmsMessage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WAP binary helpers for direct-HTTP MMS sending
# ---------------------------------------------------------------------------

def _mms_uintvar(n: int) -> bytes:
    """Encode n as a WAP uintvar (7 bits per byte, MSB = continuation flag)."""
    if n == 0:
        return b"\x00"
    parts: list[int] = []
    while n:
        parts.append(n & 0x7F)
        n >>= 7
    parts.reverse()
    return bytes(b | (0x80 if i < len(parts) - 1 else 0) for i, b in enumerate(parts))


def _mms_text(s: str) -> bytes:
    """Null-terminated ASCII text string."""
    return s.encode("ascii", errors="replace") + b"\x00"


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


# WAP-230-WSP well-known content-type short integers
_MMS_MIME_CODE: dict[str, int] = {
    "text/plain":  0x83,
    "image/gif":   0x9D,
    "image/jpeg":  0x9E,
    "image/png":   0x9F,
}


def _mms_mime(mime_type: str) -> bytes:
    code = _MMS_MIME_CODE.get(mime_type.lower())
    if code is not None:
        return bytes([code])
    return (mime_type + "\x00").encode("ascii")


def _build_mms_pdu(
    to_number: str,
    message: str,
    media_bytes: bytes | None,
    mime_type: str = "image/jpeg",
) -> bytes:
    """
    Build a WAP binary OMA MMS m-send-req PDU for direct HTTP delivery.

    OMA MMS header field codes (0x80 | assigned number):
      0x8C Message-Type   0x98 Transaction-Id  0x8D MMS-Version
      0x85 Date           0x97 To              0x89 From
      0x84 Content-Type
    """
    # --- multipart body ---
    parts: list[tuple[bytes, bytes]] = []
    if message:
        parts.append((_mms_mime("text/plain"), message.encode("utf-8")))
    if media_bytes:
        parts.append((_mms_mime(mime_type), media_bytes))

    body = _mms_uintvar(len(parts))
    for ct, data in parts:
        body += _mms_uintvar(len(ct))
        body += _mms_uintvar(len(data))
        body += ct
        body += data

    # --- PDU headers ---
    tx_id = uuid.uuid4().hex[:12]
    pdu  = b"\x8c\x80"                                        # Message-Type: m-send-req
    pdu += b"\x98" + _mms_text(tx_id)                         # Transaction-Id
    pdu += b"\x8d\x92"                                        # MMS-Version 1.2
    pdu += b"\x85" + _mms_long_int(int(time.time()))          # Date
    pdu += b"\x97" + _mms_text(to_number + "/TYPE=PLMN")      # To
    pdu += b"\x89\x01\x81"                                    # From: Insert-Address-Token
    pdu += b"\x84\xa3"                                        # Content-Type: multipart/mixed
    return pdu + body


class SMSHandler:
    def __init__(self, port="/dev/ttyUSB0", baudrate=115200):
        self.ser = serial.Serial(port, baudrate, timeout=2)
        logger.info("Initializing modem")
        self.init_modem()

    def _read_until(self, markers, timeout=5):
        """Read modem response until one of the marker strings appears, or timeout."""
        end_time = time.time() + timeout
        data = ''
        while time.time() < end_time:
            n = self.ser.in_waiting
            if n:
                # UCS2 mode: all modem output is ASCII hex — latin-1 or utf-8 would misinterpret bytes
                data += self.ser.read(n).decode('ascii', errors='ignore')
                for marker in markers:
                    if marker in data:
                        return data
            else:
                time.sleep(0.1)
        return data

    def send_at(self, command, timeout=3):
        self.flush_serial()
        self.ser.write((command + '\r').encode())
        return self._read_until(['\nOK', '\nERROR'], timeout=timeout)

    def flush_serial(self):
        self.ser.reset_input_buffer()

    def init_modem(self):
        # Toggle DTR to reset modem serial state
        self.ser.dtr = False
        time.sleep(0.5)
        self.ser.dtr = True
        time.sleep(1)

        # Cancel any pending SMS input (ESC and Ctrl-Z cover all modes)
        self.ser.write(b'\x1B\x1A\r')
        time.sleep(0.5)
        self.ser.reset_input_buffer()

        # Disable echo with raw write
        self.ser.write(b'ATE0\r')
        time.sleep(1)
        self.ser.reset_input_buffer()

        # Verify modem responds — retry up to 3 times
        for attempt in range(3):
            response = self.send_at("AT", timeout=2)
            if 'OK' in response:
                logger.info("Modem ready (attempt %d)", attempt + 1)
                break
            logger.warning("Modem not responding (attempt %d): %s", attempt + 1, response.strip())
        else:
            logger.error("Modem failed to respond after 3 attempts")

        # Wait for SIM to be ready before any SIM-dependent commands
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
        if 'OK' not in resp:
            logger.error("AT+CSCS=UCS2 failed — Norwegian characters may not work: %s", resp.strip())
        logger.info("Setting SIM storage")
        resp = self.send_at('AT+CPMS="SM","SM","SM"')
        if "ERROR" in resp:
            logger.error("Failed to set SIM storage: %s", resp.strip())
        else:
            logger.info("SIM storage set: %s", resp.strip())
        logger.info("Disabling notifications")
        self.send_at("AT+CNMI=0,0,0,0,0")

        # Purge all messages — SIM may be full from previous failed runs
        logger.info("Deleting all stored messages")
        self.send_at("AT+CMGD=1,4", timeout=5)

        # Wait for network registration before completing init
        logger.info("Waiting for network registration")
        for attempt in range(30):
            resp = self.send_at("AT+CREG?", timeout=3)
            # stat=1 (home) or stat=5 (roaming)
            if "+CREG: 1" in resp or "+CREG: 5" in resp or ",1" in resp or ",5" in resp:
                logger.info("Network registered (attempt %d): %s", attempt + 1, resp.strip())
                break
            logger.debug("Network not registered yet (attempt %d): %s", attempt + 1, resp.strip())
            time.sleep(2)
        else:
            logger.warning("Network not registered after 60s — continuing anyway")

        # Diagnostics
        logger.info("Signal: %s", self.send_at("AT+CSQ", timeout=2).strip())
        logger.info("Network: %s", self.send_at("AT+CREG?", timeout=2).strip())
        logger.info("Storage: %s", self.send_at('AT+CPMS?', timeout=2).strip())

        logger.info("Modem initialization complete")

    def read_messages(self) -> list[SmsMessage]:
        response = self.send_at('AT+CMGL="ALL"', timeout=5)
        if "ERROR" in response:
            logger.error("CMGL failed: %s", response.strip())
            return []
        if response.strip():
            logger.debug("CMGL raw: %s", repr(response))
        return self.parse_messages(response)

    @staticmethod
    def _decode_ucs2(hexstr: str) -> str:
        """Decode a UCS-2 big-endian hex string from the modem to a Python string.

        Falls back to the raw string if the input is not valid hex or has odd length.
        """
        try:
            return bytes.fromhex(hexstr).decode('utf-16-be')
        except (ValueError, UnicodeDecodeError):
            return hexstr

    def parse_messages(self, response) -> list[SmsMessage]:
        messages = []
        lines = response.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('+CMGL:'):
                parts = line.split(',')
                index = parts[0].split(':')[1].strip()
                sender = self._decode_ucs2(parts[2].strip().strip('"'))
                date = parts[4].strip().strip('"') if len(parts) >= 5 else ""

                raw_text = lines[i + 1].strip() if i + 1 < len(lines) else ""
                text = self._decode_ucs2(raw_text)

                messages.append(SmsMessage(
                    index=index,
                    sender=sender,
                    date=date,
                    text=text,
                ))
                i += 2
            else:
                i += 1
        return messages

    def delete_message(self, index):
        logger.info("Deleting message index %s", index)
        response = self.send_at(f"AT+CMGD={index}", timeout=5)
        logger.info("Delete response: %s", response.strip())

    def _send_sms_chunk(self, ucs2_number: str, chunk: str) -> bool:
        """Send a single SMS chunk. Returns True on success."""
        self.flush_serial()
        self.ser.write(f'AT+CMGS="{ucs2_number}"\r'.encode())
        prompt = self._read_until(['>'], timeout=5)
        if '>' not in prompt:
            logger.error("No SMS prompt received: %s", prompt.strip())
            return False

        self.flush_serial()
        ucs2_hex = chunk.encode('utf-16-be').hex().upper()
        self.ser.write((ucs2_hex + '\x1A').encode('ascii'))
        response = self._read_until(['\nOK', '\nERROR', '+CMGS:'], timeout=60)
        if '\nOK' in response or '+CMGS:' in response:
            return True
        logger.error("Failed to send SMS: %s", response.strip())
        return False

    def send_sms(self, number, message):
        logger.info("Sending SMS to %s: %s", number, message)
        ucs2_number = number.encode('utf-16-be').hex().upper()

        chunk_size = 159
        chunks = []
        while message:
            if len(message) <= chunk_size:
                chunks.append(message)
                break
            split_at = message.rfind(' ', 0, chunk_size + 1)
            if split_at <= 0:
                split_at = chunk_size
            chunks.append(message[:split_at])
            message = message[split_at:].lstrip(' ')
        for idx, chunk in enumerate(chunks):
            logger.info("Sending part %d/%d", idx + 1, len(chunks))
            if not self._send_sms_chunk(ucs2_number, chunk):
                return
            if idx < len(chunks) - 1:
                time.sleep(1)
        logger.info("Message sent successfully")

    def send_mms(self, number: str, message: str, media_bytes: bytes, media_mime_type: str = "image/jpeg") -> None:
        """
        Build a WAP binary MMS PDU and POST it to the carrier MMSC via the
        modem's built-in HTTP client (AT+QHTTP*), routing through the MMS APN
        PDP context so the private carrier MMSC is reachable.

        Required env vars:
          MMS_MMSC_URL   — carrier MMSC URL (e.g. http://mms.media)
          MMS_APN        — APN for MMS bearer (e.g. mms)
        Optional env vars:
          MMS_CONTEXT_ID — PDP context slot (default 3)
        """
        import io
        import os

        mmsc_url    = os.environ.get("MMS_MMSC_URL", "")
        mms_apn     = os.environ.get("MMS_APN", "mms")
        mms_context = int(os.environ.get("MMS_CONTEXT_ID", "3"))

        if not mmsc_url:
            logger.error("send_mms: MMS_MMSC_URL is not configured — cannot send MMS")
            return

        # Compress JPEG to stay under a sensible MMS size limit (~300 KB)
        _MMS_MAX_BYTES = 300 * 1024
        if ("jpeg" in media_mime_type or "jpg" in media_mime_type) and len(media_bytes) > _MMS_MAX_BYTES:
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(media_bytes))
                quality = 75
                while quality >= 30:
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=quality, optimize=True)
                    if buf.tell() <= _MMS_MAX_BYTES:
                        media_bytes = buf.getvalue()
                        logger.debug("send_mms: compressed to %d bytes (quality=%d)", len(media_bytes), quality)
                        break
                    quality -= 10
                else:
                    w, h = img.size
                    scale = (_MMS_MAX_BYTES / len(media_bytes)) ** 0.5
                    img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=60, optimize=True)
                    media_bytes = buf.getvalue()
                    logger.debug("send_mms: resized to %d bytes", len(media_bytes))
            except Exception as exc:
                logger.warning("send_mms: image compression failed, using original: %s", exc)

        logger.info("Sending MMS to %s (%d bytes, %s)", number, len(media_bytes), media_mime_type)

        pdu = _build_mms_pdu(number, message, media_bytes, media_mime_type)

        # ── 1. Bring up MMS PDP context on the carrier MMS APN ──────────────
        resp = self.send_at(f'AT+QICSGP={mms_context},1,"{mms_apn}","","",1')
        if 'ERROR' in resp:
            logger.warning("send_mms: QICSGP context %d: %s", mms_context, resp.strip())
        resp = self.send_at(f'AT+QIACT={mms_context}', timeout=30)
        logger.debug("send_mms: QIACT %d: %s", mms_context, resp.strip())

        conn_id = 0
        try:
            # ── 2. Open a raw TCP connection to the MMSC ─────────────────────
            # AT+QHTTP* cannot set Content-Type to application/vnd.wap.mms-message
            # (only accepts integer codes 0-3). Use AT+QIOPEN/QISEND/QIRD instead
            # so we can write the full HTTP request verbatim.
            from urllib.parse import urlparse
            import re as _re

            parsed = urlparse(mmsc_url)
            host = parsed.hostname or mmsc_url
            port = parsed.port or 80
            path = parsed.path or "/"
            if parsed.query:
                path += "?" + parsed.query

            http_req = (
                f"POST {path} HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                f"Content-Type: application/vnd.wap.mms-message\r\n"
                f"Content-Length: {len(pdu)}\r\n"
                f"Accept: application/vnd.wap.mms-message\r\n"
                f"Connection: close\r\n"
                f"\r\n"
            ).encode("ascii") + pdu

            # Close any stale connection on this ID from a previous failed attempt
            self.send_at(f"AT+QICLOSE={conn_id}")
            self.flush_serial()
            self.ser.write(
                f'AT+QIOPEN={mms_context},{conn_id},"TCP","{host}",{port},0,0\r'.encode()
            )
            resp = self._read_until(["+QIOPEN:", "\nERROR"], timeout=30)
            m = _re.search(r"\+QIOPEN:\s*\d+,(\d+)", resp)
            if not m or m.group(1) != "0":
                logger.error("send_mms: QIOPEN failed: %s", resp.strip())
                return

            # ── 3. Send raw HTTP request in chunks ────────────────────────────
            # Never flush between chunks — that would discard incoming server URCs.
            # If the server responds / closes early, break out and read the response.
            # Use 1460-byte chunks (modem max) to minimise the number of round-trips
            # and reduce the window in which a server URC can race with SEND OK.
            CHUNK = 1460
            offset = 0
            send_ok = True

            while offset < len(http_req):
                chunk = http_req[offset:offset + CHUNK]
                self.ser.write(f"AT+QISEND={conn_id},{len(chunk)}\r".encode())
                # 60 s timeout: the EC25's internal TCP send buffer (~16 KB) fills up
                # when the network is slow to ACK. The modem delays the ">" prompt until
                # buffer space is freed — we must wait rather than give up early.
                prompt = self._read_until([">", "ERROR", "+QIURC:"], timeout=60)
                if ">" not in prompt:
                    # No data prompt at all — server responded early, error, or timeout.
                    if "+QIURC:" in prompt:
                        logger.debug("send_mms: server URC at offset %d (no prompt): %s", offset, prompt.strip())
                    elif "ERROR" in prompt:
                        logger.error("send_mms: QISEND error at offset %d: %s", offset, prompt.strip())
                        send_ok = False
                    else:
                        logger.error("send_mms: QISEND no prompt at offset %d: %s", offset, prompt.strip())
                        send_ok = False
                    break
                # Got ">" — proceed even if a URC also arrived in the same read.
                if "+QIURC:" in prompt:
                    logger.debug("send_mms: server URC alongside prompt at offset %d: %s", offset, prompt.strip())
                self.ser.write(chunk)
                sr = self._read_until(["SEND OK", "SEND FAIL", "ERROR", "+QIURC:"], timeout=60)
                # Break immediately if a server URC arrived — even if SEND OK also came
                # in the same read (server responded before we finished sending).
                if "+QIURC:" in sr:
                    logger.debug("send_mms: server URC during send at offset %d: %s", offset, sr.strip())
                    break
                if "SEND OK" not in sr:
                    logger.error("send_mms: QISEND failed at offset %d: %s", offset, sr.strip())
                    send_ok = False
                    break
                offset += len(chunk)

            if not send_ok:
                return

            # ── 4. Read HTTP response headers ─────────────────────────────────
            time.sleep(2)
            http_resp_text = ""
            for _ in range(20):
                self.ser.write(f"AT+QIRD={conn_id},1500\r".encode())
                # Read until modem's final OK to capture all data bytes in one go
                rd = self._read_until(["\nOK", "\nERROR"], timeout=10)
                m2 = _re.search(r"\+QIRD:\s*(\d+)", rd)
                if not m2:
                    break
                n = int(m2.group(1))
                if n == 0:
                    if "\r\n\r\n" in http_resp_text:
                        break
                    time.sleep(0.5)
                    continue
                data_start = rd.find("\r\n", rd.find("+QIRD:")) + 2
                ok_pos = rd.rfind("\r\nOK")
                http_resp_text += rd[data_start:ok_pos] if ok_pos >= 0 else rd[data_start:]
                if "\r\n\r\n" in http_resp_text:
                    break

            m3 = _re.search(r"HTTP/1\.[01]\s+(\d+)", http_resp_text)
            if m3:
                http_status = int(m3.group(1))
                if http_status in (200, 206):
                    logger.info("send_mms: MMS sent to %s — HTTP %d", number, http_status)
                else:
                    header_end = http_resp_text.find("\r\n\r\n")
                    headers = http_resp_text[:header_end] if header_end >= 0 else http_resp_text
                    logger.error(
                        "send_mms: MMSC returned HTTP %d for %s — response: %r",
                        http_status, number, headers.strip(),
                    )
            else:
                logger.error("send_mms: no HTTP status in response: %r", http_resp_text[:300])

        except Exception as exc:
            logger.error("send_mms: exception during MMS send: %s", exc)

        finally:
            # ── 5. Always close TCP connection and deactivate MMS context ─────
            self.send_at(f"AT+QICLOSE={conn_id}", timeout=10)
            self.send_at(f"AT+QIDEACT={mms_context}", timeout=10)

    def close(self):
        self.ser.close()