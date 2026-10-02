import unittest
from unittest.mock import patch
import requests

from src.api.telegram_relay import IntegrationSendResult, TelegramRelayClient
from src.conversation_routing import (
    AMBIGUOUS_RESPONSE,
    ConversationRouter,
    parse_routing_input,
)
from src.command_processor import CommandProcessor


class RoutingParserTests(unittest.TestCase):
    def test_reference_route_preserves_multiline_body(self):
        parsed = parse_routing_input("#184 First line\n  second line")
        self.assertEqual("reference", parsed.argument)
        self.assertEqual(184, parsed.selector)
        self.assertEqual("First line\n  second line", parsed.body)

    def test_alias_route_strips_only_address(self):
        parsed = parse_routing_input("tg/nikolai Hello\nworld")
        self.assertEqual("alias", parsed.argument)
        self.assertEqual("tg/nikolai", parsed.selector)
        self.assertEqual("Hello\nworld", parsed.body)

    def test_bare_reply_is_not_inferred(self):
        self.assertIsNone(parse_routing_input("Yes"))
        self.assertIn("Specify a conversation", AMBIGUOUS_RESPONSE)

    def test_legacy_telegram_commands_are_not_taken_as_aliases(self):
        self.assertIsNone(parse_routing_input("tg/send 1 hello"))


class _Orchestrator:
    def __init__(self, route=None):
        self.route = route
        self.statuses = []

    def prepare_routed_message(self, **_values):
        return self.route

    def update_routed_status(self, *values):
        self.statuses.append(values)

    def routing_chats(self, user_id, offset=0):
        return {"chats": [{"alias": "tg/family", "display_name": "Family"}], "more": False}

    def routing_history(self, user_id, alias, before=None):
        return {"alias": alias, "messages": [], "more": False}


class _Telegram:
    def __init__(self, result=None):
        self.result = result or IntegrationSendResult("accepted", "900")
        self.calls = []

    def send_routed_message(self, chat_id, body, reply_to_message_id=None):
        self.calls.append((chat_id, body, reply_to_message_id))
        return self.result


class ConversationRouterTests(unittest.TestCase):
    def test_reference_reply_targets_stored_chat_and_original_message(self):
        api = _Orchestrator({
            "duplicate": False, "reference": 186, "status": "prepared",
            "alias": "tg/nikolai", "service": "tg", "external_chat_id": "42",
            "body": "Yes, around 18:00.", "reply_to_external_message_id": "700",
            "available": True,
        })
        telegram = _Telegram()
        result = ConversationRouter(api, telegram).handle(
            parse_routing_input("#184 Yes, around 18:00."), user_id=1, event_id="sms:1"
        )
        self.assertEqual("(hub) Sent to tg/nikolai.", result)
        self.assertEqual([(42, "Yes, around 18:00.", "700")], telegram.calls)
        self.assertEqual("accepted", api.statuses[0][2])

    def test_uncertain_send_is_reported_and_not_called_accepted(self):
        route = {
            "duplicate": False, "reference": 2, "alias": "tg/family", "service": "tg",
            "external_chat_id": "-100", "body": "Dinner?", "available": True,
        }
        result = ConversationRouter(
            _Orchestrator(route), _Telegram(IntegrationSendResult("uncertain", detail="timeout"))
        ).handle(parse_routing_input("tg/family Dinner?"), user_id=1)
        self.assertIn("uncertain", result)

    def test_queued_and_failed_statuses_are_reported_accurately(self):
        route = {
            "duplicate": False, "reference": 2, "alias": "tg/family", "service": "tg",
            "external_chat_id": "-100", "body": "Dinner?", "available": True,
        }
        queued = ConversationRouter(
            _Orchestrator(route), _Telegram(IntegrationSendResult("queued"))
        ).handle(parse_routing_input("tg/family Dinner?"), user_id=1)
        failed = ConversationRouter(
            _Orchestrator(route), _Telegram(IntegrationSendResult("failed", detail="offline"))
        ).handle(parse_routing_input("tg/family Dinner?"), user_id=1)
        self.assertEqual("(hub) Queued for tg/family.", queued)
        self.assertIn("offline", failed)

    def test_empty_body_is_actionable_without_forwarding(self):
        telegram = _Telegram()
        result = ConversationRouter(_Orchestrator(), telegram).handle(
            parse_routing_input("#184"), user_id=1
        )
        self.assertIn("body is empty", result)
        self.assertEqual([], telegram.calls)

    def test_chat_and_history_commands_are_hub_labelled(self):
        router = ConversationRouter(_Orchestrator(), _Telegram())
        self.assertIn("tg/family - Family", router.handle(parse_routing_input("/chats"), user_id=1))
        self.assertTrue(router.handle(parse_routing_input("/history tg/family"), user_id=1).startswith("(hub)"))


class AuthorizationAndFallbackTests(unittest.TestCase):
    def test_unauthorized_sender_gets_no_loop_generating_response(self):
        with patch("src.command_processor._orchestrator.lookup_user", return_value=None):
            self.assertIsNone(CommandProcessor().process("/chats", sender="+4700000000"))

    def test_authorized_bare_reply_is_rejected_without_forwarding(self):
        user = {"id": 1, "is_admin": True, "allowed_commands": None, "config": {}}
        with patch("src.command_processor._orchestrator.lookup_user", return_value=user):
            result = CommandProcessor().process("Yes", sender="+4712345678")
        self.assertEqual(AMBIGUOUS_RESPONSE, result)


class TelegramStatusTests(unittest.TestCase):
    @patch("src.api.telegram_relay.requests.post", side_effect=requests.ReadTimeout())
    def test_read_timeout_is_uncertain_not_failed(self, _post):
        result = TelegramRelayClient("http://telegram").send_routed_message(42, "hello")
        self.assertEqual("uncertain", result.status)

    @patch("src.api.telegram_relay.requests.post", side_effect=requests.ConnectionError())
    def test_connection_failure_is_definite_failure(self, _post):
        result = TelegramRelayClient("http://telegram").send_routed_message(42, "hello")
        self.assertEqual("failed", result.status)


if __name__ == "__main__":
    unittest.main()
