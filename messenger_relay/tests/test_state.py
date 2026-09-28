import tempfile
import unittest

from app.state import StateStore


class StateStoreTests(unittest.TestCase):
    def test_conversations_and_sticky_context_survive_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = f"{directory}/state.sqlite3"
            store = StateStore(path)
            store.upsert_conversation("42", "!room:test", "Alice", "Alice", "Hi", 12)
            store.set_context("+47123", "42")
            store.set_value("matrix_since", "s123")
            store.close()

            reopened = StateStore(path)
            self.assertEqual("s123", reopened.get_value("matrix_since"))
            self.assertEqual("42", reopened.conversations()[0]["thread_id"])
            self.assertEqual("!room:test", reopened.get_context("+47123")["room_id"])
            reopened.close()


if __name__ == "__main__":
    unittest.main()
