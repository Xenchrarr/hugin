import tempfile
import unittest
from pathlib import Path

from app.announces import AnnounceHandler
from app.chat import ChatStore


class _Identity:
    hash = bytes.fromhex("aa" * 16)


class _Destination:
    @staticmethod
    def hash(identity, app_name, aspect):
        values = {
            ("lxmf", "delivery"): bytes.fromhex("11" * 16),
            ("lxmf", "propagation"): bytes.fromhex("22" * 16),
            ("nomadnetwork", "node"): bytes.fromhex("33" * 16),
        }
        return values[(app_name, aspect)]


class _Transport:
    @staticmethod
    def hops_to(destination_hash):
        return 3


class _Rns:
    Destination = _Destination
    Transport = _Transport


class _Lxmf:
    @staticmethod
    def display_name_from_app_data(app_data):
        return "Alice"

    @staticmethod
    def pn_name_from_app_data(app_data):
        return "Relay One"


class AnnounceHandlerTests(unittest.TestCase):
    def test_decodes_known_announce_aspects(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ChatStore(Path(directory) / "chat.sqlite3")
            learned_names = []
            handler = AnnounceHandler(
                _Rns,
                _Lxmf,
                store,
                lambda destination, name: learned_names.append((destination, name)),
            )

            handler.received_announce(
                bytes.fromhex("11" * 16),
                _Identity(),
                b"packed-name",
                bytes.fromhex("44" * 16),
                False,
            )
            handler.received_announce(
                bytes.fromhex("33" * 16), _Identity(), b"Nomad Site", None, False
            )

            announces = store.announces()

        by_hash = {item["destination_hash"]: item for item in announces}
        delivery = by_hash["11" * 16]
        site = by_hash["33" * 16]
        self.assertEqual("lxmf.delivery", delivery["aspect"])
        self.assertEqual("Alice", delivery["display_name"])
        self.assertEqual(3, delivery["hops"])
        self.assertEqual("nomadnetwork.node", site["aspect"])
        self.assertEqual("Nomad Site", site["display_name"])
        self.assertEqual([("11" * 16, "Alice")], learned_names)


if __name__ == "__main__":
    unittest.main()
