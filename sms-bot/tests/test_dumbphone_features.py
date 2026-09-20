import unittest
import threading
from unittest.mock import patch

from src import command_processor
from src.commands.brief_command import _parse_time
from src.commands.news_command import _headlines
from src.commands.today_command import format_today
from src.services.dumbphone_session import DumbphoneSessionService
from src.sms_handler import SMSHandler


class DumbphoneSessionTests(unittest.TestCase):
    def test_long_result_is_paged_and_navigation_works(self):
        service = DumbphoneSessionService()
        first = service.first_page("+47", "word " * 100)
        self.assertLessEqual(len(first), 160)
        self.assertIn("(1/", first)
        second = service.move("+47", 1)
        self.assertLessEqual(len(second), 160)
        self.assertIn("(2/", second)

    def test_repeat_memory_and_cancel(self):
        service = DumbphoneSessionService()
        service.remember_command("+47", "today")
        self.assertEqual("today", service.last_command("+47"))
        self.assertEqual("Cancelled.", service.cancel("+47"))
        self.assertEqual("", service.last_command("+47"))


class FormattingTests(unittest.TestCase):
    def test_brief_time_accepts_dumbphone_formats(self):
        self.assertEqual("07:30", _parse_time("730"))
        self.assertEqual("07:30", _parse_time("07:30"))
        self.assertIsNone(_parse_time("2560"))

    def test_today_format_is_compact_and_useful(self):
        result = format_today({
            "date": "2026-09-17",
            "events": [{"start": "2026-09-17T10:00:00+02:00", "summary": "Dentist"}],
            "reminders": [{"due_at": "2026-09-17T21:00:00+02:00", "title": "Pills"}],
        }, "12C rain", "400W")
        self.assertIn("10:00 Dentist", result)
        self.assertIn("21:00 Pills", result)
        self.assertIn("Wx: 12C rain", result)

    def test_rss_titles_are_extracted(self):
        xml = b"<rss><channel><title>Feed</title><item><title>One</title></item><item><title>Two</title></item></channel></rss>"
        self.assertEqual(["One", "Two"], _headlines(xml, 2))


class _FakeOrchestrator:
    def __init__(self, config=None):
        self.config = config or {}

    def lookup_user(self, channel, identifier):
        return {"id": 1, "is_admin": True, "allowed_commands": None, "config": self.config}


class ProcessorUxTests(unittest.TestCase):
    def setUp(self):
        self.original = command_processor._orchestrator

    def tearDown(self):
        command_processor._orchestrator = self.original

    def test_menu_and_numeric_help_shortcut_route(self):
        command_processor._orchestrator = _FakeOrchestrator()
        processor = command_processor.CommandProcessor()
        self.assertIn("1 Today", processor.process("m", sender="+47"))
        result = processor.process("6", sender="+47")
        self.assertIn("cmds:", result)

    def test_custom_shortcut_routes_to_menu(self):
        command_processor._orchestrator = _FakeOrchestrator({"sms_shortcuts": {"9": "menu"}})
        processor = command_processor.CommandProcessor()
        self.assertIn("1 Today", processor.process("9", sender="+47"))

    def test_scene_name_can_be_used_as_a_direct_command(self):
        fake = _FakeOrchestrator({"sms_scenes": {"bed": "automation.bedtime"}})
        command_processor._orchestrator = fake
        with patch("src.commands.scene_command.trigger_automation", return_value={"ok": True}) as trigger:
            processor = command_processor.CommandProcessor()
            self.assertEqual("OK bed", processor.process("bed", sender="+47"))
            trigger.assert_called_once_with("automation.bedtime", variables=None)


class MissedCallTests(unittest.TestCase):
    def test_incoming_call_is_returned_once_and_hung_up(self):
        handler = SMSHandler.__new__(SMSHandler)
        handler._modem_lock = threading.RLock()
        handler._last_call_by_number = {}
        commands = []

        def send_at(command, timeout=3):
            commands.append(command)
            if command == "AT+CLCC":
                return '+CLCC: 1,1,4,0,0,"+4712345678",145\nOK'
            return "OK"

        handler.send_at = send_at
        self.assertEqual(["+4712345678"], handler.poll_incoming_calls())
        self.assertIn("ATH", commands)
        self.assertEqual([], handler.poll_incoming_calls())


if __name__ == "__main__":
    unittest.main()
