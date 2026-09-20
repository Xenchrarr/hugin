import unittest

from src.mms.decoder import MmsNotification, decode_retrieved_mms
from src.models.sms_message import SmsMessage
from src.sms_handler import SMSHandler


class _BufferedSerial:
    def __init__(self, response: bytes):
        self._response = bytearray(response)
        self.writes: list[bytes] = []

    @property
    def in_waiting(self) -> int:
        return len(self._response)

    def read(self, size: int) -> bytes:
        data = bytes(self._response[:size])
        del self._response[:size]
        return data

    def write(self, data: bytes) -> None:
        self.writes.append(data)


def _sms_deliver_pdu(user_data: bytes, dcs: int, udhi: bool = False) -> str:
    # SMSC omitted; originating address is +4712345678.
    first_octet = 0x40 if udhi else 0x00
    pdu = (
        b"\x00"
        + bytes([first_octet, 10, 0x91])
        + bytes.fromhex("7421436587")
        + bytes([0x00, dcs])
        + bytes.fromhex("62907101000080")
        + bytes([len(user_data)])
        + user_data
    )
    return pdu.hex().upper()


def _multipart_part(headers: bytes, payload: bytes) -> bytes:
    return bytes([len(headers), len(payload)]) + headers + payload


class MmsDecoderTests(unittest.TestCase):
    def test_qird_reader_uses_declared_binary_payload_length(self):
        payload = b"\x8c\x84binary\r\nOK\r\ninside\x00payload"
        response = (
            f"\r\n+QIRD: {len(payload)}\r\n".encode("ascii")
            + payload
            + b"\r\nOK\r\n"
        )
        handler = SMSHandler.__new__(SMSHandler)
        handler.ser = _BufferedSerial(response)

        result = handler._read_qird_payload(0)

        self.assertEqual(payload, result)
        self.assertEqual([b"AT+QIRD=0,1500\r"], handler.ser.writes)

    def test_chunked_http_decoder_accepts_crlf_and_lf_delimiters(self):
        self.assertEqual(
            b"Wikipedia",
            SMSHandler._decode_chunked_http_body(
                b"4\r\nWiki\r\n5\r\npedia\r\n0\r\n\r\n"
            ),
        )
        self.assertEqual(
            b"Wikipedia",
            SMSHandler._decode_chunked_http_body(b"4\nWiki\n5\npedia\n0\n\n"),
        )

    def test_pdu_reader_decodes_regular_ucs2_sms(self):
        pdu = _sms_deliver_pdu("help".encode("utf-16-be"), dcs=0x08)
        response = f"+CMGL: 4,0,,{len(bytes.fromhex(pdu)) - 1}\r\n{pdu}\r\nOK\r\n"

        messages = SMSHandler.parse_pdu_messages(response)

        self.assertEqual(1, len(messages))
        self.assertIsInstance(messages[0], SmsMessage)
        self.assertEqual("+4712345678", messages[0].sender)
        self.assertEqual("help", messages[0].text)

    def test_pdu_reader_extracts_mms_notification(self):
        mms = (
            b"\x8c\x82\x98tx-123\x00\x8d\x92"
            b"\x89\x1a\x80+4712345678/TYPE=PLMN\x00"
            b"\x96Photo from cabin\x00"
            b"\x83http://mms.example/message/abc\x00"
        )
        wsp = b"\x01\x06\x01\xbe" + mms
        udh = b"\x06\x05\x04\x0b\x84\x23\xf0"
        pdu = _sms_deliver_pdu(udh + wsp, dcs=0x04, udhi=True)
        response = f"+CMGL: 7,0,,{len(bytes.fromhex(pdu)) - 1}\r\n{pdu}\r\nOK\r\n"

        messages = SMSHandler.parse_pdu_messages(response)

        self.assertEqual(1, len(messages))
        notification = messages[0]
        self.assertIsInstance(notification, MmsNotification)
        self.assertEqual("+4712345678", notification.sender)
        self.assertEqual("tx-123", notification.transaction_id)
        self.assertEqual("http://mms.example/message/abc", notification.content_location)
        self.assertEqual("Photo from cabin", notification.subject)

    def test_retrieved_multipart_extracts_caption_and_jpeg(self):
        text = b"A snowy morning"
        jpeg = b"\xff\xd8\xff\xe0fake-jpeg\xff\xd9"
        multipart = (
            b"\x02"
            + _multipart_part(b"\x83\x8etxt.txt\x00", text)
            + _multipart_part(b"\x9e\x8ephoto.jpg\x00", jpeg)
        )
        pdu = b"\x8c\x84\x8d\x92\x84\xb3" + multipart

        result = decode_retrieved_mms(pdu)

        self.assertEqual("A snowy morning", result.caption)
        self.assertEqual("image/jpeg", result.image_mime)
        self.assertEqual(jpeg, result.image_bytes)


if __name__ == "__main__":
    unittest.main()
