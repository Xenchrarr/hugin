import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace


src_package = types.ModuleType("src")
src_package.__path__ = [str(Path(__file__).resolve().parents[1] / "src")]
sys.modules.setdefault("src", src_package)

from src.services.core.sms_routing_service import SmsRoutingService


class _Storage:
    def __init__(self):
        self.conversations = []
        self.messages = []
        self.next_conversation = 1
        self.next_refs = {}

    def get_or_create_conversation(self, **values):
        found = next((c for c in self.conversations if (
            c.owner_user_id, c.service, c.integration_account, c.external_chat_id
        ) == (
            values["owner_user_id"], values["service"], values["integration_account"],
            values["external_chat_id"],
        )), None)
        if found:
            found.display_name = values["display_name"]
            return found
        if any(c.owner_user_id == values["owner_user_id"] and c.alias == values["alias"]
               for c in self.conversations):
            raise RuntimeError("unique alias")
        item = SimpleNamespace(
            id=self.next_conversation, available=True, **values,
            to_dict=lambda: {},
        )
        item.to_dict = lambda item=item: vars(item)
        self.next_conversation += 1
        self.conversations.append(item)
        return item

    def get_conversation(self, owner, conversation_id):
        return next((c for c in self.conversations if c.owner_user_id == owner and c.id == conversation_id), None)

    def get_conversation_by_alias(self, owner, alias):
        return next((c for c in self.conversations if c.owner_user_id == owner and c.alias == alias), None)

    def get_message_by_event(self, owner, direction, event):
        return next((m for m in self.messages if event and m.owner_user_id == owner
                     and m.direction == direction and m.transport_event_id == event), None)

    def get_message_by_reference(self, owner, reference):
        return next((m for m in self.messages if m.owner_user_id == owner and m.reference == reference), None)

    def create_message(self, **values):
        owner = values["owner_user_id"]
        ref = self.next_refs.get(owner, 1)
        self.next_refs[owner] = ref + 1
        defaults = {
            "author": None, "external_message_id": None, "transport_event_id": None,
            "reply_to_reference": None,
        }
        defaults.update(values)
        item = SimpleNamespace(
            id=len(self.messages) + 1, reference=ref, status_detail=None, created_at=None,
            updated_at=None, **defaults,
        )
        self.messages.append(item)
        return item

    def update_status(self, owner, reference, status, detail, external_id):
        item = self.get_message_by_reference(owner, reference)
        if item:
            item.send_status = status
            item.status_detail = detail
            item.external_message_id = external_id or item.external_message_id
        return item

    def list_conversations(self, owner, limit, offset):
        return [c for c in self.conversations if c.owner_user_id == owner][offset:offset + limit]

    def history(self, owner, conversation_id, limit, before):
        values = [m for m in self.messages if m.owner_user_id == owner and m.conversation_id == conversation_id]
        if before is not None:
            values = [m for m in values if m.reference < before]
        return sorted(values, key=lambda m: m.reference, reverse=True)[:limit]


class SmsRoutingServiceTests(unittest.TestCase):
    def setUp(self):
        self.storage = _Storage()
        self.service = SmsRoutingService(self.storage)

    def external(self, owner=1, chat="42", alias="tg/nikolai", event="e1", body="Hello"):
        return self.service.register_external_message(
            owner_user_id=owner, service="tg", integration_account="main",
            external_chat_id=chat, alias=alias, display_name="Nikolai",
            event_id=event, external_message_id=event, body=body,
        )

    def test_distinct_conversations_get_distinct_persistent_references(self):
        nikolai = self.external()
        family = self.external(chat="-100", alias="tg/family", event="e2")
        self.assertEqual("(tg/nikolai #1)\nHello", nikolai["text"])
        route = self.service.prepare_outbound(
            owner_user_id=1, selector_type="reference", selector=nikolai["reference"], body="Yes"
        )
        self.assertNotEqual(nikolai["reference"], family["reference"])
        self.assertEqual("42", route["external_chat_id"])
        self.assertEqual("e1", route["reply_to_external_message_id"])

    def test_duplicate_event_reuses_reference_but_identical_new_events_do_not(self):
        first = self.external(body="same")
        duplicate = self.external(body="same")
        second = self.external(event="e2", body="same")
        self.assertEqual(first["reference"], duplicate["reference"])
        self.assertTrue(duplicate["duplicate"])
        self.assertNotEqual(first["reference"], second["reference"])

    def test_duplicate_sms_event_does_not_create_another_outbound_send(self):
        self.external()
        first = self.service.prepare_outbound(
            owner_user_id=1, selector_type="alias", selector="tg/nikolai",
            body="same", event_id="sms-1",
        )
        duplicate = self.service.prepare_outbound(
            owner_user_id=1, selector_type="alias", selector="tg/nikolai",
            body="same", event_id="sms-1",
        )
        self.assertEqual(first["reference"], duplicate["reference"])
        self.assertTrue(duplicate["duplicate"])

    def test_reference_is_scoped_to_owner(self):
        self.external(owner=1)
        with self.assertRaises(LookupError):
            self.service.prepare_outbound(
                owner_user_id=2, selector_type="reference", selector=1, body="steal"
            )

    def test_unknown_alias_reference_and_empty_body_are_rejected(self):
        with self.assertRaises(LookupError):
            self.service.prepare_outbound(
                owner_user_id=1, selector_type="alias", selector="tg/missing", body="hello"
            )
        with self.assertRaises(LookupError):
            self.service.prepare_outbound(
                owner_user_id=1, selector_type="reference", selector=999, body="hello"
            )
        with self.assertRaises(ValueError):
            self.service.prepare_outbound(
                owner_user_id=1, selector_type="alias", selector="tg/missing", body="  "
            )

    def test_display_name_change_does_not_change_identity_or_alias(self):
        first = self.external()
        second = self.service.register_external_message(
            owner_user_id=1, service="tg", integration_account="main",
            external_chat_id="42", alias="tg/new-title", display_name="New title",
            event_id="e2", external_message_id="2", body="Hi",
        )
        self.assertEqual("tg/nikolai", second["alias"])
        self.assertNotEqual(first["reference"], second["reference"])


if __name__ == "__main__":
    unittest.main()
