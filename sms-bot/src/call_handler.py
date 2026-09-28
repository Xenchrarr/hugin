from __future__ import annotations

import logging
import re
import threading
import time

import serial

from src.sms_handler import SMSHandler

logger = logging.getLogger(__name__)


class CallHandler:
    """Voice-call operations sharing the modem connection with SMSHandler."""

    def __init__(self, modem: SMSHandler):
        self.modem = modem
        self._last_call_by_number: dict[str, float] = {}
        self._cancel_requested = threading.Event()
        self._active = threading.Event()

    @property
    def active(self) -> bool:
        return self._active.is_set()

    def cancel(self) -> bool:
        if not self.active:
            return False
        self._cancel_requested.set()
        return True

    def poll_incoming_calls(self) -> list[str]:
        """Hang up configured one-ring triggers and return caller numbers once."""
        with self.modem._modem_lock:
            try:
                response = self.modem.send_at("AT+CLCC", timeout=3)
            except (OSError, serial.SerialException):
                logger.exception("Serial I/O failed while polling incoming calls")
                self.modem._recover_serial_locked()
                return []
            numbers: list[str] = []
            now = time.time()
            for line in response.splitlines():
                match = re.search(r'\+CLCC:\s*\d+\s*,\s*1\s*,\s*4\s*,[^\"]*"([^\"]+)"', line)
                if not match:
                    continue
                number = match.group(1)
                if re.fullmatch(r"[0-9A-Fa-f]+", number or "") and len(number) % 4 == 0:
                    number = self.modem._decode_ucs2(number)
                if now - self._last_call_by_number.get(number, 0) < 60:
                    continue
                self._last_call_by_number[number] = now
                numbers.append(number)
            if numbers:
                try:
                    self.modem.send_at("ATH", timeout=3)
                except (OSError, serial.SerialException):
                    logger.exception("Serial I/O failed while hanging up incoming call")
                    self.modem._recover_serial_locked()
            self._last_call_by_number = {
                number: seen for number, seen in self._last_call_by_number.items()
                if now - seen < 300
            }
            return numbers

    def ring_call(self, number: str, ring_seconds: int = 20) -> dict:
        with self.modem._modem_lock:
            self._cancel_requested.clear()
            self._active.set()
            try:
                return self._ring_call_locked(number, ring_seconds)
            except (OSError, serial.SerialException):
                logger.exception("Serial I/O failed while calling %s", self._masked(number))
                self.modem._recover_serial_locked()
                return {"ok": False, "status": "modem_error", "uncertain": True}
            finally:
                self._active.clear()
                self._cancel_requested.clear()

    def _ring_call_locked(self, number: str, ring_seconds: int) -> dict:
        ring_seconds = max(5, min(int(ring_seconds), 60))
        logger.info("Starting ring-only call to %s for up to %d seconds", self._masked(number), ring_seconds)
        self.modem.flush_serial()
        self.modem.ser.write(f"ATD{number};\r".encode("ascii"))
        response = self.modem._read_until(
            ["\nOK", "\nERROR", "ERROR", "NO CARRIER", "NO DIALTONE", "BUSY"], timeout=15
        )
        initial = self._terminal_status(response)
        if initial:
            return {"ok": False, "status": initial, "uncertain": False}
        if "OK" not in response.upper():
            return {"ok": False, "status": "rejected", "uncertain": False}

        status = "dialing"
        ring_elapsed = 0
        empty_polls = 0
        saw_call = False
        try:
            for _ in range(ring_seconds + 20):
                if self._cancel_requested.is_set():
                    status = "cancelled"
                    break
                time.sleep(1)
                call_list = self.modem.send_at_no_flush("AT+CLCC", timeout=3)
                logger.debug("Outgoing call CLCC: %r", call_list)
                terminal = self._terminal_status(call_list)
                if terminal:
                    status = terminal
                    break
                states = [int(m.group(1)) for m in re.finditer(
                    r"\+CLCC:\s*\d+\s*,\s*0\s*,\s*(\d+)\s*,\s*0\s*,", call_list
                )]
                if states:
                    saw_call, empty_polls = True, 0
                else:
                    empty_polls += 1
                if 0 in states:
                    status = "answered"
                    break
                if 3 in states:
                    status = "ringing"
                    ring_elapsed += 1
                    if ring_elapsed >= ring_seconds:
                        status = "ring_timeout"
                        break
                elif 2 in states:
                    status = "dialing"
                elif not states and empty_polls >= (3 if saw_call else 10):
                    status = "ended"
                    break
            else:
                status = "setup_timeout"
            diagnostics = self.failure_diagnostics() if status not in {"answered", "ring_timeout", "cancelled"} else {}
        finally:
            self.modem.send_at_no_flush("ATH", timeout=3)

        voice_ready = self._wait_for_voice_registration()

        logger.info("Ring-only call to %s finished with status %s", self._masked(number), status)
        return {
            "ok": status in {"answered", "ring_timeout"},
            "status": status,
            "uncertain": status in {"modem_error", "setup_timeout"},
            "diagnostics": diagnostics,
            "voice_ready": voice_ready,
        }

    def _wait_for_voice_registration(self, timeout_seconds: int = 20) -> bool:
        for _ in range(max(1, timeout_seconds // 2)):
            response = self.modem.send_at_no_flush("AT+CREG?", timeout=3)
            if re.search(r"\+CREG:\s*(?:\d+\s*,\s*)?[15]", response):
                return True
            time.sleep(2)
        logger.warning("Voice registration did not recover after call")
        return False

    def voice_health(self) -> dict:
        with self.modem._modem_lock:
            responses = {command: self.modem.send_at(command, timeout=5).strip() for command in (
                "AT+CPIN?", "AT+CREG?", "AT+CEREG?", "AT+CSQ", "AT+QNWINFO", "AT+COPS?", 'AT+QCFG="ims"'
            )}
        voice_registered = bool(re.search(r"\+CREG:\s*(?:\d+\s*,\s*)?[15]", responses["AT+CREG?"]))
        return {"ready": voice_registered and "READY" in responses["AT+CPIN?"], "active": self.active, "modem": responses}

    def failure_diagnostics(self) -> dict:
        diagnostics = {}
        for command in ("AT+CEER", "AT+CREG?", "AT+CEREG?", "AT+QNWINFO", "AT+COPS?", 'AT+QCFG="ims"'):
            try:
                diagnostics[command] = self.modem.send_at_no_flush(command, timeout=5).strip()
            except Exception as exc:
                diagnostics[command] = f"error: {exc}"
        logger.warning("Call failure diagnostics: %s", diagnostics)
        return diagnostics

    @staticmethod
    def _terminal_status(response: str) -> str | None:
        upper = response.upper()
        if "BUSY" in upper:
            return "busy"
        if "NO CARRIER" in upper:
            return "no_carrier"
        if "NO DIALTONE" in upper:
            return "no_dialtone"
        if "ERROR" in upper:
            return "rejected"
        return None

    @staticmethod
    def _masked(number: str) -> str:
        return f"***{number[-4:]}" if len(number) >= 4 else "***"
