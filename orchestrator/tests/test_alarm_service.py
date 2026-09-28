import sys
import types
import unittest
from datetime import datetime, time, timezone
from pathlib import Path
from unittest.mock import Mock, patch

src_package = types.ModuleType("src")
src_package.__path__ = [str(Path(__file__).resolve().parents[1] / "src")]
sys.modules.setdefault("src", src_package)

from src.models.orchestrator.Alarm import Alarm
from src.services.core.alarm_service import AlarmService


def _alarm(max_attempts=3):
    return Alarm(1, 7, "Wake up", True, "daily", None, time(7, 0), None,
                 "Europe/Oslo", 20, max_attempts, 120, True)


class AlarmServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = AlarmService.__new__(AlarmService)
        self.service.scheduler = Mock()
        self.storage = Mock()
        self.storage.get_occurrence.return_value = {
            "id": 11, "alarm_id": 1, "status": "pending", "attempt_count": 0,
        }
        self.storage.get.return_value = _alarm()
        self.storage.recent_attempt_count.return_value = 0
        self.storage.start_attempt.return_value = {
            "id": 21, "attempt_number": 1, "attempt_token": "alarm-11-1",
        }
        self.user = Mock(phone_number="+4712345678")
        self.storage_patch = patch("src.services.core.alarm_service.AlarmStorage", return_value=self.storage)
        self.user_patch = patch("src.services.core.alarm_service.UserStorage")
        self.storage_patch.start()
        users = self.user_patch.start()
        users.return_value.get_user.return_value = self.user

    def tearDown(self):
        self.storage_patch.stop()
        self.user_patch.stop()

    @patch("src.services.core.alarm_service.ring_phone")
    def test_answer_acknowledges_occurrence(self, ring):
        ring.return_value = {"ok": True, "status": "answered", "diagnostics": {}}
        self.service.execute_attempt(11)
        self.storage.finish_occurrence.assert_called_with(11, "acknowledged")
        ring.assert_called_once_with("+4712345678", 20, "alarm-11-1")

    @patch("src.services.core.alarm_service.ring_phone")
    def test_unanswered_call_is_scheduled_for_retry(self, ring):
        ring.return_value = {"ok": True, "status": "ring_timeout", "diagnostics": {}}
        self.service._schedule_attempt = Mock()
        self.service.execute_attempt(11)
        self.storage.mark_retrying.assert_called_once_with(11)
        self.service._schedule_attempt.assert_called_once()

    @patch("src.services.core.alarm_service.MessageHubService")
    @patch("src.services.core.alarm_service.ring_phone")
    def test_ambiguous_call_is_not_retried_and_falls_back(self, ring, hub_type):
        ring.return_value = {"ok": False, "status": "setup_timeout", "uncertain": True}
        self.service._schedule_attempt = Mock()
        self.service.execute_attempt(11)
        self.storage.finish_occurrence.assert_called_with(11, "uncertain")
        self.service._schedule_attempt.assert_not_called()
        hub_type.instance.return_value.submit_sms.assert_called_once()

    @patch("src.services.core.alarm_service.MessageHubService")
    @patch("src.services.core.alarm_service.ring_phone")
    def test_test_call_does_not_fallback_or_disable_alarm(self, ring, hub_type):
        self.storage.get_occurrence.return_value["source"] = "test"
        self.storage.get.return_value = Alarm(1, 7, "Wake up", True, "once", datetime.now(timezone.utc),
                                              None, None, "Europe/Oslo", 20, 3, 120, True)
        ring.return_value = {"ok": False, "status": "setup_timeout", "uncertain": True}
        self.service.execute_attempt(11)
        hub_type.instance.return_value.submit_sms.assert_not_called()
        self.storage.set_enabled.assert_not_called()


if __name__ == "__main__":
    unittest.main()
