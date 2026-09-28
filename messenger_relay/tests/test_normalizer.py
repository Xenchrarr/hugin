import unittest

from app.models import RoomInfo
from app.normalizer import MatrixEventNormalizer


class MatrixEventNormalizerTests(unittest.TestCase):
    def setUp(self):
        self.normalizer = MatrixEventNormalizer(
            "@hugin:hugin.local", "@facebookbot:hugin.local", "@facebook_"
        )
        self.room = RoomInfo(
            room_id="!room:hugin.local",
            thread_id="1234",
            title="Family",
            chat_type="group",
            members={"@facebook_42:hugin.local": "Alice"},
        )

    def test_normalizes_inbound_ghost_text(self):
        message = self.normalizer.normalize(
            {
                "type": "m.room.message",
                "event_id": "$event",
                "sender": "@facebook_42:hugin.local",
                "origin_server_ts": 1_700_000_000_999,
                "content": {"msgtype": "m.text", "body": "Hello"},
            },
            self.room,
        )

        self.assertIsNotNone(message)
        self.assertEqual("1234", message.chat_id)
        self.assertEqual("42", message.sender_id)
        self.assertEqual("Alice", message.sender_name)
        self.assertEqual("Hello", message.text)
        self.assertEqual(1_700_000_000, message.timestamp)

    def test_ignores_own_and_non_ghost_events(self):
        base = {
            "type": "m.room.message",
            "event_id": "$event",
            "content": {"msgtype": "m.text", "body": "Hello"},
        }
        for sender in (
            "@hugin:hugin.local",
            "@facebookbot:hugin.local",
            "@someone:hugin.local",
        ):
            self.assertIsNone(self.normalizer.normalize(base | {"sender": sender}, self.room))

    def test_normalizes_media_as_metadata_without_downloading(self):
        message = self.normalizer.normalize(
            {
                "type": "m.room.message",
                "event_id": "$image",
                "sender": "@facebook_42:hugin.local",
                "content": {"msgtype": "m.image", "body": "photo.jpg", "url": "mxc://x/y"},
            },
            self.room,
        )
        self.assertEqual("photo", message.media_type)
        self.assertEqual("photo.jpg", message.caption)


if __name__ == "__main__":
    unittest.main()
