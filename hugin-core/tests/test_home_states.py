import unittest
import sys
import types
from pathlib import Path

from flask import Flask

# Import controller modules without booting the whole hugin-core application.
src_package = types.ModuleType("src")
src_package.__path__ = [str(Path(__file__).resolve().parents[1] / "src")]
sys.modules.setdefault("src", src_package)

from src.controllers import home_controller


class _FakeHomeAssistant:
    def get(self, path):
        self.path = path
        return [
            {
                "entity_id": "binary_sensor.front_door",
                "state": "off",
                "attributes": {"friendly_name": "Front door"},
            },
            {
                "entity_id": "sensor.living_temperature",
                "state": "21.5",
                "attributes": {"unit_of_measurement": "C"},
            },
        ]


class HomeStatesTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(home_controller.home_blueprint, url_prefix="/home")
        self.client = app.test_client()

    def test_returns_requested_states_and_marks_missing_entity(self):
        fake = _FakeHomeAssistant()
        original = home_controller.homeassistant_service.get_api
        home_controller.homeassistant_service.get_api = lambda: fake
        try:
            response = self.client.get(
                "/home/states?entities=binary_sensor.front_door,sensor.missing"
            )
        finally:
            home_controller.homeassistant_service.get_api = original

        self.assertEqual(200, response.status_code)
        states = response.get_json()["states"]
        self.assertEqual("off", states[0]["state"])
        self.assertEqual("unavailable", states[1]["state"])
        self.assertEqual("/api/states", fake.path)


if __name__ == "__main__":
    unittest.main()
