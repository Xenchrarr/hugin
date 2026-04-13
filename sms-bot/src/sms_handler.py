import logging
import serial
import time

from src.models.sms_message import SmsMessage

logger = logging.getLogger(__name__)


class SMSHandler:
    def __init__(self, port="/dev/ttyUSB0", baudrate=9600):
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
                data += self.ser.read(n).decode(errors='ignore')
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

        logger.info("Setting text mode")
        self.send_at("AT+CMGF=1")
        logger.info("Setting SIM storage")
        self.send_at('AT+CPMS="SM"')
        logger.info("Disabling notifications")
        self.send_at("AT+CNMI=0,0,0,0,0")

        # Purge all messages — SIM may be full from previous failed runs
        logger.info("Deleting all stored messages")
        self.send_at("AT+CMGD=1,4", timeout=5)

        # Diagnostics
        logger.info("Signal: %s", self.send_at("AT+CSQ", timeout=2).strip())
        logger.info("Network: %s", self.send_at("AT+CREG?", timeout=2).strip())
        logger.info("Storage: %s", self.send_at('AT+CPMS?', timeout=2).strip())

        logger.info("Modem initialization complete")

    def read_messages(self) -> list[SmsMessage]:
        response = self.send_at('AT+CMGL="ALL"', timeout=5)
        if response.strip():
            logger.debug("CMGL raw: %s", repr(response))
        return self.parse_messages(response)

    def parse_messages(self, response) -> list[SmsMessage]:
        messages = []
        lines = response.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('+CMGL:'):
                parts = line.split(',')
                index = parts[0].split(':')[1].strip()
                sender = parts[2].strip().strip('"')
                date = parts[4].strip().strip('"') if len(parts) >= 5 else ""

                text = lines[i + 1].strip() if i + 1 < len(lines) else ""

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

    def send_sms(self, number, message):
        logger.info("Sending SMS to %s: %s", number, message)
        # Request SMS prompt
        self.flush_serial()
        self.ser.write(f'AT+CMGS="{number}"\r'.encode())
        prompt = self._read_until(['>'], timeout=5)
        if '>' not in prompt:
            logger.error("No SMS prompt received: %s", prompt.strip())
            return

        # Send message body + Ctrl-Z, wait for modem to transmit (up to 60s)
        self.flush_serial()
        self.ser.write((message + '\x1A').encode())
        response = self._read_until(['\nOK', '\nERROR', '+CMGS:'], timeout=60)
        if '\nOK' in response or '+CMGS:' in response:
            logger.info("Message sent successfully")
        else:
            logger.error("Failed to send SMS: %s", response.strip())

    def close(self):
        self.ser.close()