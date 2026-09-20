import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from src.delivery_ledger import DeliveryLedger, DispatchTokenConflict


class DeliveryLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp_dir.name) / "receipts.sqlite3")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_accepted_receipt_survives_gateway_restart(self):
        ledger = DeliveryLedger(self.path)
        self.assertEqual("send", ledger.begin("dispatch-1", "fingerprint", "sms").state)
        ledger.mark_accepted("dispatch-1", {"ok": True, "message_id": "dispatch-1"})

        restarted = DeliveryLedger(self.path)
        decision = restarted.begin("dispatch-1", "fingerprint", "sms")

        self.assertEqual("accepted", decision.state)
        self.assertEqual("dispatch-1", decision.response["message_id"])

    def test_stale_in_progress_receipt_becomes_uncertain(self):
        ledger = DeliveryLedger(self.path, stale_after_seconds=60)
        ledger.begin("dispatch-2", "fingerprint", "sms")
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                "UPDATE dispatch_receipts SET updated_at = 0 WHERE token = ?",
                ("dispatch-2",),
            )

        decision = DeliveryLedger(self.path).begin(
            "dispatch-2", "fingerprint", "sms"
        )

        self.assertEqual("uncertain", decision.state)

    def test_definite_failure_can_retry_with_the_same_token(self):
        ledger = DeliveryLedger(self.path)
        ledger.begin("dispatch-3", "fingerprint", "sms")
        ledger.mark_failed("dispatch-3", "network unavailable", uncertain=False)

        self.assertEqual(
            "send", ledger.begin("dispatch-3", "fingerprint", "sms").state
        )

    def test_token_cannot_be_reused_for_different_content(self):
        ledger = DeliveryLedger(self.path)
        ledger.begin("dispatch-4", "first", "sms")

        with self.assertRaises(DispatchTokenConflict):
            ledger.begin("dispatch-4", "different", "sms")


if __name__ == "__main__":
    unittest.main()
