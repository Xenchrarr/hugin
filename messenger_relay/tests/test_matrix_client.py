import unittest

from app.matrix_client import MatrixClient


class MatrixPortalParsingTests(unittest.TestCase):
    def test_requires_facebook_bridge_state_and_extracts_thread(self):
        state = [
            {
                "type": "m.bridge",
                "content": {
                    "protocol": {"id": "facebook"},
                    "channel": {"id": "98765", "displayname": "Friends"},
                },
            },
            {
                "type": "m.room.member",
                "state_key": "@facebook_1:hugin.local",
                "content": {"membership": "join", "displayname": "Alice"},
            },
            {
                "type": "m.room.member",
                "state_key": "@facebook_2:hugin.local",
                "content": {"membership": "join", "displayname": "Bob"},
            },
        ]

        room = MatrixClient.parse_portal("!room:hugin.local", state, "@facebook_")

        self.assertEqual("98765", room.thread_id)
        self.assertEqual("Friends", room.title)
        self.assertEqual("group", room.chat_type)
        self.assertEqual("Alice", room.members["@facebook_1:hugin.local"])

    def test_rejects_ordinary_matrix_room(self):
        self.assertIsNone(
            MatrixClient.parse_portal(
                "!room:hugin.local",
                [{"type": "m.room.name", "content": {"name": "Not Messenger"}}],
                "@facebook_",
            )
        )


if __name__ == "__main__":
    unittest.main()
