SELECT
    id, username, display_name, phone_number, telegram_user_id, config, created_at, updated_at, is_admin
FROM users
WHERE telegram_user_id = %s
LIMIT 1;
