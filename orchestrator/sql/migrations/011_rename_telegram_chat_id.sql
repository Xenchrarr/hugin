-- Rename telegram_chat_id to telegram_user_id to reflect the correct semantic.
-- The column stores a Telegram user ID (stable, per-user), not a chat ID.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'users'
          AND column_name = 'telegram_chat_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'users'
          AND column_name = 'telegram_user_id'
    ) THEN
        ALTER TABLE users RENAME COLUMN telegram_chat_id TO telegram_user_id;
    END IF;
END $$;
