import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


class _FakeFlask:
    def __init__(self, _name):
        pass

    def route(self, *_args, **_kwargs):
        return lambda func: func


class _TimedOut(Exception):
    pass


_request = types.SimpleNamespace(get_json=lambda silent=True: None)
_flask = types.ModuleType("flask")
_flask.Flask = _FakeFlask
_flask.request = _request
_flask.jsonify = lambda value: value
_telegram = types.ModuleType("telegram")
_telegram_error = types.ModuleType("telegram.error")
_telegram_error.TimedOut = _TimedOut
_telegram.error = _telegram_error
sys.modules["flask"] = _flask
sys.modules["telegram"] = _telegram
sys.modules["telegram.error"] = _telegram_error

_SPEC = importlib.util.spec_from_file_location(
    "telegram_api_under_test",
    Path(__file__).resolve().parents[1] / "src" / "api" / "telegram_api.py",
)
telegram_api = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(telegram_api)


class _Bot:
    async def send_message(self, **_kwargs):
        return None


class TelegramApiTests(unittest.TestCase):
    def setUp(self):
        telegram_api._bot = _Bot()
        telegram_api._app_loop = object()
        telegram_api._delivery_futures.clear()
        _request.get_json = lambda silent=True: {
            "chat_id": -42,
            "message": "Solar data",
            "delivery_token": "deye:-42:7",
        }

    def test_timeout_is_uncertain_and_duplicate_token_does_not_resend(self):
        future = Mock()
        future.result.side_effect = _TimedOut("read timed out")

        def schedule(coroutine, _loop):
            coroutine.close()
            return future

        with patch.object(
            telegram_api.asyncio,
            "run_coroutine_threadsafe",
            side_effect=schedule,
        ) as run:
            first = telegram_api.send_message()
            second = telegram_api.send_message()

        self.assertEqual(202, first[1])
        self.assertEqual("uncertain", first[0]["delivery_state"])
        self.assertEqual(202, second[1])
        run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
