import os
import tempfile
import unittest
from unittest.mock import patch

from app.config import Config


class ConfigTests(unittest.TestCase):
    def test_renders_server_rnode_and_tcp_configuration(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "RETICULUM_DATA_PATH": directory,
                "RETICULUM_RNODE_ENABLED": "true",
                "RETICULUM_RNODE_PORT": "/dev/ttyACM0",
                "RETICULUM_TCP_SERVER_ENABLED": "true",
            },
            clear=False,
        ):
            config = Config.from_env()
            rendered = config.write_rns_config().read_text(encoding="utf-8")

        self.assertIn("enable_transport = Yes", rendered)
        self.assertIn("share_instance = Yes", rendered)
        self.assertIn("panic_on_interface_error = No", rendered)
        self.assertIn("type = RNodeInterface", rendered)
        self.assertIn("port = /dev/ttyACM0", rendered)
        self.assertIn("frequency = 868000000", rendered)
        self.assertIn("bandwidth = 125000", rendered)
        self.assertIn("txpower = 14", rendered)
        self.assertIn("spreadingfactor = 7", rendered)
        self.assertIn("codingrate = 5", rendered)
        self.assertIn("type = TCPServerInterface", rendered)
        self.assertIn("listen_port = 4242", rendered)

    def test_disabled_interfaces_are_not_rendered(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "RETICULUM_DATA_PATH": directory,
                "RETICULUM_RNODE_ENABLED": "false",
                "RETICULUM_TCP_SERVER_ENABLED": "false",
            },
            clear=False,
        ):
            rendered = Config.from_env().write_rns_config().read_text(encoding="utf-8")

        self.assertNotIn("RNodeInterface", rendered)
        self.assertNotIn("TCPServerInterface", rendered)


if __name__ == "__main__":
    unittest.main()
