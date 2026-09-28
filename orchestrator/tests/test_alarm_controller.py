import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from flask import Flask

src_package = types.ModuleType("src")
src_package.__path__ = [str(Path(__file__).resolve().parents[1] / "src")]
sys.modules.setdefault("src", src_package)

from src.controllers.alarm_controller import alarm_blueprint


class AlarmControllerTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(alarm_blueprint, url_prefix="/alarms")
        self.client = app.test_client()
        self.auth = patch("src.auth.decode_token", return_value={"sub": "7", "is_admin": False})
        self.auth.start()

    def tearDown(self):
        self.auth.stop()

    def headers(self):
        return {"Authorization": "Bearer token"}

    @patch("src.controllers.alarm_controller.AlarmService")
    @patch("src.controllers.alarm_controller.AlarmStorage")
    def test_create_daily_alarm_for_authenticated_user(self, storage_type, service_type):
        storage_type.return_value.save.side_effect = lambda alarm: alarm
        response = self.client.post("/alarms", headers=self.headers(), json={
            "label": "Wake", "schedule_type": "daily", "local_time": "07:00",
        })
        self.assertEqual(201, response.status_code)
        self.assertEqual(7, response.get_json()["user_id"])
        service_type.instance.return_value.schedule.assert_called_once()

    @patch("src.controllers.alarm_controller.AlarmStorage")
    def test_rejects_invalid_weekdays(self, storage_type):
        response = self.client.post("/alarms", headers=self.headers(), json={
            "label": "Wake", "schedule_type": "weekdays", "local_time": "07:00", "weekdays": [8],
        })
        self.assertEqual(400, response.status_code)
        storage_type.return_value.save.assert_not_called()

    @patch("src.controllers.alarm_controller.AlarmStorage")
    def test_service_list_is_scoped_to_requested_user(self, storage_type):
        with patch("src.auth.SERVICE_KEY", "secret"):
            response = self.client.get(
                "/alarms?user_id=12", headers={"X-Service-Key": "secret"},
            )
        self.assertEqual(200, response.status_code)
        storage_type.return_value.list.assert_called_once_with(12)


if __name__ == "__main__":
    unittest.main()
