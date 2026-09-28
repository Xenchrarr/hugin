import tempfile
import unittest
from pathlib import Path

from app.state import StateStore


class StateStoreTests(unittest.TestCase):
    def test_contacts_context_and_delivery_receipt_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            store = StateStore(path)
            destination = "ab" * 16
            store.remember_contact(destination, "Alice", "hello")
            store.set_context("+47123", destination)
            store.record_delivery("token-1", "message-1")

            reopened = StateStore(path)

            self.assertEqual("Alice", reopened.contacts()[0]["display_name"])
            self.assertEqual(destination, reopened.get_context("+47123")["destination_hash"])
            self.assertEqual("message-1", reopened.delivery_result("token-1"))


if __name__ == "__main__":
    unittest.main()

