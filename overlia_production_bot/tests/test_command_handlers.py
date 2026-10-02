import unittest
from datetime import datetime, timezone

from telegram import Chat, Message, Update, User
from telegram.ext import CommandHandler

from src.services.bot import register_update_handlers


class _Application:
    def __init__(self):
        self.handlers = []
        self.error_handlers = []

    def add_handler(self, handler):
        self.handlers.append(handler)

    def add_error_handler(self, handler):
        self.error_handlers.append(handler)


class CommandHandlerTests(unittest.TestCase):
    def setUp(self):
        self.application = _Application()
        register_update_handlers(self.application)

    @staticmethod
    def _plain_text_update(text: str) -> Update:
        message = Message(
            message_id=1,
            date=datetime.now(timezone.utc),
            chat=Chat(id=1, type="private"),
            from_user=User(id=1, first_name="Test", is_bot=False),
            text=text,
        )
        return Update(update_id=1, message=message)

    def test_all_message_text_actions_are_slash_command_handlers(self):
        self.assertTrue(self.application.handlers)
        self.assertTrue(
            all(isinstance(handler, CommandHandler) for handler in self.application.handlers)
        )

    def test_plain_command_words_do_not_match_any_handler(self):
        command_handlers = [
            handler for handler in self.application.handlers
            if isinstance(handler, CommandHandler)
        ]

        for handler in command_handlers:
            for command in handler.commands:
                with self.subTest(command=command):
                    update = self._plain_text_update(command)
                    self.assertIsNone(handler.check_update(update))


if __name__ == "__main__":
    unittest.main()
