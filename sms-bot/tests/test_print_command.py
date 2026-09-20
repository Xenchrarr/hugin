import unittest
from unittest.mock import patch

from src.commands.print_command import PrintCommand
from src.models.parsed_command import ParsedCommand


class PrintCommandTests(unittest.TestCase):
    @patch("src.commands.print_command.print_image", return_value=True)
    @patch("src.commands.print_command._core.get_weather_image_bytes", return_value=b"png")
    def test_weather_print_uses_light_mode(self, get_weather_image, print_image):
        command = ParsedCommand(
            path="print",
            positional=["weather"],
            user_config={"weather_location_id": "1-72837"},
        )

        result = PrintCommand().execute(command)

        self.assertEqual("OK printed", result)
        get_weather_image.assert_called_once_with("1-72837", dark_mode=False)
        print_image.assert_called_once_with(b"png")


if __name__ == "__main__":
    unittest.main()
