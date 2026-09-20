"""Opt-in PostgreSQL integration tests for Message Hub queue invariants.

Set MESSAGE_HUB_TEST_DATABASE_URL to an expendable PostgreSQL database. Every
run creates and drops an isolated schema; it does not modify the public schema.
"""

from __future__ import annotations

import os
import sys
import types
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import psycopg
    from psycopg import sql
except ImportError:  # pragma: no cover - dependency is present in the service image
    psycopg = None
    sql = None


src_package = types.ModuleType("src")
src_package.__path__ = [str(Path(__file__).resolve().parents[1] / "src")]
sys.modules.setdefault("src", src_package)

from src.persistence.MessageHubStorage import MessageHubStorage


TEST_DATABASE_URL = os.environ.get("MESSAGE_HUB_TEST_DATABASE_URL", "").strip()


class _ConnectionDb:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, params=None):
        return self.connection.execute(query, params)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()


@unittest.skipUnless(
    TEST_DATABASE_URL and psycopg is not None,
    "set MESSAGE_HUB_TEST_DATABASE_URL to run PostgreSQL integration tests",
)
class MessageHubPostgresTests(unittest.TestCase):
    schema: str

    @classmethod
    def setUpClass(cls):
        cls.schema = "message_hub_test_" + uuid.uuid4().hex
        with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as admin:
            admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(cls.schema)))

        with cls._connect() as connection:
            connection.execute(
                "CREATE TABLE notification_settings (id BIGINT PRIMARY KEY)"
            )
            connection.execute(
                "CREATE TABLE reminders (id BIGINT PRIMARY KEY)"
            )
            migrations = Path(__file__).resolve().parents[1] / "sql" / "migrations"
            connection.execute(
                (migrations / "009_add_users.sql").read_text(encoding="utf-8")
            )
            catch_up = (
                "010_add_is_admin.sql",
                "011_rename_telegram_chat_id.sql",
                "012_add_user_command_permissions.sql",
                "012_telegram_relay.sql",
                "013_telegram_relay_preset.sql",
                "014_ical_sources.sql",
                "015_ical_sources_color.sql",
                "016_deye_telegram_rule.sql",
                "017_sms_outbox.sql",
                "018_checkins.sql",
                "019_message_routes.sql",
            )
            # Simulate a database whose objects exist but whose schema history
            # stopped at 009, then prove the catch-up sequence is repeat-safe.
            for _ in range(2):
                for filename in catch_up:
                    connection.execute(
                        (migrations / filename).read_text(encoding="utf-8")
                    )
            for filename in (
                "020_message_hub.sql",
                "021_message_hub_inbox.sql",
                "022_remove_legacy_message_paths.sql",
                "023_message_hub_delivery_ack_links.sql",
                "024_message_hub_attachments.sql",
                "025_message_gateway_dispatch_tokens.sql",
            ):
                connection.execute((migrations / filename).read_text(encoding="utf-8"))
            connection.commit()

    @classmethod
    def tearDownClass(cls):
        with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(cls.schema)
                )
            )

    @classmethod
    def _connect(cls):
        connection = psycopg.connect(TEST_DATABASE_URL)
        connection.execute(
            sql.SQL("SET search_path TO {}").format(sql.Identifier(cls.schema))
        )
        return connection

    def setUp(self):
        with self._connect() as connection:
            connection.execute(
                "TRUNCATE message_hub_messages, message_gateway_incidents "
                "RESTART IDENTITY CASCADE"
            )
            connection.execute(
                "UPDATE message_gateways SET enabled = 1, status = 'healthy', "
                "consecutive_failures = 0, consecutive_successes = 0"
            )
            connection.commit()

    def _storage(self, connection):
        storage = MessageHubStorage.__new__(MessageHubStorage)
        storage._db = _ConnectionDb(connection)
        return storage

    def _enqueue(
        self,
        storage,
        *,
        phone="+4711111111",
        key=None,
        policy="replay",
        acknowledge_delivery_ids=None,
        attachments=None,
    ):
        return storage.enqueue(
            direction="outbound",
            kind="mms" if attachments else "text",
            payload={"text": "hello"},
            metadata={"source_type": "telegram", "source_label": "Family"},
            priority=50,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            deliveries=[{
                "gateway_key": "sms-main",
                "address": {"phone": phone},
                "recipient_key": f"sms:{phone}",
                "recovery_policy": policy,
                "priority": 50,
                "max_attempts": 8,
                "acknowledge_delivery_ids": acknowledge_delivery_ids or [],
            }],
            attachments=attachments or [],
            idempotency_key=key,
        )

    def test_cutover_keeps_migrated_route_and_removes_old_tables(self):
        with self._connect() as connection:
            endpoint_count = connection.execute(
                "SELECT COUNT(*) FROM message_relay_endpoints "
                "WHERE name = 'Deye Solar Webhook'"
            ).fetchone()[0]
            route_count = connection.execute(
                "SELECT COUNT(*) FROM message_relay_routes "
                "WHERE name = 'Deye solar query'"
            ).fetchone()[0]
            old_tables = connection.execute(
                "SELECT to_regclass('telegram_relay_destinations'), "
                "to_regclass('telegram_relay_rules'), to_regclass('sms_outbox')"
            ).fetchone()

        self.assertEqual(1, endpoint_count)
        self.assertEqual(1, route_count)
        self.assertEqual((None, None, None), old_tables)

    def test_enqueue_is_idempotent(self):
        with self._connect() as connection:
            storage = self._storage(connection)
            first_message, first_deliveries = self._enqueue(storage, key="same-event")
            second_message, second_deliveries = self._enqueue(storage, key="same-event")

        self.assertEqual(first_message.id, second_message.id)
        self.assertEqual(first_deliveries[0].id, second_deliveries[0].id)

    def test_attachment_storage_is_idempotent_and_cascades_with_message(self):
        attachment = {
            "position": 0,
            "content_type": "image/jpeg",
            "filename": "camera.jpg",
            "content": b"jpeg-data",
            "size_bytes": 9,
            "sha256": "a" * 64,
        }
        with self._connect() as connection:
            storage = self._storage(connection)
            first_message, _ = self._enqueue(
                storage,
                key="same-media",
                attachments=[attachment],
            )
            second_message, _ = self._enqueue(
                storage,
                key="same-media",
                attachments=[attachment],
            )
            stored = storage.get_attachments(first_message.id)
            connection.execute(
                "DELETE FROM message_hub_messages WHERE id = %s",
                (first_message.id,),
            )
            remaining = connection.execute(
                "SELECT COUNT(*) FROM message_hub_attachments WHERE message_id = %s",
                (first_message.id,),
            ).fetchone()[0]
            connection.rollback()

        self.assertEqual(first_message.id, second_message.id)
        self.assertEqual(1, len(stored))
        self.assertEqual(b"jpeg-data", stored[0].content)
        self.assertEqual(0, remaining)

    def test_idempotent_media_submission_rejects_different_attachment(self):
        first = {
            "position": 0,
            "content_type": "image/jpeg",
            "filename": "camera.jpg",
            "content": b"first",
            "size_bytes": 5,
            "sha256": "a" * 64,
        }
        changed = dict(first, content=b"other", sha256="b" * 64)
        with self._connect() as connection:
            storage = self._storage(connection)
            self._enqueue(storage, key="changed-media", attachments=[first])

            with self.assertRaisesRegex(ValueError, "different attachments"):
                self._enqueue(storage, key="changed-media", attachments=[changed])

    def test_two_workers_claim_a_delivery_only_once(self):
        with self._connect() as connection:
            self._enqueue(self._storage(connection))

        def claim(token):
            with self._connect() as worker_connection:
                delivery = self._storage(worker_connection).claim_next(token)
                return delivery.id if delivery else None

        with ThreadPoolExecutor(max_workers=2) as pool:
            claimed = list(pool.map(claim, ("worker-a", "worker-b")))

        self.assertEqual(1, len([delivery_id for delivery_id in claimed if delivery_id]))

    def test_acknowledgement_is_scoped_to_the_recipient(self):
        with self._connect() as connection:
            storage = self._storage(connection)
            _, first = self._enqueue(storage, phone="+4711111111", policy="inbox_only")
            _, second = self._enqueue(storage, phone="+4722222222", policy="inbox_only")

            count = storage.acknowledge_inbox(
                "sms:+4711111111", [first[0].id, second[0].id]
            )
            statuses = dict(connection.execute(
                "SELECT id, status FROM message_hub_deliveries ORDER BY id"
            ).fetchall())

        self.assertEqual(1, count)
        self.assertEqual("acknowledged", statuses[first[0].id])
        self.assertEqual("held", statuses[second[0].id])

    def test_response_acceptance_atomically_acknowledges_linked_inbox_items(self):
        with self._connect() as connection:
            storage = self._storage(connection)
            _, held = self._enqueue(storage, policy="inbox_only", key="held-message")
            _, response = self._enqueue(
                storage,
                key="command-response",
                acknowledge_delivery_ids=[held[0].id],
            )

            claimed = storage.claim_next("worker-a")
            self.assertEqual(response[0].id, claimed.id)
            storage.mark_accepted(claimed, "provider-1")
            statuses = dict(connection.execute(
                "SELECT id, status FROM message_hub_deliveries ORDER BY id"
            ).fetchall())

        self.assertEqual("acknowledged", statuses[held[0].id])
        self.assertEqual("accepted", statuses[response[0].id])

    def test_failed_response_does_not_acknowledge_linked_inbox_items(self):
        with self._connect() as connection:
            storage = self._storage(connection)
            _, held = self._enqueue(storage, policy="inbox_only", key="held-failed")
            _, response = self._enqueue(
                storage,
                key="failed-response",
                acknowledge_delivery_ids=[held[0].id],
            )

            claimed = storage.claim_next("worker-a")
            self.assertEqual(response[0].id, claimed.id)
            storage.mark_failed(
                claimed,
                "temporary failure",
                datetime.now(timezone.utc) + timedelta(minutes=1),
            )
            held_status = connection.execute(
                "SELECT status FROM message_hub_deliveries WHERE id = %s",
                (held[0].id,),
            ).fetchone()[0]

        self.assertEqual("held", held_status)

    def test_uncertain_delivery_requires_forced_retry_and_rotates_token(self):
        with self._connect() as connection:
            storage = self._storage(connection)
            self._enqueue(storage, key="uncertain-response")
            claimed = storage.claim_next("worker-a")
            original_token = claimed.dispatch_token

            self.assertTrue(storage.mark_uncertain(claimed, "ambiguous modem result"))
            self.assertIsNone(storage.retry_delivery(claimed.id))
            retried = storage.retry_delivery_anyway(claimed.id)

        self.assertEqual("pending", retried.status)
        self.assertNotEqual(original_token, retried.dispatch_token)

    def test_inbox_hides_items_linked_to_an_active_response(self):
        with self._connect() as connection:
            storage = self._storage(connection)
            _, held = self._enqueue(storage, policy="inbox_only", key="held-active")
            self._enqueue(
                storage,
                key="active-response",
                acknowledge_delivery_ids=[held[0].id],
            )

            items = storage.prepare_inbox("sms:+4711111111")
            summary = storage.get_inbox_summary("sms:+4711111111")

        self.assertEqual([], items)
        self.assertEqual(0, summary["total"])

    def test_response_cannot_acknowledge_another_recipient(self):
        with self._connect() as connection:
            storage = self._storage(connection)
            _, held = self._enqueue(
                storage,
                phone="+4722222222",
                policy="inbox_only",
                key="other-recipient",
            )

            with self.assertRaisesRegex(ValueError, "response recipient"):
                self._enqueue(
                    storage,
                    phone="+4711111111",
                    key="invalid-response",
                    acknowledge_delivery_ids=[held[0].id],
                )

    def test_retention_preserves_nonterminal_messages(self):
        with self._connect() as connection:
            storage = self._storage(connection)
            terminal_message, terminal = self._enqueue(storage, phone="+4711111111")
            active_message, _ = self._enqueue(storage, phone="+4722222222")
            connection.execute(
                "UPDATE message_hub_deliveries SET status = 'accepted' WHERE id = %s",
                (terminal[0].id,),
            )
            connection.execute(
                "UPDATE message_hub_messages SET created_at = NOW() - INTERVAL '40 days'"
            )
            connection.commit()

            removed = storage.cleanup_terminal(30)
            remaining = {
                row[0] for row in connection.execute(
                    "SELECT id FROM message_hub_messages"
                ).fetchall()
            }

        self.assertEqual(1, removed["messages"])
        self.assertNotIn(terminal_message.id, remaining)
        self.assertIn(active_message.id, remaining)


if __name__ == "__main__":
    unittest.main()
