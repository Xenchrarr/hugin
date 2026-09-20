import threading
import unittest
from unittest.mock import Mock, patch

from src.sms_handler import SMSHandler


class _FailedSerial:
    def __init__(self):
        self.closed = False

    def reset_input_buffer(self):
        raise OSError(5, "Input/output error")

    def close(self):
        self.closed = True


class SerialRecoveryTests(unittest.TestCase):
    def test_call_poll_reconnects_after_usb_io_error(self):
        handler = SMSHandler.__new__(SMSHandler)
        handler._port = "/dev/ttyUSB0"
        handler._baudrate = 115200
        handler._modem_lock = threading.RLock()
        handler._last_call_by_number = {}
        failed_serial = _FailedSerial()
        replacement_serial = Mock()
        handler.ser = failed_serial
        handler.init_modem = Mock()

        with patch("src.sms_handler.serial.Serial", return_value=replacement_serial) as open_serial:
            self.assertEqual([], handler.poll_incoming_calls())

        self.assertTrue(failed_serial.closed)
        self.assertIs(handler.ser, replacement_serial)
        open_serial.assert_called_once_with("/dev/ttyUSB0", 115200, timeout=2)
        handler.init_modem.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
