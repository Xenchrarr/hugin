-- Rename telegram_chat_id to telegram_user_id to reflect the correct semantic.
-- The column stores a Telegram user ID (stable, per-user), not a chat ID.

ALTER TABLE users RENAME COLUMN telegram_chat_id TO telegram_user_id;
