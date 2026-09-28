import sys
import types
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from flask import Flask


# Import controller modules without booting the whole hugin-core application.
src_package = types.ModuleType("src")
src_package.__path__ = [str(Path(__file__).resolve().parents[1] / "src")]
sys.modules.setdefault("src", src_package)


def _stub(name, **members):
    module = types.ModuleType(name)
    for key, value in members.items():
        setattr(module, key, value)
    sys.modules[name] = module


class _Client:
    pass


_stub("src.clients.deye", DeyeClient=_Client)
_stub("src.clients.growatt", GrowattClient=_Client)
_stub("src.config", settings=types.SimpleNamespace(TELEGRAM_BOT_URL="http://bot"))
_stub("src.database", get_session=lambda: None)
_stub("src.models.power", PowerReading=object)
_stub(
    "src.services.user_config_service",
    get_primary_user_config=lambda: {},
    get_user_config=lambda _user_id: {},
)

from src.controllers import power_controller


class DeyeWebhookTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(power_controller.power_blueprint, url_prefix="/power")
        self.client = app.test_client()

    def test_send_uses_source_message_as_idempotency_token(self):
        config = {
            "deye_app_id": "app",
            "deye_app_secret": "secret",
            "deye_email": "user@example.com",
            "deye_password": "password",
            "deye_device_sn": "serial",
        }
        inverter_data = {
            "currentPower": 100,
            "todayEnergy": 2,
            "totalEnergy": 300,
            "monthlyEnergy": 20,
            "battery": {},
        }
        response = Mock()
        response.raise_for_status.return_value = None

        with (
            patch.object(power_controller, "get_user_config", return_value=config),
            patch.object(power_controller, "DeyeClient") as client,
            patch.object(power_controller.requests, "post", return_value=response) as post,
        ):
            client.return_value.get_inverter_data.return_value = inverter_data
            result = self.client.post(
                "/power/deye/webhook",
                json={"chat_id": -42, "message_id": 7, "text": "/deye"},
            )

        self.assertEqual(200, result.status_code)
        self.assertEqual("deye:-42:7", post.call_args.kwargs["json"]["delivery_token"])
        self.assertEqual((5, 35), post.call_args.kwargs["timeout"])


if __name__ == "__main__":
    unittest.main()
