import unittest
from unittest.mock import patch

from src.sms_handler import SMSHandler


class SmsStorageTests(unittest.TestCase):
    def setUp(self):
        self.handler = SMSHandler.__new__(SMSHandler)

    def test_parser_keeps_read_and_unread_received_messages(self):
        response = (
            '+CMGL: 1,"REC UNREAD","002B0034003700310032",,"26/09/17,10:00:00+08"\r\n'
            '00680065006C0070\r\n'
            '+CMGL: 2,"REC READ","002B0034003700310032",,"26/09/17,10:01:00+08"\r\n'
            '00740067002F006C006900730074\r\n'
            'OK\r\n'
        )

        messages = self.handler.parse_messages(response)

        self.assertEqual(["help", "tg/list"], [m.text for m in messages])
        self.assertEqual(["REC UNREAD", "REC READ"], [m.status for m in messages])

    def test_parser_ignores_messages_stored_for_sending(self):
        response = (
            '+CMGL: 3,"STO SENT","002B0034003700390039",,"26/09/17,10:02:00+08"\r\n'
            '00740067002F00730065006E006400200031002000680069\r\n'
            'OK\r\n'
        )

        self.assertEqual([], self.handler.parse_messages(response))

    @patch("src.sms_handler.time.sleep", return_value=None)
    def test_modem_initialization_does_not_bulk_delete_storage(self, _sleep):
        class FakeSerial:
            dtr = True

            @staticmethod
            def write(_data):
                return None

            @staticmethod
            def reset_input_buffer():
                return None

        handler = SMSHandler.__new__(SMSHandler)
        handler.ser = FakeSerial()
        handler._own_number = ""
        commands = []

        def send_at(command, timeout=3, flush=True):
            commands.append(command)
            responses = {
                "AT": "OK",
                "AT+CPIN?": "+CPIN: READY\r\nOK",
                'AT+CSCS="UCS2"': "OK",
                'AT+CPMS="SM","SM","SM"': "OK",
                "AT+CREG?": "+CREG: 0,1\r\nOK",
                "AT+CSQ": "+CSQ: 20,99\r\nOK",
                "AT+CPMS?": "+CPMS: 1,20,1,20,1,20\r\nOK",
                "AT+CNUM": "OK",
                "AT+CMGF=1": "OK",
                "AT+CNMI=0,0,0,0,0": "OK",
            }
            return responses.get(command, "OK")

        handler.send_at = send_at
        handler.init_modem()

        self.assertFalse(any(command.startswith("AT+CMGD") for command in commands))


if __name__ == "__main__":
    unittest.main()
